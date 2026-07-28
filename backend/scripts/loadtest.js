// k6 load test against spec §23's API latency budgets:
//   - read endpoints (warm cache):  p95 < 200ms
//   - write endpoints:              p95 < 500ms
//
// Run against a locally-running backend pointed at the real seeded catalogue (8,103 products),
// not the ephemeral pytest test database — this measures real query plans against real data
// volume, not an empty schema. No Docker/cloud target needed: k6 is a static binary.
//
//   k6 run -e BASE_URL=http://127.0.0.1:8020 backend/scripts/loadtest.js
//
// Two scenarios run back-to-back (not concurrently, so their p95s aren't contending with each
// other's load): `reads` hits the product listing/PDP/category endpoints every real shopper
// request depends on; `writes` exercises a guest add-to-cart, the cheapest genuine write that
// still does a real INSERT (cart + cart_item creation) rather than a no-op.
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';

// A handful of real slugs, fetched once via setup() rather than hardcoded, so this script keeps
// working if the seeded catalogue is ever re-ingested with different products.
export function setup() {
  const res = http.get(`${BASE_URL}/api/v1/products?per_page=20`);
  const slugs = JSON.parse(res.body).data.map((p) => p.slug);

  // `writes` needs products that actually have purchasable stock — per-variant stock is
  // randomized 0-60 at ingest (spec §7.3), so some products have every variant sold out. Sampling
  // from the unfiltered list above and falling back to variants[0] when none are available isn't a
  // load test of the write path, it's an accidental test of the (correctly-enforced) 409
  // ITEM_UNAVAILABLE business rule instead — filter here so `writes` only ever hits real stock.
  const inStockRes = http.get(`${BASE_URL}/api/v1/products?per_page=20&in_stock=true`);
  const inStockSlugs = JSON.parse(inStockRes.body).data.map((p) => p.slug);

  return { slugs, inStockSlugs };
}

export const options = {
  scenarios: {
    reads: {
      executor: 'ramping-vus',
      exec: 'reads',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 20 },
        { duration: '20s', target: 20 },
        { duration: '5s', target: 0 },
      ],
    },
    writes: {
      executor: 'ramping-vus',
      exec: 'writes',
      startTime: '40s', // after `reads` finishes, so the two scenarios don't share load
      startVUs: 0,
      stages: [
        { duration: '10s', target: 20 },
        { duration: '20s', target: 20 },
        { duration: '5s', target: 0 },
      ],
    },
  },
  thresholds: {
    'http_req_duration{scenario:reads}': ['p(95)<200'],
    'http_req_duration{scenario:writes}': ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
  },
};

export function reads(data) {
  const slug = data.slugs[Math.floor(Math.random() * data.slugs.length)];

  const listing = http.get(`${BASE_URL}/api/v1/products?per_page=24&page=${1 + (__VU % 10)}`);
  check(listing, { 'listing 200': (r) => r.status === 200 });

  const pdp = http.get(`${BASE_URL}/api/v1/products/${slug}`);
  check(pdp, { 'pdp 200': (r) => r.status === 200 });

  const categories = http.get(`${BASE_URL}/api/v1/categories`);
  check(categories, { 'categories 200': (r) => r.status === 200 });

  sleep(0.2);
}

export function writes(data) {
  const jar = http.cookieJar();
  const slug = data.inStockSlugs[Math.floor(Math.random() * data.inStockSlugs.length)];
  const pdp = http.get(`${BASE_URL}/api/v1/products/${slug}`, { jar });
  const variants = JSON.parse(pdp.body).data.variants;
  const variant = variants.find((v) => v.available > 0);
  if (!variant) return; // in_stock=true means *some* variant has stock, but not necessarily this one

  const add = http.post(
    `${BASE_URL}/api/v1/cart/items`,
    JSON.stringify({ variant_id: variant.id, quantity: 1 }),
    { headers: { 'Content-Type': 'application/json' }, jar },
  );
  check(add, { 'add-to-cart 201/200': (r) => r.status === 200 || r.status === 201 });

  sleep(0.2);
}
