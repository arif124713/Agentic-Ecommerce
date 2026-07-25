# BlackCart — Progress Log

Tracks what's actually built against [`spec.MD`](./spec.MD), and exactly how. Written after each
working session so a future session (or another engineer) can pick this up without re-deriving
context. Status legend: ✅ done · 🟡 partial · ⬜ not started.

**Overall**: Phase 0 (Foundations) complete, Phase 1 (Data & Catalogue) mostly complete for the
public storefront read path. Phase 2 (Identity) is **end-to-end functional** (§8). Phase 3
(Commerce) is now also **end-to-end functional** — cart (guest + merge-on-login), coupons,
checkout, order creation with real stock locking, a simulated payment gateway, the full order
state machine, and time-based delivery-tracking simulation, verified live through the browser: add
to cart → checkout → pay → confirmation → order history → a real tracking timeline that advances
on its own as you watch it. See §9 below. Phase 4 (Admin & Operations) is now also **end-to-end
functional** for its scoped-down core — RBAC-gated admin shell covering product/variant/inventory
management, order transitions and refunds, user/role management, coupon CRUD, and a dashboard
summary, verified live through the browser as an actual promoted admin user. See §10 below.
Phase 5 (Search, Recommendations & Discovery) is now also **end-to-end functional** for its
scoped-down core — real relevance-ranked search (MySQL, not Elasticsearch), autocomplete with
popular-query logging, zero-result handling, similar/frequently-bought-together/recently-viewed
recommendation rails, a working wishlist, back-in-stock alerts wired to a real restock trigger, and
newsletter signup — verified live through the browser. See §11 below. Phase 6 (Hardening) is now
substantially built out: a real backend + frontend automated test suite (spec §24 — 48 backend
pytest cases and 32 frontend vitest cases, all green) which **found and fixed a genuine oversell
bug** in checkout's stock-locking code (§12); security headers, an in-process rate limiter, and a
dependency audit that fixed 4 vulnerable packages and a too-short JWT signing key (§13); sitemap.xml
/robots.txt, per-page meta/OG tags, and JSON-LD structured data (§13); an accessibility sweep that
found and fixed real heading-order and unlabeled-form-control issues across 15+ pages (§13); and a
Prometheus `/metrics` endpoint (§13). Product reviews & moderation (spec §8.3, §9.7) are now also
**end-to-end functional** — verified-purchase-gated review submission, a pending →
approved/rejected/hidden moderation queue, and live rating-aggregate recompute on the PDP, verified
live through the browser. See §14 below. A **git repository now exists** (one commit) with a
working GitHub Actions CI pipeline (backend: ruff/pytest+coverage/alembic-from-scratch gate;
frontend: tsc/oxlint/vitest/build) — building it from scratch surfaced and fixed three real,
previously-undetected migration bugs (the baseline migration only ever created one of seven
catalogue tables). See §15 below. Load/security-scanning and deployment/DR remain unstarted.
Running **natively on Windows** — no
Docker/Redis/Celery/Elasticsearch (see §5/§6 below for why and what that changes).

---

## Section-by-section status vs spec.MD

| § | Section | Status | Notes |
|---|---|---|---|
| 1–3 | Exec summary, goals, personas/RBAC | 🟡 | RBAC now fully wired end-to-end — roles/permissions/matrix (§3.2/§3.3) seeded, enforced via a `require(*perms)` dependency, and manageable through an admin UI (§10 below); no `perm_ver`/Redis cache so a role change only takes effect on the user's next login/refresh |
| 4 | System architecture | 🟡 | Layering (`api → service → repository → model`) followed for catalogue + auth + admin; no Nginx/UoW/event bus yet |
| 5 | Technology stack | 🟡 | See "Stack deviations" below — several infra pieces substituted or deferred |
| 6 | Environments & config | 🟡 | `Settings` (pydantic-settings) implemented, fails fast pattern in place; only `local` env exists |
| 7 | Dataset ingestion pipeline | 🟡 | Real dataset ingested with real cleaning rules, condensed into 1 script instead of 9 CLI stages — full details in §7 below |
| 8 | Database design | 🟡 | Catalogue (§8.3) + auth/identity + commerce tables (carts, addresses, orders, payments, shipments, coupons — §9) + admin tables (`inventory_movements`, `refunds` — §10 below) + `reviews` (§14 below) built; CMS/support tables not created |
| 9 | Domain model & business rules | 🟡 | Pricing, cart, inventory (row-locked, now with an append-only movement ledger — §10 below), order state machine, coupon validation chain, review eligibility/moderation rules (§9.7 — §14 below) all implemented; shipping is flat-rate not zone-based |
| 10 | API design | 🟡 | Conventions followed (envelope, error codes, pagination shape) for catalogue + auth + cart/checkout/orders + admin endpoints |
| 11 | Authentication & session management | ✅ | Backend built end-to-end against spec's `/api/v1/auth/*` contract (§10.8) — see §8 below. MFA endpoints and admin API keys not built |
| 12 | Simulated payment gateway | 🟡 | Deterministic test cards + COD implemented synchronously (§9 below); wallet OTP methods (bKash/Nagad/Rocket/UPI), 3DS challenge step, and async webhook/Celery retry chain not built |
| 13 | Order fulfilment & delivery simulation | 🟡 | Full T+0..T+34h shipment timeline simulated and lazily reconciled against wall-clock time (§9 below); admin can now manually transition/refund orders (§10 below), but there's no ops queue/pick-list UI (§13.3) |
| 14 | Search & discovery | 🟡 | Real relevance-ranked search, autocomplete, zero-result fallback, recommendation rails, wishlist, recently-viewed, back-in-stock alerts, newsletter all built against a MySQL backend instead of Elasticsearch — full details in §11 below |
| 15–16 | Caching, background jobs | ⬜ | Not started — no Redis/Celery |
| 17 | Frontend architecture | 🟡 | Route map, data layer, component org followed for storefront + auth + cart/checkout/order pages |
| 18 | Design system | ✅ | Tokens, typography scale, spacing/motion, component standards implemented as specified |
| 19 | Responsive & accessibility | 🟡 | Breakpoints, touch targets, focus rings, reduced-motion in place; an axe-core sweep across 15+ pages found and fixed real heading-order and unlabeled-form-control issues (§13 below) — not a full WCAG audit |
| 20 | SEO & structured data | 🟡 | sitemap.xml, robots.txt, per-page meta/OG tags, JSON-LD (Product/BreadcrumbList/Organization/WebSite/ItemList) — §13 below. No hreflang, no redirects table, no CI structured-data linting |
| 21 | Observability | 🟡 | Structured logging (§1) plus a Prometheus `/metrics` endpoint (§13 below) exposing request rate/latency/status out of the box; no OpenTelemetry tracing, no Grafana dashboards/alerts — needs a collector/Grafana this setup doesn't have |
| 22 | Security | 🟡 | Auth/IDOR/CSRF test suite (§12); security headers, an in-process rate limiter with 429+Retry-After, and a dependency audit (4 packages upgraded, 1 fail-fast fix) — §13 below. No audit logging, no file-upload pipeline (no uploads exist yet), no gitleaks/SBOM/pip-audit/npm-audit wired into CI yet (§15) |
| 23 | Performance budgets | ⬜ | Not started |
| 24 | Testing strategy | 🟡 | Real pytest (backend, 59 cases) + vitest (frontend, 32 cases) suites now exist covering the spec's flagged critical scenarios — full details in §12/§14 below; no Playwright E2E, load testing, or contract testing |
| 25–26 | CI/CD, deployment | 🟡 | Git repo initialized, GitHub Actions CI running ruff/pytest+coverage/alembic-from-scratch (backend) and tsc/oxlint/vitest/build (frontend) — §15 below. No CD/deployment pipeline, no remote pushed yet, branch protection needs manual GitHub setup (guidance in README) |
| 27 | Repository structure | 🟡 | Backend/frontend layout matches; `.github/workflows/` now exists (§15); no `docker/`, `nginx/`, `infra/` yet |
| 28–31 | Feature flags, roadmap, risks, appendices | ⬜ | Reference material, not implementation |

---

## 1. Backend foundations (spec §4, §6, §10) ✅

Built in `backend/app/`:

- **`core/config.py`** — `Settings` (pydantic-settings), reads `.env` from the repo root via an
  absolute path computed from `__file__` (robust regardless of process cwd). Fails fast: raises if
  `APP_SECRET_KEY` is still the dev default in production.
- **`core/logging.py`** — `structlog`, JSON renderer in production / console renderer in dev, with a
  redaction processor that masks a fixed set of sensitive keys (passwords, tokens, etc.) before they
  ever hit a log line.
- **`core/errors.py`** — exception hierarchy (`AppError` and subclasses: `NotFoundError`,
  `ConflictError`, `ForbiddenError`, `UnauthorizedError`, `RateLimitedError`,
  `DependencyUnavailableError`) plus FastAPI exception handlers that convert all of them —
  including unhandled `Exception` and Pydantic validation errors — into the standard error envelope
  from spec §10.5 (`{"error": {"code", "message", "details", "request_id"}}`).
- **`middleware/request_id.py`** — accepts or generates `X-Request-ID`, binds it into structlog's
  contextvars for the duration of the request, echoes it back in the response header.
- **`middleware/response_envelope.py`** — wraps successful JSON responses in `{"data", "meta"}`
  (spec §10.2). Collection endpoints that already return `{"data", "meta", "facets"}` are detected
  and passed through with `meta.request_id`/`timestamp` filled in rather than double-wrapped.
- **`api/v1/operational.py`** — `/healthz` (liveness, no dependency checks), `/readyz` (checks DB
  connectivity via `SELECT 1`), `/version` (git SHA, computed once at import).
- **`main.py`** — wires it all together; CORS restricted to `cors_origin_list` from `Settings`.

**How it was verified**: started uvicorn, curled `/healthz` and `/readyz`, confirmed the JSON shape
matched spec exactly.

---

## 2. Database & catalogue schema (spec §8.3) ✅

- **`db/base.py`** — `Base` declarative class, `TimestampMixin` (`created_at`/`updated_at` with
  server defaults), `SoftDeleteMixin` (`deleted_at`).
- **`db/session.py`** — async SQLAlchemy engine (`aiomysql` driver — see stack deviations), pooled,
  `pool_pre_ping=True`.
- **`models/catalog.py`** — `Brand`, `Category` (self-referencing, materialised `path` column per
  spec §8.3 for O(1) subtree queries), `Product`, `ProductVariant`, `ProductImage`,
  `ProductAttribute`. Includes the spec's `CHECK` constraints (`stock >= reserved`,
  `price >= 0`, etc.) and the generated `discount_percent` as a Python property (matches the spirit
  of the spec's `GENERATED ALWAYS AS` column).
- **Alembic**: initialised (`alembic init`), `env.py` patched to pull the DB URL from `Settings`
  and autogenerate against `Base.metadata`. One baseline migration
  (`8ec51962b1e8_baseline_catalogue_schema` → later `3b87e7cbe117` after a fix) creates all six
  tables. `alembic upgrade head` applied cleanly against a local MySQL 8.0.44 instance.

**Real bug fixed here**: the first migration attempt failed with
`Invalid default value for 'created_at'` because `ProductImage.created_at` used
`server_default="CURRENT_TIMESTAMP"` as a Python string literal (SQLAlchemy quoted it) instead of
`func.now()`. Fixed, migration regenerated, applied cleanly.

---

## 3. Real data ingestion (spec §7) 🟡

### What the spec asks for vs what was built

Spec §7.2 specifies 9 separate CLI stages (`fetch`, `profile`, `clean`, `normalise`, `enrich`,
`media`, `load`, `index`, `verify`). What's built is **one script**,
`backend/scripts/ingest_flipkart.py`, that does clean → normalise → enrich → load in a single pass.
`profile`, `media` (image transcoding to WebP/AVIF), and `index` (Elasticsearch) are not implemented.

### How the source data was obtained

The user provided a Kaggle API key (`kaggle_api_key` in `.env`). Kaggle's classic dataset-download
endpoint accepts it as an HTTP **Bearer token** (confirmed by testing — no separate username needed
with this newer token format):

```bash
curl -H "Authorization: Bearer $KAGGLE_KEY" \
  "https://www.kaggle.com/api/v1/datasets/download/aaditshukla/flipkart-fasion-products-dataset" \
  -o flipkart_fashion_products_dataset.zip
```

Downloaded ~15.7 MB zip → `data/raw/flipkart_fashion_products_dataset.json` (82 MB, 30,000 records).
This matches the exact field list in spec §7.1 (`_id, actual_price, average_rating, brand, category,
crawled_at, description, discount, images, out_of_stock, pid, product_details, seller,
selling_price, sub_category, title, url`).

### What the raw data actually looks like (profiled before writing cleaning code)

- 30,000 records, 28,080 unique `pid`s (spec-anticipated duplicate-key issue, confirmed real).
- Prices as strings with commas (`"2,999"`) — needed stripping before `Decimal()` conversion.
- `product_details` as a list of single-key dicts (`[{"Fabric": "Cotton"}, {"Fit": "Slim"}]`) —
  needed flattening.
- **~93% of titles/attributes resolve to menswear** — this dataset is heavily skewed, not a balanced
  catalogue. Confirmed via both title-regex inference and the structured `Ideal For` attribute
  (18,455 of 18,489 non-null values were exactly `"Men"`).
- ~2,068 records have no brand; ~325 distinct brand strings are truncated at the source
  (`"REEB"`, `"Pu"`, `"ECKO Unl"`, `"True Bl"`) — verified this is how the raw JSON actually reads,
  not something introduced by processing.
- ~40% of records (11,980 / 30,000) have an empty `description` field, but usually still have
  `product_details` attributes.
- No variant, stock, rating-count, or sold-count fields at all — spec §7.3 explicitly anticipates
  this and says stock should be randomised in a seeded range since "the dataset has none."

### Cleaning rules implemented (spec §7.3), in `clean_record()`

| Field | Rule applied |
|---|---|
| `title` | `html.unescape`, whitespace collapse, title-case only if fully upper/lower, truncate 255 |
| `actual_price`/`selling_price` | Strip non-digit/non-dot chars → `Decimal`; unparseable → quarantined |
| Price sanity | If `selling_price > actual_price`, swap; if either ≤ 0, quarantined |
| `average_rating` | Parsed to `Decimal`, clamped to [0, 5], invalid → `NULL` |
| `brand` | Trimmed, whitespace-collapsed, empty → `"Unbranded"`. **No fuzzy merge** (spec allows rapidfuzz ≥92 fuzzy matching; not implemented — see gaps) |
| `images` | Deduped preserving order, empty → quarantined, URLs upgraded from the dataset's 128×128 thumbnail to 832×832 (`/image/128/128/` → `/image/832/832/` in the Flipkart CDN path) |
| `product_details` | Flattened list-of-single-key-dicts into a `dict`; an allowlist (`Fabric→material`, `Pattern`, `Fit`, `Sleeve`, `Type`, `Neck Type`, `Country of Origin`, `Sales Package`) becomes `product_attributes` rows |
| `category`/`sub_category` | Mapped via a hand-built `CATEGORY_MAP` from the 24 observed `(category, sub_category)` pairs into a leaf slug/name; unmapped → keyword fallback (bag/wallet/belt → Accessories, "footwear" → Footwear) → `"Uncategorised"` |
| `out_of_stock` | → `stock = 0` for every variant |
| Stock (in-stock items) | Randomised 0–60 per variant, **deterministically seeded from `pid`** (`random.Random(hash(pid))`) so re-running the script is reproducible |
| Duplicates | Deduped on `(brand.lower(), title.lower())`, keeping whichever record has more attributes + images (spec §7.3's exact rule) |

### Description — made mandatory (user requirement, 2026-07-23)

The user flagged missing descriptions as a blocker for a future recommendation engine. Fix in
`synthesize_description()`: when the source `description` is empty, one is composed from the real
parsed attributes — e.g. *"Typography Men Round Neck Grey T-Shirt (Pack of 3) by REF for men. Made
from cotton blend with a typography pattern. Regular, half sleeve, round neck. Part of the Topwear
range."* Every clause is conditional on the attribute actually being present; nothing is invented.
Result: **0 of 8,103 loaded products have a null/empty description** (verified with a `SUM(description
IS NULL OR description='')` query after load).

### Category population threshold — added on user request

Initial ingestion produced 5 gender-based top categories: Men (7,935), Unisex (168), Women (25),
Boys (6), Girls (2). The user asked to remove categories without enough data rather than ship
half-empty sections (and pointed out "Kids" had zero products — correct: it never existed as a
category at all, only the sparse `boys`/`girls` tokens did). Added `MIN_CATEGORY_PRODUCTS = 50`;
any gender bucket under that threshold has its products **quarantined** (reason
`category_too_small`), not silently reassigned. Final result: **2 top categories, Men and Unisex,
8,103 products** — an honest reflection of what the source data actually supports.

### Category tile images

After load, two `UPDATE ... JOIN` SQL statements backfill `categories.image_url`: first each leaf
category gets `ANY_VALUE(thumbnail_url)` from one of its real products, then each top category
inherits one from a child leaf. This replaced the placeholder `picsum.photos` images originally used
for the (since-removed) home page category tiles.

### Quarantine & rejection reporting (spec §7.5)

Every rejected record is written to `data/quarantine/ingest_<timestamp>.jsonl` with a `reason` field
(`missing_title`, `unparseable_price`, `non_positive_price`, `no_images`, `category_too_small`).
Script prints a summary and exits non-zero if the rejection rate exceeds `REJECTION_THRESHOLD = 15%`
(raised from the spec's stated 5% default because this real-world source is noisier than a curated
feed — documented in the script's docstring).

### Load mechanics — a real engineering problem worth recording

MySQL doesn't support `RETURNING`, so bulk `INSERT ... executemany` doesn't hand back generated
PKs for child rows (variants/images/attributes need `product_id`). Solved by relying on documented
MySQL behaviour: `cursor.lastrowid` after a multi-row `INSERT` returns the **first** row's
auto-increment id, and — since this is a single-threaded batch load with no concurrent writers —
subsequent rows are sequential. So each batch computes `product_ids = [first_id + i for i in
range(len(batch))]` and uses that to build the child rows in the same transaction. Batches of 1,000
products; full run (8,103 products + ~38k images + ~43k attributes + ~49k variants) completes in
**~5 seconds**.

### Bugs hit and fixed during ingestion (chronological)

1. **Duplicate brand name under case-insensitive collation** — `brands.name` is unique under
   `utf8mb4_0900_ai_ci` (case-insensitive), but the Python dedup was case-sensitive, so `"Inspi"`
   and a differently-cased variant collided at the DB level. Fixed by deduping brands on
   `name.lower()` and keying the `brand_id` lookup the same way.
2. **`Data too long for column 'base_color'`** — some `Color` attribute values (e.g.
   `"Dark Blue, White"`) combined with the column's `VARCHAR(40)` limit. Fixed by truncating to 40
   chars during cleaning.
3. **`Data too long for column 'seo_description'`** — `f"Buy {title} online."` could exceed the
   `VARCHAR(255)` limit when `title` was near its own 255-char cap. Fixed by truncating the
   composed string, not just the title.

Each was caught by actually running the script against the real 30k-record file, not by inspection —
worth noting because the synthetic seed script (168 hand-generated products) never exercised any of
these paths.

---

## 4. Public catalogue API (spec §10.8, subset) ✅

`GET /api/v1/products` (filter by `category`, `brand`, `price_min/max`, `gender`, `q`, `sort`;
offset pagination; brand facet counts), `GET /api/v1/products/{slug}`, `GET /api/v1/categories`,
`GET /api/v1/categories/{slug}`, `GET /api/v1/brands`.

**Real bug fixed**: category filtering originally did `Category.slug == category_slug`, an exact
match. Since products are only ever linked to *leaf* categories (e.g. `men-tshirts`) but the storefront
nav links to *top-level* categories (e.g. `men`), `/c/men` returned zero results. Fixed using the
materialised `path` column exactly as spec §8.3 prescribes it for this purpose:
`Category.path == top_path OR Category.path LIKE '{top_path}/%'` — a subtree match instead of an
exact match. Verified: `/products?category=men` went from 0 → 70 (synthetic data) → correctly
scoped once real data replaced it.

---

## 5. Frontend (spec §17, §18) ✅ for the storefront read path

Vite + React 19 + TypeScript (strict) + Tailwind v4 + React Query + React Router 7 + Zustand
(installed, not yet used — no client-only state exists yet) + Axios + React Hot Toast.

- **`styles/tokens.css`** — every CSS variable from spec §18.1 (surfaces, text, borders, accent,
  semantic colours, effects, radii) transcribed exactly, mapped into Tailwind's `@theme` layer.
  Typography scale, spacing, and motion tokens from §18.2/18.3 implemented as Tailwind utilities
  (`text-display`, `text-price`, `container-page`). Self-hosted variable Inter font via
  `@fontsource-variable/inter` (spec asks for self-hosted, preloaded, variable font).
- **Components**: `Button` (4 variants, loading state that preserves width via absolute-positioned
  spinner so it doesn't reflow — spec §18.4's explicit requirement), `ProductCard` (3:4 image, 2-line
  title clamp, struck-through MRP, keyboard-reachable quick-add and wishlist toggle — not
  hover-only), `RatingStars`, `Skeleton`/`ProductCardSkeleton` (matches final layout dimensions),
  `EmptyState`/`ErrorState`, `FilterSidebar`.
- **Pages**: Home (hero, trending rail), Catalog/PLP (`/c/:categorySlug`, filters + sort in the URL
  query string per spec §17.1's "URL is the source of truth" rule, brand facet checkboxes,
  pagination), Product/PDP (`/p/:productSlug`, colour/size selection, description, attributes).
- **Data layer**: single `apiClient` (Axios) with an `X-Request-ID` interceptor; React Query with
  the spec's key convention (`['products', 'list', filters]`, `['products', 'detail', slug]`);
  `staleTime: 5min` for catalogue queries.
- **Accessibility**: skip-to-content link, visible focus rings via `:focus-visible`, `prefers-reduced-
  motion` handling in the base stylesheet, 44px minimum touch targets on interactive controls,
  `aria-pressed`/`aria-label` on toggle buttons.

**Verified in-browser** (via the Chrome automation tool, not just typecheck) at every stage: home
page render, category navigation, product card grid, PDP variant selection, mobile-width grid
behaviour, back-button navigation — screenshotted and inspected, not assumed from code review.

### UI fixes made after initial build (user-requested, 2026-07-23)

1. **Dynamic nav/footer/home tiles** — originally hardcoded `Men`/`Women`/`Kids` links. Once the
   category-threshold fix dropped Women/Kids from the data, these went dead. Replaced with
   `useQuery(['categories'], listCategories)` in `Header`, `Footer`, and `HomePage`, filtered to
   `depth === 0`, so the UI can never again drift out of sync with what the database actually has.
2. **Removed redundant home page category tiles** — they duplicated the top nav one scroll down;
   removed the whole section.
3. **Reduced image footprint** — `ProductGrid` column breakpoints changed from
   `2/2/3/4` to `2/3/4/6` (more, smaller cards on wide screens); PDP hero image capped at
   `max-w-sm` (~384px) instead of taking a full 50%-width column via
   `md:grid-cols-[minmax(0,420px)_1fr]`.
4. **Back button on PDP** — `useNavigate(-1)` wired to a button next to the breadcrumb.
5. **Complete grid rows on the home page** — the Trending rail originally fetched 8 products against
   column counts of 2/3/4/5/6, which doesn't divide evenly into any of those past 2 and 4, leaving a
   half-empty last row at most breakpoints. Fixed two ways at once: dropped the 5-column breakpoint
   (columns are now 2/3/4/6, all divisors of 12) and changed `per_page` to 12. Every breakpoint now
   renders whole rows only (6/4/3/2 full rows respectively) — verified at both a narrow and wide
   viewport.

---

## 6. Sub-category navigation (better UX, user-requested) ✅

The Men category was one flat 7,935-product grid with no way to narrow to just Topwear, Footwear,
etc. — brand facets existed but category itself wasn't filterable beyond top-level. Fixed with a
drill-down chip bar rather than just adding category to the existing checkbox sidebar, since
category is a primary navigation axis (one active choice at a time), unlike brand (multi-select
refinement).

**Backend** — `ProductRepository.category_facets()` in `repositories/catalog.py`: given the current
category slug, returns its **children** (drill-down — e.g. on `/c/men` you see Topwear, Bottomwear,
Footwear, …); if the current category is a leaf with no children, it instead returns its
**siblings** (children of its parent) with itself flagged `is_active=True`, so a leaf page
(`/c/men-footwear`) still shows the full sibling set for lateral navigation instead of being a dead
end. Counts are real per-category `COUNT(*)` on active products, and categories with zero matching
products are dropped from the list entirely. Exposed as a new `facets.categories` array on
`GET /api/v1/products`, alongside the existing `facets.brands`.

**Frontend** — new `components/filters/CategoryChips.tsx`: a horizontal scrollable pill bar
(`Link`s, not buttons — real navigation, not client-side-only filtering) rendered in `CatalogPage`
between the page header and the brand sidebar. Active chip styled solid white/black; inactive chips
show name + count. `CatalogPage` also gained a `useEffect` resetting `page` to 1 when
`categorySlug` changes — needed because React Router reuses the component instance across param
changes on the same route pattern, so the old page number would otherwise persist into a
differently-sized category and could point past the end.

**Verified in-browser**: `/c/men` shows 13 real sub-category chips with correct counts (Topwear
4,763 … Raincoats 12); clicking "Footwear" navigates to `/c/men-footwear`, correctly shows 229
products, narrows the brand sidebar to just the 3 brands that actually sell footwear, highlights
the active chip, and keeps sibling chips visible for direct lateral navigation. Same verified on the
smaller Unisex category (Accessories 167, Footwear 1).

---

## 7. Auth frontend — Login/Register/Account UI (spec §11, §17.1) 🟡 frontend-only

Scoped deliberately as **frontend-only** for this session (user chose this over starting the Phase 2
auth backend or polishing existing storefront pages). Every page is wired to the exact endpoint
paths/payloads in spec §10.8's auth endpoint catalogue, so connecting a real backend later is a
service-layer change, not a rewrite.

**Pages built** (`frontend/src/pages/auth/`, `frontend/src/pages/account/`), all following spec
§17.1's route map exactly (`/auth/login`, `/auth/register`, `/auth/forgot`, `/auth/reset/:token`,
`/auth/verify` + `/auth/verify/:token`, `/account`):

- **LoginPage** — email/password, remember-me, forgot-password link, redirects to `?next=` (or
  `/account`) on success.
- **RegisterPage** — first/last name, email, password + confirm, live password-strength meter, terms
  + marketing-opt-in checkboxes; redirects to `/auth/verify?email=` on success.
- **ForgotPasswordPage** — always shows a neutral "check your email" success state regardless of
  whether the account exists, matching spec §10.8's explicit no-enumeration requirement for
  `POST /password/forgot`.
- **ResetPasswordPage** — reads `:token` from the path (not a query param, per spec's route map),
  new password + confirm, strength meter.
- **VerifyEmailPage** — dual-purpose: with `:token` in the path it auto-verifies on mount; without
  one (post-registration landing) it shows "check your inbox" with a rate-limited resend (60s
  cooldown, matching the spirit of spec §10.7's resend rate limit).
- **AccountPage** — profile summary, sessions/devices list (spec §5.1 "sessions/devices UI") with
  per-device revoke and "sign out everywhere", protected by a `ProtectedRoute` wrapper that redirects
  unauthenticated visitors to `/auth/login?next=...`.

**Supporting infrastructure**:

- `services/auth.ts` — one function per §10.8 endpoint (`registerAccount`, `login`, `logout`,
  `logoutAll`, `getCurrentUser`, `verifyEmail`, `resendVerification`, `forgotPassword`,
  `resetPassword`, `listSessions`, `revokeSession`), all snake_case payloads per spec §10.1.
- `hooks/useAuth.ts` — `useCurrentUser()`, a React Query wrapper around `GET /auth/me` (`['auth',
  'me']`), the single source of truth for auth state app-wide, per spec §17.2's rule that server
  state lives in React Query, never duplicated into Zustand.
- New UI primitives in `components/ui/`: `Input`, `PasswordInput` (show/hide toggle, 44px target),
  `Checkbox`, `FormAlert` (danger/success/info, correct `role="alert"` vs `role="status"` per tone).
- `components/auth/PasswordStrengthMeter.tsx` — a lightweight client-side heuristic (length + case +
  digit + symbol variety, 5-segment score) since zxcvbn isn't in the frontend dependency table (spec
  §11.3 only mandates it server-side); explicitly advisory, mirroring the spec's own framing.
- Installed `react-hook-form` + `@hookform/resolvers` (spec §5.1 lists react-hook-form; wasn't
  installed yet). All forms use zod schemas via `zodResolver`.
- `Header.tsx` now reads `useCurrentUser()` to point the account icon at `/account` when
  authenticated or `/auth/login?next=%2Faccount` otherwise, instead of always linking to `/account`.

**Backend gap, handled explicitly**: since no `/api/v1/auth/*` routes exist yet, `getCurrentUser()`
treats both `401` and `404` as "guest" (returns `null` instead of throwing) — the 404 branch is a
deliberate, commented shim for the current no-backend state and should be removed once Phase 2 auth
lands and starts returning real `401`s.

**Real bug found and fixed during in-browser verification**: `VerifyEmailPage`'s auto-verify-on-mount
flow (calling `useMutation().mutate()` from inside a `useEffect`) got permanently stuck showing
"Verifying your email" — the mutation's promise settled (confirmed via network tab, backend replied
404 in ~2ms) but the component never re-rendered into the success/error branch. The *same* mutation
pattern triggered by a button click (the resend flow, on the same page) worked fine, isolating the
bug to the effect-on-mount + React 19 StrictMode dev double-invoke interaction specifically. Fixed by
not routing the auto-verify call through `useMutation` at all — it now calls the plain
`verifyEmail(token)` service function directly inside the effect and tracks pending/success/error via
local `useState`, sidestepping the observer-lifecycle interaction entirely. The click-triggered resend
mutation was left on `useMutation` since it isn't affected. Verified by reloading `/auth/verify/:token`
against the live (routeless) backend and watching it settle into "Verification failed" instead of
hanging.

**Verified in-browser** (Chrome automation, full flows, not just typecheck): empty-form validation
with auto-focus on the first invalid field, password show/hide toggle, live password-strength meter
reacting to input, real submit-error rendering (`FormAlert` showing the backend's actual error body),
`/account` correctly redirecting an unauthenticated visit to
`/auth/login?next=%2Faccount`, and all five auth pages rendering pixel-consistent with the existing
monochrome design system. `tsc -b` and `oxlint` both clean.

**Known gap**: no backend to actually authenticate against yet — every mutation will surface a real
`404`/error-envelope-shaped message until Phase 2's `/api/v1/auth/*` routes are built. That's the
logical next step.

---

## 8. Phase 2 auth backend (spec §8.3, §11, §10.8) ✅

Built in `backend/app/`, matching the layering already established by the catalogue module
(`api → service → repository → model`):

- **`models/auth.py`** — `User`, `Role`, `Permission` (+ `role_permissions` join table), `UserRole`
  (explicit mapped class, not a bare secondary table, since it carries `granted_by`/`granted_at`),
  `RefreshToken`, `EmailVerificationToken`, `PasswordResetToken`, `LoginAttempt`. Trimmed from spec
  §8.3's full `users` table to what Phase 2 actually uses — `phone`/`phone_verified_at` and
  `mfa_secret`/`mfa_recovery_codes` omitted since no phone or MFA endpoints exist yet (documented
  deviation, not an oversight).
- **`core/security.py`** — Argon2id hashing (`time_cost=3, memory_cost=64MB, parallelism=4`, exactly
  spec §11.3's parameters) with rehash-on-login; a constant-time-ish `verify_password` that always
  runs a real hash comparison (against a precomputed dummy hash when the user doesn't exist) so
  "unknown email" and "wrong password" take the same code path and time, per spec §11.4; password
  policy (12–128 chars, 3-of-4 character classes, common-password/name blocklist); JWT
  encode/decode (HS256, `sub`/`sid`/`roles`/`perms`/`iat`/`exp`/`jti`/`iss`/`aud` claims — `perm_ver`
  omitted, see gaps); opaque-token generation/hashing for refresh/verification/reset tokens.
- **`core/cookies.py`** — `access_token` (HttpOnly, Lax, 15 min), `refresh_token` (HttpOnly, Strict,
  scoped to `/api/v1/auth`, 14 days), `csrf_token` (readable, Lax) exactly per spec §11.1.
  `cookie_secure` is `False` outside `production` so cookies still work over plain `http://localhost`
  in dev (spec assumes `Secure` always; deviated and documented, same spirit as the existing
  Windows-native deviations).
- **`core/mail.py`** — a `MailBackend` Protocol abstracted the same way as spec §12.1's
  `PaymentProvider`, with only a `ConsoleMailBackend` implemented (structlog-logs the verification/
  reset link) since there's no SMTP/MailHog in this native setup. This is how the flows were actually
  tested — reading the link out of the server log and curling it, no real inbox involved.
- **`repositories/auth.py`** — `UserRepository` (incl. `get_roles_and_permissions`, joining
  `user_roles → roles → role_permissions → permissions`), `RefreshTokenRepository` (rotate/revoke/
  revoke-family/revoke-all), `OneTimeTokenRepository` (one generic class instantiated for both
  `EmailVerificationToken` and `PasswordResetToken` — identical create/consume shape, spec's own two
  tables are structurally identical), `LoginAttemptRepository`.
- **`services/auth/auth_service.py`** — `register`, `verify_email`, `resend_verification`, `login`,
  `refresh`, `logout`, `logout_all`, `forgot_password`, `reset_password`, `get_user_out`,
  `list_sessions`, `revoke_session`. Progressive lockout (spec §11.4) keyed on `(email_hash, ip)` via
  two `login_attempts` window counts (5/15min, 10/1hr) — DB-based since there's no Redis, but the
  exact keying spec calls for (so an attacker guessing from a different IP can't lock out the victim).
  Refresh rotation: every refresh revokes the presented token and issues a new one on the same
  `family_id`; presenting a token whose `revoked_reason == "rotated"` again is treated as a
  compromise — the whole family is revoked and a `session_reuse_detected` event is logged (spec
  §11.2). Revocations for mundane reasons (logout, logout-all, password reset) do *not* trigger that
  escalation — see "real bug" below for why that distinction matters.
- **`api/v1/auth/router.py`** + **`api/deps.py`** — all 12 endpoints from spec §10.8's auth catalogue
  except MFA and admin-API-key ones (register, login, logout, logout-all, refresh, email/verify,
  email/resend, password/forgot, password/reset, me, sessions, sessions/{id} DELETE). `get_current_user`
  reads/verifies the `access_token` cookie; `verify_csrf` enforces the double-submit pattern on every
  cookie-authenticated mutating endpoint (logout, logout-all, session revoke).
- **`scripts/seed_rbac.py`** — seeds the 6 personas from spec §3.2 and 17 permissions + the full
  role→permission matrix from spec §3.3, idempotently. Every new registrant is auto-assigned the
  `customer` role in `AuthService.register`.
- **Migration** `2e5206dc7f03_auth_identity_schema` — autogenerated, then hand-fixed (see bug #1
  below); `alembic upgrade head` → `downgrade -1` → `upgrade head` all verified clean, and
  `alembic check` reports no drift against the models (spec §8.4's CI gate).

### Real bugs found and fixed (all caught by actually exercising the flows, not by inspection)

1. **Alembic downgrade failed on MySQL**: the autogenerated `downgrade()` explicitly dropped
   `ix_refresh_tokens_user` (and the equivalent indexes on `email_verification_tokens`/
   `password_reset_tokens`) before dropping their tables — but MySQL refuses to drop an index that's
   still backing a live FK constraint (`Cannot drop index ... needed in a foreign key constraint`).
   First attempt at the down→up cycle left the DB in a half-downgraded state (two tables silently
   gone) while `alembic_version` still claimed `head` — a real "trust but verify" moment; fixed by
   removing those specific explicit drops (the subsequent `drop_table` removes the index for free)
   and manually restoring the DB to a clean baseline before re-verifying the full cycle.
2. **`AmbiguousForeignKeysError` on `User.user_roles`**: `user_roles` has two FKs to `users`
   (`user_id` and `granted_by`), so SQLAlchemy couldn't infer which one backs the relationship.
   Fixed with an explicit `foreign_keys="UserRole.user_id"` on the `User.user_roles` side (the
   `UserRole.user` side already had it; the relationship needs it on *both* ends here).
3. **`MissingGreenlet` in the RBAC seed script**: touching `role.permissions` on a role that had
   just been `flush()`ed (transient → persistent) triggered an implicit lazy-load, which isn't legal
   under async SQLAlchemy outside an awaited context. Fixed by assigning the permission list at
   construction time (`Role(..., permissions=list(wanted))`) while the object is still transient —
   a pure in-memory operation — instead of appending to it after the object becomes persistent.
4. **`TypeError: can't compare offset-naive and offset-aware datetimes`** in `refresh()`: MySQL's
   `DATETIME` has no timezone-aware variant (unlike Postgres), so every datetime SQLAlchemy reads
   back is naive regardless of the model declaring `DateTime(timezone=True)` — comparing a freshly
   read `token.expires_at` against `datetime.now(UTC)` crashed. Fixed by stripping tzinfo off the
   comparison side; every stored timestamp is UTC wall-clock by convention so the values are still
   correctly comparable once both are naive.
5. **Cookies silently dropped by `ResponseEnvelopeMiddleware`**: the pre-existing middleware (from
   the Phase 0/1 session) rebuilt every JSON response via `headers=dict(response.headers)` — and a
   plain `dict` can't hold three separate `Set-Cookie` headers, so only the *last* one survived.
   Login "succeeded" but only `access_token` ever reached the browser; `refresh_token`/`csrf_token`
   were gone, which would have made session refresh and CSRF-protected logout silently broken for
   every future feature that sets cookies, not just auth. Caught via `curl -i` showing a single
   `set-cookie` line where three were expected. Fixed by copying `response.raw_headers` (which
   preserves duplicates) and mutating the new response's `raw_headers` **list in place** rather than
   rebinding the attribute — Starlette's `MutableHeaders` holds a reference to that exact list object,
   so a naive `new_response.raw_headers = [...]` would have desynced `.headers` (used by
   `RequestIDMiddleware` downstream) from what actually gets sent over the wire.
6. **Reuse-detection false-positive on intentional logout**: initially *any* revoked refresh token
   presented to `/refresh` was treated as reuse (family-wide revocation + scary "reuse detected"
   message) — including a token revoked by the user's own "Sign out" a moment earlier, which isn't a
   security event. Fixed by checking `revoked_reason == "rotated"` specifically; other revocations
   just return a plain "session is no longer valid."

### Frontend touch-up required to actually use this backend

The Phase 2 **frontend** (previous session) didn't attach a CSRF header at all, since no backend
existed to require one yet. Added a small interceptor to `frontend/src/services/apiClient.ts`: on
every non-GET request, read the `csrf_token` cookie and attach it as `X-CSRF-Token` — exactly what
spec §17.2 already specifies for the shared `apiClient` ("attach X-Request-ID and CSRF token"),
just not implemented until there was a backend to exercise it against.

### Verified live, browser-to-database, not just curl

`curl` first (register → read the verification link out of the console-logged mail backend →
verify → login → confirm all three cookies arrive → `/me` → `/sessions` → `/refresh` rotation →
reuse-of-old-token correctly rejected → `logout-all` correctly *not* flagged as reuse → CSRF-missing
logout correctly `403`s → CSRF-present logout `204`s → `forgot-password` returns identical `202` for
a real vs. unknown email → weak-password and duplicate-email registration correctly rejected →
5-failed-attempts lockout correctly `423`s even the *correct* password until it clears → password
reset invalidates the old password and all sessions). Then the same login → account page → sessions
list → sign-out loop again through the actual Chrome-driven frontend, confirming the UI built in the
prior session and the backend built in this one actually fit together (this is where the CSRF gap and
the cookie-dropping middleware bug were caught — neither was visible from curl alone in the way that
mattered, since curl testing happened before the CSRF interceptor existed).

### Known gaps / new since this session

- **MFA and admin API keys** (spec §10.8's `/mfa/*` endpoints, §11.5): not built — no frontend pages
  call them yet either, so scope matched what's actually usable.
- **`perm_ver` cache-busting** (spec §3.2's Redis-cached permission version): skipped, no Redis.
  Permissions are re-resolved by a fresh join query on every `/me`/login/refresh instead — correct
  today at this scale, would need revisiting under real load.
- **Rate limiting** (spec §10.7): not implemented (Redis-dependent); only DB-based progressive
  lockout exists. `POST /auth/register`, `/password/forgot`, etc. have no request-rate ceiling yet.
- **New-device email notifications** (spec §11.4) and the reuse-detected security email: both just
  `logger.warning`, no email actually sent — the mail backend exists but nothing wires a
  "SESSION_REUSE_DETECTED" event to it yet.
- Test credentials left in the dev DB for convenience: `ada@example.com` / `NewPass9!zQrT4x`
  (verified, `customer` role, no lingering lockout — login_attempts/refresh_tokens tables were
  cleared of test noise before finishing).

---

## 9. Phase 3 commerce — cart, checkout, payments, fulfilment (spec §8.3, §9, §12, §13) ✅

Built in one session, backend and frontend together, and deliberately scoped down from the full
spec (documented below) to a coherent, fully-working core loop rather than a wide, half-working
surface: **browse → add to cart (guest or signed-in) → apply coupon → checkout → pay (simulated) →
order confirmation → order history → a tracking timeline that visibly advances in real time.**

### Schema

New tables in `models/commerce.py`: `addresses`, `carts`, `cart_items`, `coupons`,
`coupon_redemptions`, `orders`, `order_items`, `order_status_history`, `payments`,
`payment_events`, `shipments`, `shipment_events`. One deliberate deviation from spec §8.1's "never
expose internal auto-increment ids" convention: addresses use the plain integer `id` rather than a
ULID `public_id`, since every address operation is ownership-scoped to the current user anyway
(unlike a truly public resource, guessing another user's address `id` gets you a 404, not their
address) — cart items and order line items follow the same reasoning. Migration
`e39d64c1a264_commerce_schema` — full `upgrade → downgrade → upgrade` cycle and `alembic check`
verified clean on the first attempt (the FK/index-drop-ordering bug from the auth migration was
caught proactively this time and fixed before ever applying it).

### Cart (`repositories/cart.py`, `services/cart_service.py`, `api/v1/cart/`)

- Guest carts via an HttpOnly `cart_session` cookie (real DB rows, not localStorage, so they
  survive a refresh — spec §9.3); signed-in carts resolved by `user_id`. `get_optional_user` (a
  new non-raising sibling to `get_current_user` in `api/deps.py`) lets the same endpoints serve
  both without duplicating routes.
- **Merge on login** (spec §9.3): wired directly into the `/auth/login` router — if a guest cart
  cookie is present, `CartService.merge_guest_into_user` unions by variant
  (`quantity = min(guest + user, 10, available)`) and clears the guest cookie. This is the one
  place cart code reaches into the auth flow; it's a router-level call, not a service-to-service
  import, keeping the module boundary spec §4.2 asks for.
- Every mutation (add/update/remove/apply-coupon) returns the **entire recalculated cart**, per
  spec §9.3 — no endpoint returns just the changed line.
- Prices are **always re-read live** from `product_variants.price` on every view; the
  `unit_price_snapshot` captured at add-time is kept only to show a "price changed" banner, never
  used for totals — matches spec §9.1's "snapshot is a UX device, never the authority" rule exactly.
- Coupon validation chain (spec §9.6, subset): exists → active → date window → global limit →
  per-user limit → min-order-amount → compute. Scope-matching (`applies_to` product/category/brand)
  and stackability are not implemented — coupons here are global, single-per-cart only.

### Checkout & orders (`services/order_service.py`, `api/v1/orders/`)

- **Collapsed the multi-resource checkout flow.** Spec §10.8 describes a persisted
  `checkout_session` resource (create → attach address → attach shipping method → `POST /orders`
  referencing it). Built instead: `POST /checkout/session` is a **stateless preview** (recomputes
  totals given an address + payment method, no DB row, no reservation window), and `POST /orders`
  is the one real transactional step — it re-validates and locks everything itself. Two endpoints
  is genuinely simpler than four and the safety property that actually matters (no oversell) lives
  entirely in the order-creation transaction, not in a separate reservation resource.
- **Stock safety** (spec §9.4): `POST /orders` takes `SELECT ... FOR UPDATE` on every distinct
  variant row, **ordered by id** (deadlock-free under concurrent checkouts touching overlapping
  variants), re-checks `available >= qty`, then decrements `stock` directly in the same
  transaction. No separate reserve/release phase — since payment confirmation is synchronous here
  (see below), reserve-then-commit would just be reserve-then-immediately-commit with extra steps.
- **Idempotency** (spec §10.6): `Idempotency-Key` header: replaying the same key returns the
  original order verbatim instead of creating a duplicate. Simple "check then create" — not
  airtight against a true concurrent double-submit race, documented as a gap below.
- **Coupon redemption**: locked via `SELECT ... FOR UPDATE` on the coupon row at order-creation
  time (separately from the cart-apply-time check), so two concurrent checkouts can't both redeem
  the last unit of a limited coupon.
- **Order numbers / transaction ids / tracking numbers**: `BC-YYYYMMDD-{ULID suffix}`,
  `TXN{ULID prefix}`, `BC{hex}` respectively — matching spec §12.6/§13.2's *shape* without their
  exact checksum/base32 schemes (documented simplification).

### Simulated payment (`core/payment.py`)

`PaymentProvider` Protocol + `SimulatedProvider`, isolated the same way spec §12.1 asks — a real
provider is an adapter swap. All of spec §12.3's deterministic test cards work exactly as
documented (`4242...4242` succeeds, `4000...0002` declines, `...9995` insufficient funds,
`...0069` expired, `...0119` gateway error); anything else is sampled at
`PAYMENT_SIMULATOR_SUCCESS_RATE`. Confirmation is **synchronous** — spec §12.5's async webhook
chain (HMAC-signed callback, `payment_events` row, exponential-backoff retries) needs Celery, which
isn't in this native-Windows stack; `payment_events` rows are still written, just from the
in-request code path instead of a real webhook POST. Only `card` and `cod` methods are implemented
— bKash/Nagad/Rocket/UPI's OTP-redirect flow and the 3DS-challenge test card are treated as
instant successes rather than building the extra confirmation round-trip.

### Order state machine & delivery simulation (spec §9.5, §13.1) — the interesting part

`ORDER_TRANSITIONS` is the single source of truth for legal transitions, exactly as spec §9.5
demands ("no ad-hoc `order.status = "shipped"` anywhere"). The delivery timeline runs without
Celery via a **lazy reconciliation** pattern: a `Shipment` and all six `shipment_events` (spec
§13.1's T+0/2h/8h/20h/30h/34h schedule) are created with real future timestamps, compressed by
`DELIVERY_SIMULATOR_MINUTES_PER_HOUR` (default 0.05 — the full 34-hour schedule plays out in
~1.7 real minutes, so a demo session can watch an order go from Confirmed to Delivered without
waiting). Every time an order is read (`GET /orders/{number}`, `/tracking`), `_reconcile()` compares
`now` against the stored event timestamps and advances `order.status` (and writes the matching
`order_status_history` row) if enough time has passed — no background worker needed, the "worker"
is just "did anyone look at this order recently."

A **two-minute pre-ship delay** (`PRE_SHIP_DELAY_MINUTES`, a fixed real-world value, *not* scaled by
the compression factor above) sits between `confirmed` and the shipment being created at all — this
was a deliberate second pass, not the first design (see bugs below): without it, a paid order would
jump straight to `shipped` inside the same request that created it, which per §9.5 makes customer
cancellation ("permitted only in pending_payment, confirmed, processing") permanently unreachable.

### Real bugs found and fixed (again, all by exercising the flows, not by inspection)

1. **`MissingGreenlet` on a brand-new cart's `.items`** — identical root cause to the RBAC-seed bug
   from Phase 2 (§8 above): touching a relationship collection on an object that's already been
   `flush()`ed triggers an illegal lazy-load under async SQLAlchemy. Fixed by passing `items=[]`
   explicitly to the `Cart(...)` constructor before it's ever added to the session, instead of
   letting the ORM default-initialise the collection after the object becomes persistent.
2. **Stale cart after adding an item** — `add_item()` correctly wrote the new `CartItem` to the DB,
   but the response showed the *old* cart contents. Cause: within one request/session, the cart
   object was already identity-mapped from an earlier query with its `.items` collection loaded
   (even if empty); SQLAlchemy's default behaviour is to leave an already-loaded relationship alone
   on a subsequent query unless told otherwise. Fixed with `execution_options(populate_existing=True)`
   on the post-mutation reload query — forces a real refresh instead of trusting the stale
   in-memory collection.
3. **Cancellation was unreachable** — the first version of `_ship_order` ran synchronously inside
   `create_order()`, so every successful payment jumped straight from `pending_payment` to
   `shipped` in one request. Since spec §9.5 only allows customer cancellation through
   `processing`, this made the cancel endpoint dead code — caught not by an error, but by *noticing*
   that a manual cancel-right-after-checkout test had nothing valid to act on. Fixed by moving the
   confirmed→processing→packed→shipped jump out of the request path and into `_reconcile()`,
   gated by `PRE_SHIP_DELAY_MINUTES`.
4. **Illegal `shipped → delivered` transition** — `_reconcile()` initially jumped straight to
   whatever the *latest* elapsed shipment event implied, so an order nobody had checked on for a
   few minutes (crossing both the `out_for_delivery` and `delivered` thresholds between views)
   tried to transition `shipped → delivered` directly and hit `ORDER_TRANSITIONS["shipped"] =
   {"out_for_delivery"}` — a `409 CONFLICT`, discovered as an order detail page stuck on a loading
   skeleton in the browser. Fixed by having `_reconcile()` step through `out_for_delivery` first
   and only transition to `delivered` on a subsequent (or the same) call once both edges have
   legitimately elapsed — the state machine's history now always records every intermediate hop,
   regardless of how long it's been since anyone last looked at the order.

### Known gaps / new since this session

- **Checkout session is stateless** (see above) — no server-held stock reservation window between
  "preview" and "place order." Safe today (the real lock happens at order creation), but doesn't
  match spec §10.8's `checkout_session_id` resource if something later depends on that identity.
- **Shipping is flat-rate + optional COD surcharge**, not spec §9.2's zone/weight-based engine — no
  delivery zones or variant weights are modelled.
- **Tax is a single flat `TAX_RATE_PERCENT`** (default 0), not per-`tax_class` rates from `settings`.
- **Idempotency-Key replay is "check then create"**, not airtight against a true concurrent
  double-submit (spec §10.6 implies a request-hash comparison and a `409 REQUEST_IN_PROGRESS` for
  in-flight duplicates — not implemented).
- **No PDF invoices/receipts** (WeasyPrint not installed) — spec §12.6's watermarked
  `SIMULATED — NOT A REAL PAYMENT` receipt doesn't exist yet.
- **Order list view doesn't reconcile** — only order detail/tracking pages trigger `_reconcile()`,
  so the history list can show a stale status (e.g. "Shipped" when it's actually "Delivered") until
  the order is opened once.
- **Returns are out of scope** — `RETURN_REQUESTED`/`RETURN_APPROVED`/`REFUNDED` exist in
  `ORDER_TRANSITIONS` but nothing drives an order into them; that's Phase 4 (admin) territory.
- Demo data left in the dev DB on purpose: 3 seeded coupons (`WELCOME10`, `FLAT100`, `FREESHIP` —
  admin coupon CRUD is Phase 4, so this script stands in for it) and 5 real orders on `ada@example.com`
  showing every terminal state (confirmed, shipped, delivered, cancelled, payment-failed) as a
  working showcase of the full lifecycle.

### Verified live, browser-to-database, not just curl

Full loop through the actual Chrome-driven frontend: product page → select variant → add to cart
(drawer opens, badge updates) → cart page → apply coupon (`WELCOME10` correctly rejected on reuse
per-user-limit, `FREESHIP` correctly applied) → checkout (address preselected to default, live
preview totals reacting to payment method) → place order with the `4242...4242` success card →
confirmation page → order detail → tracking timeline rendering real elapsed events → order history
listing every prior test order with correct status badges and totals. Also curl-verified
separately: stock decrement/release (success vs. declined-card vs. cancelled), coupon
`used_count` incrementing exactly once, idempotent replay returning the identical order, and the
full state progression (confirmed → [2 min] → shipped → [~2 min] → delivered) observed by polling
an order in the background while continuing other work.

---

## 10. Phase 4 admin & operations (spec §3.2/§3.3, §8.3, §29) ✅ for the scoped-down core

Built in one session, backend and frontend together, scoped down from the full spec admin surface
(CMS/banners, support tickets, bulk import/export, audit-log viewer, feature flags, search
reindex — all deferred, documented at the bottom) to the operational core: **product/variant/
inventory management, order operations (transition + refund), user & role management, coupon CRUD,
and a dashboard summary** — everything a real store operator needs day-to-day, gated by the RBAC
matrix that was seeded but unused in Phase 2.

### Authorization (`api/deps.py`)

A `require(*permissions)` dependency factory reads the `perms` claim already embedded in the access
token JWT (set at login, per Phase 2) and 403s unless every requested permission is present —
`iam:user:assign_role`, `catalog:product:write`, `order:refund:issue`, etc., matching the seeded
codes exactly. No Redis, so this is the same documented gap as Phase 2: a role granted or revoked
mid-session only takes effect the next time the user logs in or refreshes their token, not
instantly. `scripts/promote_admin.py <email> [role_code]` is the only way to create the first admin
today (idempotent — safe to rerun) since there's obviously no UI yet to promote the very first one.

### Schema

Two new tables in `models/catalog.py` / `models/commerce.py`: `inventory_movements` (append-only
stock ledger — `delta`, `reason`, `reference_type/id`, `balance_after`, `actor_user_id`, per spec
§8.3) and `refunds` (`amount`, `reason`, `status`, `transaction_id` unique, linked to both the order
and the payment it refunds). Migration `cb7fb7c4289c_inventory_and_refunds` — the MySQL
FK/index-drop-ordering bug (§8/§9 above, now a 3rd occurrence) was caught and fixed proactively
before ever applying it; full `upgrade → downgrade → upgrade` cycle verified clean.

### What was built

- **Catalog & inventory** (`services/admin/catalog_service.py`, `api/v1/admin/catalog.py`):
  product list/detail/create/update/soft-delete/restore, variant add/update/delete, and an
  inventory-adjust endpoint that writes a ledger row and recomputes `product.stock_total` from the
  live sum of non-deleted variant stock — never trusts a client-supplied total.
- **Orders** (`services/order_service.py` extended, `api/v1/admin/orders.py`): admin list (search +
  status filter, unscoped by user), a transition endpoint that reuses the exact same
  `ORDER_TRANSITIONS` state machine from Phase 3 (no separate "admin can do anything" bypass), and a
  refund endpoint that validates the amount against what's actually left to refund and writes a
  `Refund` row plus updates `order.refunded_total`/`payment_status`.
- **Users & roles** (`services/admin/user_service.py`, `api/v1/admin/users.py`): list/detail,
  assign/revoke role, suspend (revokes all refresh tokens via
  `RefreshTokenRepository.revoke_all_for_user` so a suspended user's existing sessions actually die,
  not just future logins — and hard-blocks suspending your own account), reactivate.
- **Coupons** (`services/admin/coupon_service.py`, `api/v1/admin/coupons.py`): list/create/update/
  deactivate with code-uniqueness checks — this is the CRUD UI that Phase 3's gap list said was
  missing (coupons had only existed via a seed script until now).
- **Dashboard** (`services/admin/dashboard_service.py`, `api/v1/admin/dashboard.py`): today/week
  order counts and revenue, orders-by-status breakdown, low-stock variant count, total customers —
  a handful of aggregate queries, not a real analytics engine.
- **Frontend**: a role-gated `AdminLayout` (redirects to login if unauthenticated, to `/` if
  authenticated but has no non-customer role) mounted at a separate top-level `/admin` route (not
  nested inside the storefront's `RootLayout`, since it has its own chrome), plus a conditional
  "Admin" link in the storefront header for staff users. Product/coupon forms reuse
  react-hook-form + zod exactly like the storefront checkout forms; the variant editor is a
  per-row inline-editable table with its own dirty-tracking and Save/Remove per row rather than one
  big form submit.

### Real bugs found and fixed (again, all by exercising the flows, not by inspection)

1. **Inventory adjustment silently reverted.** `POST /admin/inventory/{id}/adjust` wrote a correct
   ledger row (`balance_after` right) but the variant's own `stock` column bounced back to its old
   value. Cause: `_recompute_stock_total` re-fetched the product via `get_by_id`, which uses
   `execution_options(populate_existing=True)` (needed elsewhere so the eager-loaded `.variants`
   collection doesn't go stale — same pattern as the Phase 3 cart bug). But `populate_existing`
   cuts both ways: it also overwrites *uncommitted* in-memory changes on an identity-mapped object
   back to its last-flushed DB value, silently discarding the `variant.stock = new_stock` mutation
   that had just been made moments earlier. Fixed with `await self.session.flush()` immediately
   before the re-fetch — persists the mutation within the transaction first, so `populate_existing`
   has nothing uncommitted left to clobber. Verified via curl (ledger + `stock_total` correct on the
   very next adjust) and a direct DB query.
2. **Deleted products had no way back.** `restore_product` and its frontend service call existed
   from the start, but nothing surfaced *that* a product was deleted or how to reach the restore
   action — `AdminProductDetail`/`AdminProductListItem` didn't even expose `is_deleted`. Fixed by
   adding the field to both schemas and builders, then a dimmed row + "Deleted" badge in the list
   and a restore banner on the edit page.
3. **`z.coerce.number()` breaking `zodResolver`'s type inference** (product and coupon forms) — a
   schema's input type (raw `<input>` strings) diverges from its output type (numbers) once
   coercion is involved, and `useForm<T>`'s single-generic form assumes they're the same. Fixed
   using react-hook-form's 3-generic `useForm<FormInput, unknown, FormValues>()` signature
   (`FormInput = z.input<typeof schema>`, `FormValues = z.output<typeof schema>`) in both places.
4. **Blank *optional* numeric fields silently became `0`, not `null` — found during this session's
   final browser verification pass, after the fact of typechecking cleanly.** The coupon form's
   `max_discount_amount`/`min_order_amount`/`usage_limit_total`/`usage_limit_per_user` were all
   `z.coerce.number().optional()`. `z.coerce.number()` runs *before* `.optional()` ever sees the
   value, and `Number('')` is `0`, not `NaN` — so leaving a field blank coerced it to a real `0`
   instead of `undefined`. Confirmed by creating a coupon with every optional field left blank and
   querying the row directly: `max_discount_amount=0.00, min_order_amount=0.00,
   usage_limit_total=0, usage_limit_per_user=0` — all should have been `NULL`. This isn't cosmetic:
   `cart_service.py`/`order_service.py` treat `usage_limit_total is not None and used_count >=
   usage_limit_total` as the exhaustion check, so `0 >= 0` is true on the very first redemption
   attempt — **every coupon created without explicitly filling in these fields was silently
   dead-on-arrival**, and a `0` cap on `max_discount_amount` would zero out any percent/fixed
   discount even before that. Fixed with a `z.preprocess` step that maps `''`/`undefined`/`null` to
   `undefined` before the `z.coerce.number().optional()` runs. Re-verified: a fresh coupon created
   the same way now stores `NULL` in all four columns (confirmed via direct DB query), and editing
   it afterward to set a real `usage_limit_total` persists correctly alongside the still-`NULL`
   fields.

### Known gaps / deviations (in addition to what §1–3's table above already notes)

- **Deliberately out of scope this pass**: CMS/banners, support tickets, bulk product import/export,
  an audit-log viewer (actions aren't logged to a dedicated table, only implied by
  `inventory_movements`/`order_status_history`/`refunds` rows), feature flags, and search reindex
  tooling. None of these have any backend scaffolding yet — this is a real gap, not a UI-only one.
- **No permission-change propagation** — documented above, same root cause (no Redis) as Phase 2's
  session-cache gap.
- **Refund amount validation is server-side only** — the admin order page doesn't show
  paid/refunded totals inline (the type didn't expose them and a placeholder computation was
  removed rather than shipping something misleading); the backend still correctly rejects an
  over-large refund, so this is a UX gap, not a correctness one.
- **Idempotency-Key isn't used on admin mutations** (transition, refund, inventory adjust) the way
  it is on `POST /orders` — a double-click could in principle apply the same transition or refund
  twice; transitions are guarded by the state machine (a second identical transition attempt from
  the new state fails), but a double refund submit is not currently guarded beyond the
  remaining-amount check happening to still pass.
- **Dashboard is a handful of aggregate queries**, not a real analytics/reporting engine — no
  date-range picker, no CSV export, no per-category or per-brand breakdown.

### Verified live, browser-to-database, not just curl

Backend curl-verified end-to-end first: dashboard summary, product list/detail, inventory adjust
(both the bug in #1 above and its fix), order list/transition/refund, user list/role-assign/
revoke/self-suspend-guard, coupon CRUD. Then the full admin frontend, driven through actual Chrome,
signed in as `ada@example.com` promoted to `admin`+`super_admin` via `promote_admin.py`:
dashboard rendering real stat cards and an orders-by-status breakdown; Products → opened a product,
changed its price, saved, reloaded the page from scratch and confirmed the new price persisted;
adjusted one variant's stock inline in the `VariantsEditor`, saved, reloaded, confirmed the new
stock value survived a full page reload (not just optimistic UI); Orders → opened an order that had
auto-advanced from "Confirmed" to "Shipped" between the list view and the detail view (the Phase 3
lazy-reconciliation timeline advancing live, observed as a side effect rather than deliberately
triggered), applied a manual transition to "Out for delivery" with a reason, watched the badge
update; opened a separate paid/delivered order and issued a ₹100 partial refund, saw the success
message and the payment status flip to `partially_refunded`; Users → assigned the `support` role to
a customer-only account, saw the chip appear, revoked it, saw it disappear, suspended the account
(confirm/cancel UI, reason field), saw status flip to "Suspended" and the button become
"Reactivate account", reactivated it back to "Active"; Coupons → this is where bug #4 above was
actually found — created a coupon leaving every optional field blank, and only *then*, reading the
edit page's own re-fetched values (all showing `0` instead of blank) noticed it was wrong, tracked
it to the DB, fixed the schema, and re-verified create → edit (setting a real usage limit) →
deactivate all persisting correctly afterward.

---

## 11. Phase 5 search, recommendations & discovery (spec §14) ✅ for the scoped-down core

Built in one session, backend and frontend together, scoped down from the full spec surface
(Elasticsearch, synonyms, semantic/kNN search, `product_affinity` nightly precompute, named
multi-wishlists, review moderation — all deferred, noted below) to a coherent, genuinely-working
core: **real relevance search with autocomplete → similar/frequently-bought-together/recently-viewed
rails on the PDP → a working wishlist → back-in-stock alerts that actually fire on restock →
newsletter signup.**

### Schema

New `models/discovery.py` (migration `7e6e6ca89efc_discovery_and_search`): `search_queries` (logged
query + result_count, spec §14.3/§14.4), `wishlists`/`wishlist_items` (one implicit wishlist per
user — spec §8.3 allows named plural lists, simplified to a single default list for this scope),
`recently_viewed` (capped at 50/user, spec §8.5), `stock_alerts`, `newsletter_subscribers`. Also
added the spec §8.3/§14.2 `ft_products` FULLTEXT index (`title`, `search_keywords`, `WITH PARSER
ngram`) directly on the `Product` model (`mysql_prefix="FULLTEXT"`, `mysql_with_parser="ngram"`) so
`alembic check` sees no model/schema drift — full `upgrade → downgrade → upgrade` cycle verified
clean, continuing the FK/index-drop-ordering care from every prior migration (nothing new broke
here, but `ix_recently_viewed_user`/`ix_stock_alerts_variant_pending` start with their FK columns so
their explicit `drop_index` calls were removed from `downgrade()` up front rather than found by
trial and error again).

### Real bug found and fixed: the FULLTEXT ngram index built per spec was unusable, so search doesn't use it

This is the interesting one. Spec §14.1/§14.2 calls for MySQL `FULLTEXT ... WITH PARSER ngram` as
the non-Elasticsearch fallback. Built it exactly as specified, wired `MATCH(title, search_keywords)
AGAINST(:q IN NATURAL LANGUAGE MODE)` for relevance, and curl-tested it before trusting it (same
"actually exercise the flow" discipline as every prior phase) — and it was badly broken:
`q=tee` matched **3,874 of 8,103 products** (48% of the entire catalogue), and a deliberately
nonsense query `q=xyzzynonexistent` matched **6,628 products (82%)**. Root cause, confirmed by
querying MySQL directly: `ngram_token_size` defaults to 2, so "tee" decomposes into 2-grams `te`/`ee`
and "xyzzynonexistent" decomposes into ~15 overlapping 2-grams like `en`/`nt`/`on`/`te` — extremely
common English bigrams that appear in huge swaths of unrelated titles ("Green", "Sweet", "Sweater"…).
NATURAL LANGUAGE MODE scores any shared n-gram as a positive match, so short queries match almost
everything. Tried `BOOLEAN MODE` with quoted-phrase terms next (`+"tee"`) — better (302 matches) but
still imprecise, because ngram phrase-matching operates on shared token sequences rather than true
substring containment, still returning titles like "Green T-Shirt" for "tee" via approximate n-gram
overlap.

**Fix**: abandoned MATCH/AGAINST for ranking entirely. Search is now a precise **token-AND `LIKE`**
match across `title`/`search_keywords` (every significant word — length ≥ 2 — must appear as a
substring somewhere), with a **token-OR broadened fallback** when the strict AND returns zero rows
(spec §14.3's "fallback broadened query" — still implemented, just via a different mechanism), and a
cheap relevance proxy (`CASE WHEN title LIKE 'query%' THEN 1 ELSE 0`, tie-broken by `sold_count`)
instead of a real BM25-ish score. Re-verified: `q=tee` now returns exactly 302 honestly-matching
products (titles/brands that actually contain "tee" — including brand names like "Steenb" and
"TeeMoods", which is correct, not a bug, once traced through), `q=xyzzynonexistent` correctly returns
0 with the fallback flag set, `q=nike` correctly returns 0 (this dataset genuinely has no Nike
products), `q=blue jeans` returns 114 precise AND-matches. The `ft_products` index stays declared on
the model for schema fidelity with spec §8.3/§14.2 and as a documented on-ramp for a future real
Elasticsearch swap — it just isn't queried, which is the honest state to leave it in rather than
quietly making the index do something it doesn't (`repositories/catalog.py`'s `_token_condition`
docstring records this whole finding for the next person who's tempted to "simplify" back to
MATCH/AGAINST).

### Search (`repositories/catalog.py`, `services/catalog/product_service.py`, `api/v1/public/catalog.py`)

- `ProductRepository.list_products` now returns `(products, total, used_fallback)`; `used_fallback`
  surfaces as `meta.search_fallback` in the API response so the frontend can show "no exact matches,
  showing related results" instead of silently substituting a different result set.
- Every `q`-bearing search on page 1 is logged to `search_queries` (query text + result count +
  optional user id) — spec §14.3's zero-result analysis logging and the data source for
  autocomplete's "popular past queries."
- `repositories/search.py` (`SearchRepository`) backs `GET /search/suggest?q=`: top 5 products
  (thumbnail + price), top 3 brands, top 3 categories, top 4 popular past queries — all plain
  indexed `LIKE`/`GROUP BY` queries, no caching (spec §14.4 wants 60s server-side cache; skipped,
  no Redis, documented gap consistent with every other phase).
- `ProductRepository.similar()`: same category + gender + a ±40% price band (spec §14.5's
  `more_like_this` replacement), falling back to same-category-only if the price band comes up
  empty — common in this catalogue's smaller sub-categories.
- `ProductRepository.frequently_bought_with()`: co-occurrence counts from `order_items`, computed
  **on-demand per request** rather than spec §14.5's nightly Celery job into a `product_affinity`
  table (no Celery here). With only a handful of demo orders in this dataset the results are often
  sparse or empty — an honest reflection of the actual data, not padded with anything fabricated.

### Wishlist, recently-viewed, stock alerts, newsletter (`repositories/discovery.py`, `services/discovery_service.py`)

- `WishlistService`/`RecentlyViewedService`/`StockAlertService`/`NewsletterService`, all following
  the established `api → service → repository → model` layering. Wishlist add/remove is idempotent
  (checked before insert/delete rather than relying on the DB unique constraint to reject a
  duplicate); recently-viewed is a plain upsert-by-`(user_id, product_id)` with an overflow trim
  query capping at 50 rows per user, run inline since there's no Celery to batch it.
- **Back-in-stock notification actually fires**, not just logs an intent: `StockAlertService`
  imported into `AdminCatalogService.adjust_inventory` (a legitimate service→service call, not a
  repository reach-across) — when a variant's `available` crosses 0 → positive, every pending
  `stock_alerts` row for that variant gets emailed via the existing `ConsoleMailBackend` and marked
  `notified_at`. Verified end-to-end via curl: subscribed two alerts (one guest with an explicit
  email, one logged-in user with no email supplied — resolves to the account email), restocked the
  variant through `POST /admin/inventory/{id}/adjust`, and confirmed the log line
  `stock_alerts_notified count=2` plus two `mail_sent` entries.
- `GET /wishlist/slugs` exists purely as a cheap membership check (a bare list of slugs) so
  `ProductCard`/`ProductPage` can render a filled/outline heart on every card without fetching full
  wishlist payloads — React Query dedupes it to one request no matter how many cards are on screen.

### Frontend

- **`components/search/SearchBar.tsx`** replaces the old dead `/search` icon-link: an
  expand-in-place search field (fixed sheet on mobile, anchored popover on desktop) with a 200ms
  debounced autocomplete dropdown grouping products/brands/categories/popular queries, full keyboard
  nav (`ArrowUp`/`ArrowDown`/`Enter`/`Escape`, `aria-activedescendant`/`role="combobox"`/`role="option"`),
  and click-outside-to-close.
- **`CatalogPage`** (spec §14.3's zero-result UX): a dedicated empty state for `q`-driven searches
  ("No results for X" + spelling/browse-catalogue guidance + a "Browse all products" link) distinct
  from the generic filter-emptied state, plus a "no exact matches — showing related results" banner
  when `meta.search_fallback` is true.
- **`hooks/useWishlist.ts`**: `useWishlistSlugs()` (React-Query-cached membership list) +
  `useToggleWishlist()` (optimistic add/remove with rollback on error). Wired into both
  `ProductCard`'s existing (previously purely-local, non-functional) heart button and `ProductPage`'s
  existing (previously inert, no `onClick` at all) wishlist button; both redirect a guest to
  `/auth/login?next=...` instead of attempting the mutation.
- **`pages/account/WishlistPage.tsx`** at `/account/wishlist`, reachable from the account nav (the
  "Wishlist (soon)" placeholder from Phase 2/3's `AccountPage` now just says "Wishlist" and links
  through).
- **`components/product/ProductRail.tsx`**: horizontal-scroll product row, reused for all three PDP
  rails (Similar products, Frequently bought together, Recently viewed) — renders nothing at all
  when its data is empty rather than showing an empty section header. `ProductPage` records a view
  via `POST /products/{slug}/view` on mount (signed-in users only — see gaps).
- **`components/product/NotifyMeForm.tsx`**: below the disabled "Out of stock" button, a signed-in
  user gets a single "Notify me when back in stock" button (uses their account email server-side); a
  guest gets an inline email-capture form. Both verified live — the signed-in path shows a live
  toast + inline confirmation after clicking, and a `POST /admin/inventory/.../adjust` restock in a
  separate tab produced the real `stock_alerts_notified` log line for both a guest and a signed-in
  subscriber captured earlier in the same test pass.
- **`components/layout/NewsletterForm.tsx`** in the footer's new fifth column; verified live
  (submitted a real email, got "You're subscribed.").

### Known gaps / deviations

- **Elasticsearch not built at all** — `SEARCH_BACKEND` isn't even a real switch yet; there's only
  the MySQL path described above. Spec §14.1's "both implementations satisfy the same contract test
  suite" doesn't apply since there's one implementation.
- **No synonyms** (spec §14.2's `tee ⇄ t-shirt`, `kurti ⇄ kurta`, etc.) — a real gap the token-LIKE
  approach can't paper over; searching "tshirt" and "t-shirt" can return different result sets.
- **No semantic/kNN search** (spec §14.5's optional phase-5 enhancement) — not attempted, no
  embedding model in this stack.
- **`frequently_bought_with` is on-demand, not a nightly `product_affinity` precompute** — fine at
  this data volume (single-digit-millisecond query), would not scale to a real order volume without
  revisiting.
- **No 60s autocomplete cache, no 200ms server-side anything** — all Redis-shaped gaps, consistent
  with every earlier phase's documented reason (no Redis in this native-Windows setup).
- **Recently-viewed is signed-in-users-only** — spec §14.5 says "client-hydrated," which would also
  cover guests via `localStorage`; not built, so a guest browsing session has no recently-viewed
  rail at all (the PDP simply omits the section, per `ProductRail`'s empty-renders-nothing rule).
- **Wishlist is a single implicit list per user**, not spec §8.3's named multi-list model — matches
  how almost every real storefront's wishlist actually behaves in practice, but is a deliberate
  simplification worth flagging if multi-list ever becomes a real requirement.
- **Similar-products price band (±40%) and category match are heuristic**, not ES's
  `more_like_this` text-similarity scoring — reasonable given the actual dataset (heavily
  menswear-skewed, sparse per-category population in spots), but a real semantic-similarity engine
  would generalise better.
- **Guest back-in-stock/newsletter emails aren't verified deliverable** — `ConsoleMailBackend` logs
  the send, same as every other mail flow in this project; no real inbox involved (unchanged from
  Phase 2's mail-backend gap).

### Verified live, browser-to-database, not just curl

Backend curl-verified first: search precision/fallback for `tee`/`xyzzynonexistent`/`nike`/`blue
jeans` (including the FULLTEXT-to-LIKE pivot above), `/search/suggest` grouping, `/products/{slug}
/similar` and `/frequently-bought-together`, `/recently-viewed` + `POST .../view` round-trip,
wishlist add/list/slugs/remove, newsletter subscribe, and the full stock-alert → admin-restock →
`stock_alerts_notified count=2` chain. Then the same flows through the actual Chrome-driven
frontend, signed in as the existing `ada@example.com` (promoted admin): typed "tee" into the new
header search bar and watched the live autocomplete dropdown render matching products/brands and a
genuine "popular past query" entry (seeded by the curl testing moments earlier — real evidence the
`search_queries` logging loop works end-to-end, not just that the UI renders mock data); opened a
suggested product, confirmed the Similar-products rail rendered real related items, clicked the
wishlist heart and watched it fill in, scrolled down and confirmed the Recently-viewed rail showed
the exact two products viewed earlier via curl against the same account; visited `/account/wishlist`
and saw both wishlisted items with working cards; navigated to a product where every variant is out
of stock, confirmed the disabled "Out of stock" button and the signed-in "Notify me" button, clicked
it, and got both a toast and an inline "You're on the list" confirmation; submitted the footer
newsletter form and got "You're subscribed."; searched a deliberately nonsense query and confirmed
the dedicated zero-result empty state (spelling guidance + "Browse all products" link) rendered
instead of a bare "no products" message. `tsc -b` and `oxlint` both clean throughout.

---

## 12. Phase 6 testing (spec §24) 🟡 — a real, scoped test suite, and a real bug it caught

Phase 6 ("Hardening & Launch") spans several genuinely disjoint tracks — testing, security
hardening, SEO/accessibility, observability, CI/CD, deployment/DR — several of which need
infrastructure this native-Windows setup doesn't have (no git repo yet, no Docker, no CI remote,
no k6/ZAP). Asked which to start with; testing was chosen, since spec §2.3 states coverage as a
named success criterion and the app had **zero tests** of any kind going in.

### Backend: pytest + a dedicated test database

- **`backend/pytest.ini`**: `asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`.
- **`backend/tests/conftest.py`**: points the whole app at a separate `blackcart_test` MySQL
  database (env vars set before any `app.*` import, since `get_settings()` is `@lru_cache`d and
  `app.db.session` builds its engine at import time) — dropped and recreated fresh every test run,
  schema built via `Base.metadata.create_all` (which picks up the FULLTEXT `ft_products` index too,
  since it's declared on the model, not just in migration SQL), RBAC seeded by importing and
  calling `scripts/seed_rbac.py`'s `seed()` directly.
- **Two isolation strategies**, deliberately different:
  - `db_session`/`client` (used by nearly every test): one DB connection per test, wrapped in an
    outer transaction with the SQLAlchemy session joined via `join_transaction_mode=
    "create_savepoint"` — the service layer's own internal `session.commit()` calls just close a
    savepoint, and the whole test's writes roll back at teardown. No test can see another test's
    data, and nothing needs manual cleanup.
  - `real_client`/`real_db_session` (used by exactly one test — see below): a dedicated per-test
    engine with **real, independent, non-rolled-back** sessions, one per request, exactly like
    production. Needed because the one thing that test is actually checking — real MySQL row
    locking under real concurrent transactions — doesn't exist if every request secretly shares
    one session.
  - Every fixture builds and disposes its **own** engine within the current test's own event loop
    rather than reusing the module-level `app.db.session.engine` singleton across tests: pytest-
    asyncio gives each test function a fresh event loop by default, and an async SQLAlchemy engine
    binds its internal asyncio primitives (pool locks) to whichever loop first touches it — reusing
    one engine across loops is the classic way to hit "Future attached to a different loop"
    errors. Hit this for real while building the harness (first with a session-scoped `_prepare_
    database` reusing the shared engine, then again after overriding pytest-asyncio's `event_loop`
    fixture — which turned out to be only partially honored in pytest-asyncio 0.24 and produced
    the same error non-deterministically); the per-test-engine design above is what actually fixed
    it, not a config tweak.

### The real bug: checkout's stock lock was real at the DB level but silently ineffective in Python

Spec §9.4/§24.3 explicitly calls for "a concurrency test [that] fires 50 simultaneous checkouts
against a variant with stock 10 and asserts exactly 10 succeed." Wrote it (`tests/
test_inventory_concurrency.py`) against `real_client` — 50 separate users, 50 separate carts, one
shared variant with `stock=10`, fired via `asyncio.gather`. First run: **all 50 succeeded**, and
the variant's final stock was `9`, not `0` or negative.

Root cause, found by an isolated repro before touching the real code: `OrderRepository.
lock_variants()`'s `SELECT ... FOR UPDATE` **does** correctly lock the row at the database level —
confirmed directly (a second concurrent transaction blocked for exactly as long as the first held
the lock). But `CartRepository.get_active_by_user()` eager-loads `Cart.items → CartItem.variant`
*before* `create_order()` ever calls `lock_variants()` — so the `ProductVariant` Python object is
already sitting in the session's identity map, populated with whatever `.stock` it had *before*
the lock was acquired. SQLAlchemy's default behaviour for a plain `select()` against an
already-identity-mapped row is to **not** overwrite its already-loaded attributes. So every one of
the 50 concurrent requests blocked correctly, then — once unblocked — silently read the *stale,
pre-lock* Python object instead of the freshly-locked, freshly-committed database row. All 50 saw
`stock=10`, all 50 passed the availability check, all 50 computed `10 - 1 = 9` in Python, and the
last one to commit "won" — a textbook lost-update race hiding behind a lock that looked correct
from every angle except the one that mattered. This is the exact same *class* of bug as the
`populate_existing` fixes from Phases 3/4 (cart-stale-after-mutation, inventory-adjustment-
reverted) — same root cause, different call site, never connected to this one until a concurrency
test actually existed to trigger it.

**Fix**, in `repositories/order.py`'s `lock_variants()`: added `.execution_options(populate_existing
=True)`, so the freshly-locked row's data actually overwrites the stale cached object. That alone
then surfaced a *second*, smaller bug: `populate_existing` refreshes the whole object, which
expired the variant's already-loaded `.product`/`.product.brand` relationships too (not requested
by this specific query) — and `create_order()` reads `i.variant.product.title` /
`i.variant.product.brand.name` for the order-line snapshot right after calling `lock_variants()`,
so the very next request hit `MissingGreenlet` (an expired relationship triggering an implicit
lazy-load, illegal under async SQLAlchemy outside an awaited context). Fixed by adding
`selectinload(ProductVariant.product).selectinload(Product.brand)` to the same query. Re-ran:
**exactly 10 of 50 succeeded**, final stock `0`, `reserved` `0`. Full non-concurrency suite (30
other tests) re-run afterward to confirm the fix caused no regressions — clean.

This was shipping in production-equivalent code since Phase 3 (commit history has no test ever
exercising real concurrent checkouts) — a flash-sale-style traffic spike against a low-stock item
would have oversold it without limit. Exactly the failure mode the spec's own test scenario names,
caught the first time anyone actually wrote that test.

### What else the backend suite covers

48 tests total across 6 files:

- **`test_pricing.py`** (8) — `q2` rounding, shipping-fee threshold/COD-surcharge math, tax
  computation, a totals-identity check across several synthetic carts (spec §24.3's rounding
  property test, done as a fixed case set rather than a true property-based/hypothesis test).
- **`test_cart.py`** (11) — quantity clamped to available stock and to the 10-unit cap (both the
  single-request and accumulate-then-clamp paths), out-of-stock add rejected, percent/fixed/
  free-shipping coupon math including the max-discount cap and the min-order-amount rejection,
  expired and unknown coupon codes rejected.
- **`test_order_lifecycle.py`** (9) — each deterministic test card's terminal state, COD's
  pending-payment-status quirk, duplicate `Idempotency-Key` returning the same order without a
  second stock decrement, cancellation restoring stock before `PACKED` and being refused after
  (forcing the pre-ship-delay window via a direct `order.created_at` rewrite, then a real `GET` to
  trigger `_reconcile()` — matching exactly how the real app advances state), illegal vs. legal
  admin transitions, and a coupon's per-user redemption limit actually blocking reapplication
  after a real order consumed it.
- **`test_inventory_concurrency.py`** (1) — the flagship scenario above.
- **`test_auth_security.py`** (11) — refresh-token reuse revoking the whole family (and confirming
  a mundane logout-revoke is *not* misflagged as reuse), tampered/expired/`alg:none` JWTs
  rejected, IDOR on both orders and addresses (user B gets a clean 404 for user A's resources, not
  a 403 that would confirm the resource exists), missing-vs-present CSRF token on a cookie-auth
  POST, and admin routes correctly 403ing a permission-less user and 401ing an unauthenticated one.
- **`test_search.py`** (5) — a regression guard for the FULLTEXT-to-LIKE search rewrite from Phase
  5 (§11 above): single- and multi-token AND precision against a small fixture catalogue, the
  zero-result fallback flag, and the OR-broadened fallback actually returning the right set.

Coverage (`pytest-cov`, line coverage over `app/`): **68% overall**. Concentrated where it matters
most per spec §24.2's own priority (pricing, permissions, state machine) rather than spread evenly
— `core/pricing.py` and the auth/order/cart HTTP paths are heavily exercised; admin sub-services,
the discovery service, and large chunks of `order_service.py`/`cart_service.py` (refunds, tracking,
admin listing, `_reconcile`'s edge branches) aren't touched at all, since this pass targeted the
methods the test suite's scenarios actually walk through rather than every method in every file.
This is a deliberate first pass, not a claim of meeting spec §24.2's 80%-overall/100%-service-layer
gates.

### One flaky test, and why

`test_tampered_access_token_is_rejected` initially corrupted the token by flipping its *last*
character — which failed non-deterministically (~1 run in 5). Root cause: base64url's final
character sometimes has "don't-care" bits, so a specific subset of last-character edits decode to
the exact same bytes, leaving a technically-unmodified (and therefore still valid) signature. Not
a bug in the app — a bug in the test's own tampering method. Fixed by flipping a character in the
middle of the JWT's payload segment instead, which changes real signed bytes unconditionally.
Verified with 8 back-to-back runs, all green, after being flaky roughly 20% of the time before.

### Frontend: vitest + React Testing Library

- **`frontend/vitest.config.ts`** + **`src/test/setup.ts`** (`@testing-library/jest-dom/vitest`).
  `npm run test` / `npm run test:watch` added to `package.json`.
- 32 tests across 5 files: pure `lib/money.ts` formatting (7), `CartLine`'s quantity
  increment/decrement/cap-at-available/cap-at-10/remove/unavailable-notice/price-changed-notice
  behaviour (9), `CouponInput`'s apply/uppercase/applied-state/error-state/remove flow mocked
  against `@/services/cart` (6), `SearchBar`'s 200ms debounce (including the "below the 2-char
  minimum never fires" case), keyboard navigation into a specific suggestion, Enter-with-nothing-
  highlighted falling through to a plain search submit, and Escape-to-close (7), and `ProductCard`'s
  wishlist toggle — guest redirect to login, add, and remove, mocked against `@/services/discovery`
  and `@/hooks/useAuth` (3). `tsc -b` and `oxlint` both clean throughout.
- Network calls are mocked at the service-module boundary (`vi.mock('@/services/...')`) rather than
  via `msw` (spec §24.1 names msw) — simpler to set up for this scope and sufficient for testing
  component/hook logic in isolation; genuine request/response-shape coverage still comes from the
  backend's own API tests and from the manual browser verification passes each prior phase did.

### A real, separate finding while installing test tooling: react-router has an open high-severity CVE

Installing `vitest`/`@testing-library/react` triggered `npm audit`, which flagged
[GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2) — a high-severity CSRF
bypass in React Router's RSC mode, affecting versions 7.12.0–8.2.0. The installed version
(7.18.1, pinned via `^7.18.1` in package.json) falls inside that range. The real fix is a **major**
version bump to 8.3.0+ (`npm audit fix --force` instead tries to downgrade within the `^7.18.1`
range, which doesn't actually reach a patched version) — not attempted here, since a react-router
v8 upgrade is a breaking-change migration across every route/nav call in the app and shouldn't
happen as a side effect of adding test tooling. **Flagged, not fixed — a deliberate v8 migration
is a follow-up task**, not a bundled one.

### Known gaps / deviations

- **No Playwright E2E suite** (spec §24.3's 10 named journeys) — everything above is unit/
  integration-level; the golden-path flows have only ever been manually verified live through the
  browser each prior phase, not automated.
- **No contract testing** (schemathesis/OpenAPI-diff), **no load testing** (k6), **no SAST/DAST**
  (bandit/trivy/ZAP) — all named in spec §24.1/§24.5, none attempted.
- **No property-based testing** (hypothesis) — the totals-identity check is a fixed case set, not
  a true generated-input property test.
- **Coverage is 68% overall, not spec's 80%/100%-service-layer gates** — see above.
- **`test_auth_security.py`'s IDOR coverage is orders + addresses only** — spec §22.7's checklist
  also names reviews and carts; reviews don't exist yet (unbuilt feature) and cart IDOR wasn't
  separately tested (carts are guest-cookie- or user-scoped by construction, lower risk, but
  untested is untested).
- **The react-router CVE is flagged, not fixed** — see above.

### Verified

`pytest tests/ -v --cov=app --cov-report=term-missing` → 48 passed, 68% line coverage.
`npm run test` → 32 passed. `tsc -b` and `oxlint` clean on both the new test files and the two
production-code fixes (`repositories/order.py`). The concurrency test specifically re-run 1 more
time after the fix (on top of the initial green run) to confirm exactly-10-of-50 wasn't a fluke.

---

## 13. Phase 6 continued — security, SEO, accessibility, observability 🟡

Continuing Phase 6 after §12's testing work. Asked which of §19–23/§25–26 to tackle; chose to
work through security → dependency audit → SEO → accessibility → basic observability, skipping
only what's genuinely blocked by missing infra (no git repo for CI/CD, no Docker/Grafana/k6/ZAP).

### Security headers (spec §22.2)

New `middleware/security_headers.py`. Spec puts these at the Nginx layer; there's no Nginx here,
so they're a FastAPI middleware instead — same headers, different layer. Deliberately **more**
locked-down than spec's own template: spec's CSP (`default-src 'self'`, nonce-based `script-src`)
is written for a server that renders HTML with inline scripts. This backend is a pure JSON API
(`/docs` aside, disabled outright in production) that never returns HTML for a CSP to police, so
`default-src 'none'` is the actually-correct policy here — no nonce generation, because there's no
inline script for a nonce to authorise. `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`
match spec's values exactly; `Strict-Transport-Security` is gated on `is_production` so a plain-http
local session is never told to upgrade every future request to https. A new `POST /api/v1/csp-report`
(`api/v1/security.py`) logs violation reports via structlog — accepts raw JSON rather than a strict
schema, since browsers send two different historical report shapes.

**Ordering bug avoided, not hit**: `ResponseEnvelopeMiddleware` rebuilds the response object by
copying `raw_headers` forward from whatever it receives — so `SecurityHeadersMiddleware` has to run
*before* it in the request-in/response-out sense. Starlette's `add_middleware()` makes the
earliest-added middleware innermost (closest to the route) — reasoned through this rather than
guessing, then verified with `curl -sD -` that every header actually survives the envelope rebuild.

### Rate limiting (spec §10.7/§22.1)

New `core/rate_limit.py`: spec wants a Redis-backed token bucket shared across API workers; no
Redis here, so it's a plain in-process fixed-window counter per `(endpoint, IP)`, correct for this
single-worker native setup but would under-count if this ever ran behind multiple worker processes
without a shared store — documented, not hidden. Applied to `/auth/register` (5/hour),
`/auth/login` (20/15min — a coarser, faster-to-trigger signal than the existing DB-based lockout,
since it doesn't need a DB round trip), `/auth/email/resend`, `/auth/password/forgot` (5/hour
each), `/auth/password/reset` (10/hour). Returns `429` with a real `Retry-After` header — required
extending `AppError` with an optional `headers` dict that the exception handler now forwards,
since the existing error envelope had no header-passing path at all.

**Test-suite interaction, caught immediately**: the limiter's counters live in a module-level dict
for the whole test process. Two problems, both fixed in `conftest.py`: (1) added an autouse
`_reset_rate_limits` fixture clearing the dict before every test, so whichever test happened to run
6th against `/auth/register` in a given run didn't get a spurious 429 depending on test order; (2)
the 50-concurrent-checkout test registers 50 users through `real_client`, and ASGITransport gives
every simulated client the *same* fake source IP by default — 50 registrations from "one IP" tripped
the new 5/hour limit immediately. Fixed by assigning each of the 50 test clients a distinct
`X-Forwarded-For` header, which is also more realistic (a real flash sale comes from many IPs, not
one) — not a rate-limiter bug, a test fixture that needed to catch up to a control that didn't
exist when it was written.

### Dependency audit (spec §22.7)

`pip-audit` found 29 known vulnerabilities across 6 backend packages. Upgraded 4 that had a clean,
low-risk path: `pyjwt` 2.10.1→2.13.0, `cryptography` 43.0.3→49.0.0, `python-dotenv` 1.0.1→1.2.2,
`aiomysql` 0.2.0→0.3.2 — full test suite re-run after (still 50/50 green). Left 2 unfixed and
documented rather than force-upgraded:

- **`starlette` (0.41.3, ~10 CVEs)** — transitively pinned by `fastapi==0.115.6`
  (`starlette<0.42.0,>=0.40.0`); every fix version is outside that range. The real fix is a FastAPI
  major-version bump (latest FastAPI wants `starlette>=0.46.0`), which is a breaking-change
  migration across the whole app's routing/DI/response-model surface — **confirmed this the hard
  way** (see below), not a call to make silently inside a dependency-patching pass.
- **`pytest` (8.3.4)** — dev-only, never ships to production; left alone rather than risk the
  pytest 8→9 jump breaking the pytest-asyncio 0.24 interplay this session's own test harness
  depends on (§12's event-loop debugging).

**Confirmed the starlette risk is real, by accident**: installing `prometheus-fastapi-instrumentator`
(for the `/metrics` endpoint below) silently pulled `starlette` up to 1.3.1 as a transitive
dependency — and the app immediately failed to import (`TypeError: Router.__init__() got an
unexpected keyword argument 'on_startup'`, a real FastAPI/Starlette API break). Caught by the
routine "does the app still import" check this session runs after every dependency change, not
by inspection. Fixed by pinning `starlette==0.41.3` back explicitly and using
`prometheus-fastapi-instrumentator==6.1.0` instead (an older release that depends on `fastapi`
directly rather than `starlette`, so it doesn't drag the pin along with it) — verified the resolved
environment afterward and re-ran the full suite. This is now the concrete example for why the
starlette CVEs are flagged-not-fixed rather than papered over: the *first* attempt to touch this
dependency in any way broke the app outright.

**A dependency upgrade surfaced a real, separate finding**: `pyjwt` 2.13.0 added a warning —
`InsecureKeyLengthWarning: The HMAC key is 20 bytes long, which is below the minimum recommended
length of 32 bytes for SHA256` — on every single token this app has ever issued. The dev-default
`APP_SECRET_KEY` (`"dev-secret-change-me"`, used whenever the env var isn't set) is exactly 20
bytes, under RFC 7518 §3.2's recommended HMAC-SHA256 minimum. Fixed in `core/config.py`: lengthened
the default to 35 bytes (silences the warning in dev/test), and — since the placeholder-string
check alone doesn't catch a *real* but still-too-short production secret — added a second fail-fast
check (`len(app_secret_key) < 32 bytes`) to the existing production guard, so a misconfigured
production secret is rejected at startup instead of quietly issuing weak tokens forever. Verified:
the warning is gone, full suite still green.

**npm audit** re-confirmed the one open finding from Phase 6's testing session — react-router's
CSRF-bypass CVE (GHSA-qwww-vcr4-c8h2) — unchanged, still deliberately deferred (major-version fix).

### SEO (spec §20)

- **Backend** (`api/seo.py`, mounted unprefixed on the app root like `/healthz`): `GET
  /sitemap.xml` (8,121 real URLs — home + ~17 categories + 8,103 active products, `lastmod` from
  `Product.updated_at`) and `GET /robots.txt` (disallows `/admin`, `/checkout`, `/account`, `/api`,
  `/search`, `/cart`; references the sitemap). Deliberately **not** spec §20.4's sitemap-index-of-
  chunked-child-sitemaps structure — at ~8k URLs everything fits in one file under the 50k-URL
  cap, and building index/chunking machinery that would never actually execute at this scale would
  just be untested code. Dropped a planned `/b/{brandSlug}` sitemap section on realizing no such
  frontend route exists yet — would have been dead links. In production behind Nginx (not present
  here), `/sitemap.xml`/`/robots.txt` need an explicit proxy rule to this backend, same as every
  other "no Nginx" deviation already documented.
- **Frontend**: `components/seo/SeoHead.tsx` uses React 19's native support for `<title>`/`<meta>`/
  `<link>` anywhere in the render tree (hoisted to `<head>` automatically — no react-helmet
  needed). Wired into Home (Organization+WebSite JSON-LD), CatalogPage (BreadcrumbList+ItemList,
  `noindex` on `q`-driven search-result pages since they're not canonical content), and ProductPage
  (Product+BreadcrumbList JSON-LD, OG/Twitter image from the primary product photo).
  `lib/structuredData.ts` builds the JSON-LD payloads from the same data the page already rendered
  (spec §20.3's "generated from the same data the page renders"). JSON-LD is rendered via a
  defensively-escaped `dangerouslySetInnerHTML` (`<` → `<`) — the payload is always JSON this
  code built itself, never raw user input, but a product title containing a literal `</script>`
  sequence could otherwise break out of the tag; this is the standard JSON-LD XSS mitigation, not
  an exception to the "no dangerouslySetInnerHTML" rule so much as the one legitimate use of it.
- **Verified live**: fetched real JSON-LD off both the home page and a real product page through
  Chrome (`document.querySelectorAll('script[type="application/ld+json"]')`) — correct `@type`,
  real price/currency/availability/rating pulled from the actual API response, not placeholder data.

### Accessibility (spec §19)

Ran `axe-core` (fetched from a CDN into the live Chrome tab, not installed as a project dependency
— a one-time audit tool, not a permanent one) across 15+ page/state combinations: Home, PLP, PDP,
Cart, Login, Register, Wishlist, Order History, Account, the search overlay, and 7 admin pages
(Dashboard, Products list/form, Orders list, Users list/detail, Coupons list/form). Found and fixed
two real, sitewide issue classes rather than one-off page bugs:

- **`heading-order`** (moderate): `FilterSidebar`'s "Brand" heading was an `<h3>` with no `<h2>`
  anywhere before it on category pages (h1→h3 skip) — changed to `<h2>`. `Footer`'s five section
  headings ("Shop"/"Help"/"Company"/"Legal"/"Newsletter") were all `<h3>`, which is only valid if
  every single page renders an `<h2>` before the footer — true on content-heavy pages (Home, PLP,
  PDP) but not on simple ones like the auth pages (h1 with no h2 at all before the footer).
  Changed all five to `<h2>`, which is correct regardless of what precedes it on any given page —
  the sitewide fix, not a per-page patch.
- **`select-name`** (critical): 6 admin filter/action `<select>` elements (category/status filters
  on Products and Orders lists, the "add a role" select on User detail, the "next status" select on
  Order detail) had no accessible name — no `<label>`, no `aria-label` — just a placeholder-style
  first `<option>` that's only a *visual* label substitute, invisible to assistive tech. Added
  `aria-label` to each, plus the three admin search `<input>`s that had the same gap (placeholder
  text only — not flagged by axe as a violation, but still `placeholder`-only labeling, the exact
  anti-pattern spec §8's forms guidance already calls out elsewhere in this codebase).

Re-ran the full sweep after fixing: **zero violations across every page tested.** Full frontend
test suite (32 tests) and `tsc -b`/`oxlint` re-run clean afterward.

### Observability (spec §21)

`Instrumentator().instrument(app).expose(app, endpoint="/metrics")` — `prometheus-fastapi-
instrumentator==6.1.0` (not the latest 8.0.2; see the dependency-audit section above for why).
Gets spec §21.2's `http_requests_total`/`http_request_duration_seconds` (by method/route/status)
for free; verified live via curl that real traffic against `/healthz` and `/api/v1/products`
produces real counter entries. `/metrics` itself is unauthenticated, matching Prometheus's usual
internal-network-only scrape model — would need a network-level restriction in a real deployment
(Nginx's job, not present here). Structured logging (spec §21.1) already existed from Phase 0.

### Known gaps / deviations

- **`starlette`/`fastapi` CVEs deliberately unfixed** — see the dependency-audit section; the real
  fix is a FastAPI major-version migration, empirically confirmed risky this session.
- **`react-router` CVE deliberately unfixed** — carried over from §12, unchanged.
- **No OpenTelemetry tracing, no Grafana dashboards/alerts, no business-metric counters**
  (`orders_created_total`, `payment_attempts_total`, etc.) — spec §21.2–21.4, needs a collector and
  Grafana this native setup doesn't have.
- **No hreflang, no `redirects` table for slug changes, no CI structured-data linting** — spec §20.2
  /§20.4, lower priority at this project's single-locale, no-live-CI stage.
- **Accessibility sweep is axe-core only, not a full manual WCAG audit** — axe catches ~30-40% of
  real accessibility issues by its own project's estimate; things like actual screen-reader
  walkthroughs, keyboard-only full-journey testing (spec §24.3's E2E scenario #9), and color
  contrast edge cases in dynamic states weren't separately verified.
- **No SAST/DAST** (bandit, trivy, ZAP), **no gitleaks/SBOM** — spec §22.7; several need a git
  history or CI to run against, which don't exist yet.
- **Rate limiting is in-process, not Redis-backed** — same category of gap as the DB-based login
  lockout from Phase 2; would under-count across multiple worker processes.

### Verified

Backend: `pytest tests/ -q` → 50 passed (48 + 2 new rate-limit tests) after every change in this
section, not just at the end. `pip-audit` re-run clean of new findings. Frontend: `npm run test` →
32 passed, `tsc -b`/`oxlint` clean. Live-verified via curl: security headers present on a real API
response, CSP report endpoint accepts a POST, `/sitemap.xml` returns 8,121 real URLs, `/robots.txt`
correct, `/metrics` shows real per-route counters. Live-verified via Chrome: JSON-LD on home and a
real product page, zero axe violations across the full page sweep after fixes.

---

## 14. Reviews & Moderation (spec §8.3, §9.7) ✅

Built in one session, backend and frontend together — the first genuinely new feature since the
spec's Phase 0–6 roadmap (§29) was exhausted; picked over CMS/banners/support-tickets and a
storefront polish pass because it's the one with real, un-stubbed schema fields already sitting
unused on `products` (`rating_avg`/`rating_count`/`review_count` have been `NULL`/`0` on every
product since Phase 1).

### Schema

New `models/review.py` (migration `961a4da1cda1_reviews`): `reviews(id, product_id FK CASCADE,
user_id FK CASCADE, order_item_id FK SET NULL, rating CHECK(1..5), title, comment,
is_verified_purchase, status, helpful_count, reported_count, moderated_by, moderated_at,
created_at, updated_at)`, `UNIQUE(product_id, user_id, order_item_id)` exactly as spec §8.3
specifies — one review per purchased line item, not per product (see the "real bug" below for why
that distinction turned out to matter). `alembic upgrade → downgrade → upgrade` and `alembic check`
verified clean; the recurring FK/index-drop-ordering fix (same class of bug as every prior
migration) was applied proactively to `downgrade()` before ever running it.

### Backend (`repositories/review.py`, `services/review_service.py`, `api/v1/public/reviews.py`, `api/v1/admin/reviews.py`)

- **Eligibility** (spec §9.7's "only a DELIVERED order item may be reviewed"): `GET
  /products/{slug}/reviews/eligibility` lists every one of the user's delivered-and-unreviewed
  order items for that product. `POST /products/{slug}/reviews` re-validates server-side
  (`order_item_id` must belong to the user, on a delivered order, for this exact product, not
  already reviewed) rather than trusting the eligibility response — the same "don't trust the
  client-side snapshot" discipline as cart/checkout pricing.
- **Moderation queue**: `GET /admin/reviews?status=` + `POST /admin/reviews/{id}/moderate`, gated
  by the `review:review:moderate` permission that was seeded (and unused) since Phase 2's RBAC
  matrix. Every moderation decision recomputes `rating_avg`/`rating_count` (from **approved**
  reviews only) and `review_count` (from every review regardless of status) on the product row —
  spec §9.7's exact two-tier aggregate rule.
- **Own-review visibility**: the public list endpoint shows approved reviews to everyone, plus the
  viewer's own review(s) regardless of status — "the author always sees their own pending review"
  (spec §9.7), implemented as an OR condition in the `WHERE` clause rather than a second query.
- **24-hour edit window**: `PATCH /reviews/{id}` lets the author edit within 24h of posting, which
  resets `status` back to `pending` and clears `moderated_by`/`moderated_at` (spec §9.7) — re-review
  required, not a silent re-publish.

### Real bugs found and fixed (again, all by exercising the flows live, not by inspection)

1. **`MissingGreenlet` on `review.created_at` after the very commit that created it.** First
   `POST /products/{slug}/reviews` against the live dev server 500'd. Root cause: SQLAlchemy's
   `expire_on_commit=True` (the default) marks *every* attribute on *every* tracked object as stale
   after any commit — not just the row that was written — so building the response DTO by reading
   `review.created_at` (a `server_default` column MySQL can't `RETURNING`) right after
   `session.commit()` tried an implicit lazy-reload outside an awaited context. This is the same
   *class* of bug as the cart/inventory/coupon `populate_existing` fixes from Phases 3/4/6 — never
   read an ORM attribute after a commit without an explicit `await session.refresh(...)` or having
   captured the value beforehand. Fixed in `create()`/`update_own()`/`AdminReviewService.moderate()`
   by building the returned response object either immediately after an explicit `refresh()` or
   *before* the commit that would expire it, whichever was cheaper for that call path.
2. **`MultipleResultsFound` on the eligibility endpoint for a repeat purchaser.** Caught live in the
   browser: Ada (who'd bought and had delivered two separate units of the same product across two
   orders) got a 500 the moment she opened "Write a review" a second time. `ReviewRepository.
   get_own_review()` used `scalar_one_or_none()` assuming one review per (product, user) — but the
   schema's actual unique constraint is per (product, user, *order_item*), so a user who reviewed
   both of their deliveries legitimately has two `Review` rows for the same product. Fixed by
   ordering by `created_at DESC LIMIT 1` — the eligibility card now shows the most recent one for
   quick-edit; every review (including the older one) is still fully visible and editable through
   the ordinary review list, nothing is hidden. Added a regression test
   (`test_eligibility_after_reviewing_two_separate_deliveries_of_same_product`) since this was a
   real gap in the original spec-reading, not just an edge case.
3. **Stale React Query cache showed the wrong viewer's version of the review list.** After fixing
   bug #2 and reloading the PDP, Ada's own pending review still didn't appear even though she was
   signed in and the backend now returned it correctly (confirmed separately via curl). Cause: the
   reviews list's `queryKey` was `['reviews', productSlug, page]` — no viewer identity in it — so a
   copy already fetched as a guest (or a different user) stayed cached and wasn't refetched on
   login, even though the endpoint's response genuinely depends on who's asking (spec §9.7's
   own-pending-review visibility). Fixed by adding `user?.public_id ?? 'guest'` to the query key, so
   a login/logout naturally lands on a fresh cache entry instead of serving a stale, viewer-specific
   response to the new viewer. This is a real, general gotcha for any endpoint whose response shape
   varies by auth state — worth checking for on other viewer-dependent queries later (wishlist
   membership already sidesteps it by being `enabled: Boolean(user)`-gated instead).

### Frontend (`components/product/ReviewsSection.tsx`, `WriteReviewForm.tsx`, `StarRatingInput.tsx`, `pages/admin/ReviewsQueuePage.tsx`)

- PDP gets a `#reviews` section: rating average + 5-row breakdown bar chart, paginated review list
  (verified-purchase badge, own-review pending/rejected status tag), and a "Write a review" CTA that
  redirects a guest to login (`?next=...%23reviews`) or renders `WriteReviewForm` for a signed-in
  eligible customer. The existing PDP rating summary now links to `#reviews`.
- `WriteReviewForm` fetches eligibility first: shows a plain-language ineligibility message, an
  order-picker (only rendered when there's more than one eligible purchase) + `StarRatingInput` +
  title/comment form for a first-time reviewer, or an inline edit card (pre-filled, 24h-window-aware)
  if the user already has a review for this product.
- `StarRatingInput`: a keyboard-accessible (`role="radiogroup"`/`radio`, 44×44px targets) 1–5 star
  picker with hover preview, built new since the existing `RatingStars` component is a read-only
  summary display, not an input control.
- `pages/admin/ReviewsQueuePage.tsx`: status-filtered list (mirrors `OrdersListPage`'s select
  pattern) with inline Approve/Reject/Hide actions per review, added to `AdminLayout`'s nav and
  `/admin/reviews` in the router. Like every other admin nav item in this codebase, it's shown to
  any staff role and relies on the backend's `require("review:review:moderate")` to actually enforce
  who can act — consistent with (not a new deviation from) how Coupons/Users/Orders nav items
  already work here.

### Known gaps / deviations

- **No helpful-vote or report-abuse endpoints** — `helpful_count`/`reported_count` columns exist
  (spec §8.3) and are returned in every response, but nothing increments them yet; scoped out to
  keep this pass to submission + moderation, the two things spec §9.7 actually describes in detail.
- **Review images** (spec §8.3's `reviews.images JSON`) — not built; no upload pipeline exists
  anywhere in the project yet (documented gap since Phase 6's security review).
- **No email on approval/rejection** — spec doesn't explicitly require one for reviews (unlike
  order events in §9.8's table), so none was added; the existing `ConsoleMailBackend` was left
  untouched here.
- **Admin nav item isn't permission-filtered** — see above; a `catalog_manager`/`ops_manager` would
  see the "Reviews" link in the sidebar even though they lack `review:review:moderate` and would get
  a real 403 clicking into it. Pre-existing pattern across every admin nav item, not new.

### Verified

Backend: `pytest tests/test_reviews.py -v` → 9 passed (eligibility, creation, duplicate-order-item
rejection, undelivered-purchase rejection, own-pending-visible/stranger-hidden, admin-approve
rating recompute, the two-separate-deliveries regression case, permission-gated moderation queue,
24h edit-resets-to-pending). Full suite `pytest tests/ -q` → 59 passed (50 prior + 9 new), no
regressions. `tsc -b` and `oxlint` clean on all new frontend files. Live-verified via curl first
(eligibility, create, duplicate rejection, moderation, aggregate recompute), then via curl again
after fixing bugs #1 and #2 above (both were caught by the curl pass, not the browser pass), then
end-to-end through the actual Chrome-driven frontend signed in as `ada@example.com`: guest view of
the PDP shows only the one approved review with the pending one correctly invisible; signing in
reveals both of Ada's own reviews including the pending one (bug #3 above, caught here); opened
"Write a review" and got the pre-filled edit card (not a blank form) for her most recent review
(bug #2's fix, confirmed live); changed the rating 3★→5★, saved, saw the toast and the review
correctly flip back to "Pending"; opened `/admin/reviews`, saw exactly that pending review, clicked
Approve, saw it disappear from the pending filter and the product's live rating jump from "5.0 (1
rating)" to "5.0 (2 ratings)" with the breakdown bar updating to 5★×2 — all observed live, not
assumed from the code.

---

## 15. Git repository + CI/CD (spec §25) ✅

Picked over CMS/banners/support-tickets and a storefront polish pass as the next phase — every
prior phase's "known gaps" list has been citing "no git repository yet" as the reason CI/CD,
dependency scanning, and eventually deployment couldn't start. This phase closes that.

### Git init and the first commit

`git init` at the repo root, then one commit covering everything built through Phase 7 (reviews).
Before committing: extended `.gitignore` (it already excluded `.env`/`data/raw/`/`node_modules`/
`myenv` from earlier sessions) to also cover `backend/.pytest_cache/`, `backend/.ruff_cache/`,
`backend/.coverage`, and `.claude/` (this tool's local session state — personal/machine-specific,
not project source); added a `.gitattributes` (`* text=auto eol=lf`) so the Windows dev machine and
Linux CI runners don't fight over line endings. Verified nothing sensitive would be staged before
committing: `.env` (real `mysql_password`/`kaggle_api_key`) is excluded, `.env.example` only has
placeholders, and grepping the tracked docs confirmed `README.md`/`done.MD` only ever *name* the
secret env vars, never their values. 247 files, one commit.

### CI workflow (`.github/workflows/ci.yml`)

Two jobs, matching spec §25's intent (lint/typecheck/test/build gates) scoped to what this project
actually has tooling for:

- **backend**: a real `mysql:8.0` service container (not mocked), `ruff check`, `pytest` with
  coverage against a fresh `blackcart_test` DB (same isolation the local test suite already uses),
  then a from-scratch `alembic upgrade head → downgrade base → upgrade head → check` cycle against
  a second empty database — spec §8.4's own CI gate, finally actually run for the first time (see
  the real bugs below for why "finally" is doing a lot of work in that sentence). `mypy` also runs
  but as `continue-on-error`, not a hard gate: this is genuinely the first time mypy has ever been
  pointed at this codebase (spec §5.2 names it; done.MD never once lists it as an enforced check
  before now), and a first run surfaces ~25 pre-existing errors — almost all the same shape (mypy
  can't see through Pydantic's `from_attributes=True` duck-typing from an ORM object to a schema
  class). Recorded as a tracked, honest baseline rather than either silently ignoring mypy entirely
  or making CI red on day one for debt that predates this phase.
- **frontend**: `npm ci`, `tsc -b`, `oxlint`, `vitest run`, `vite build`.

Every step in both jobs was actually run locally before being trusted in the YAML — ruff/pytest/tsc/
oxlint/vitest/build all confirmed green, and the alembic sequence specifically simulated end-to-end
against throwaway local databases with the exact same env-var names and command sequence the
workflow file uses (`MYSQL_USER`/`mysql_password`/`MYSQL_HOST`/`MYSQL_PORT` matching `Settings`'
field aliases in `core/config.py` exactly).

### Real bugs found and fixed — the migration chain had never actually been built from scratch

This is the interesting part of this phase. Simulating the CI alembic gate locally (fresh DB →
`alembic upgrade head`) failed immediately, and not with a flake — reproducibly, against multiple
differently-named fresh databases. Root cause, once traced: **the baseline migration
(`3b87e7cbe117_baseline_catalogue_schema`) only ever created one table, `product_images`** — not
`brands`/`categories`/`products`/`product_variants`/`product_attributes`/`inventory_movements`,
despite all of them being declared in `app/models/catalog.py` since early in the project. This had
been invisible for the entire life of the project because **nothing had ever actually built a
database via the full migration chain from empty**: the dev DB (`blackcart`) was seeded once via
`Base.metadata.create_all` before Alembic discipline started, and `tests/conftest.py`'s test
database deliberately also uses `Base.metadata.create_all` (not Alembic) for speed and isolation —
both legitimate choices on their own, but between them, `alembic upgrade head` from a truly empty
database had a zero-percent test-coverage blind spot until this session's CI gate specifically
targeted it.

Once the baseline was traced, two more migrations turned out to be compensating for the same gap:
`cb7fb7c4289c_inventory_and_refunds` was re-creating `inventory_movements` (because the baseline
never had, an earlier autogenerate silently "adopted" it as new), and
`7e6e6ca89efc_discovery_and_search` was hand-adding the `ft_products` FULLTEXT index via raw
`ALTER TABLE` (same reason — the baseline never created it even though the model declared it).
Both would collide (`Table already exists`, `Duplicate key name`) the moment the baseline actually
created these objects correctly.

**Fix**, done properly rather than by hand-transcribing SQL and hoping it matches the models
exactly: temporarily pointed `alembic/env.py`'s `target_metadata` at a scoped `MetaData` containing
only `app.models.catalog`'s seven tables (via SQLAlchemy's `Table.to_metadata()`), then used
`alembic.autogenerate.produce_migrations`/`render_python_code` directly against a genuinely empty
database — this sidesteps `alembic revision --autogenerate`'s own "is the DB at head" precondition
check (which would otherwise refuse to diff an unversioned empty DB against a 6-revision chain) and
just introspects live schema vs. the given metadata. The generated code became the new content of
`3b87e7cbe117`, with the exact same recurring FK-index-drop-ordering fix this project has applied
to every migration since Phase 2 applied proactively to its `downgrade()` too (`ix_products_brand`/
`ix_categories_parent_sort`/`ix_variants_product_active`/`ix_inventory_movements_variant` all lead
with a live FK column). The two downstream migrations then had their now-duplicate
`inventory_movements`/`ft_products` creation removed, each with a comment explaining why. `env.py`'s
temporary scoping hook was reverted afterward — it was a one-off regeneration tool, not something
that should ship. Re-verified: `upgrade head → downgrade base → upgrade head → alembic check` all
clean against a fresh database, `pytest tests/ -q` still 59/59 (unaffected — it never used Alembic
to build its schema), and the real `blackcart`/`blackcart_test` databases were left untouched
throughout (all reproduction happened against disposable, uniquely-named throwaway databases).

This was a real, previously-undetected gap in a project that otherwise prides itself on "verified
live, not assumed" — a genuinely fresh deploy (a new contributor, a new environment, this exact CI
job) would have failed at the very first `alembic upgrade head`, and nothing before this phase would
ever have caught it.

### Known gaps / deviations

- **`mypy` is informational, not a hard gate** — see above; tightening it is real follow-up work
  (fix ~25 pre-existing errors first), not bundled into standing up CI itself.
- **No dependency/SAST scanning in CI** (`pip-audit`, `npm audit`, bandit, trivy, gitleaks) — spec
  §22.7/§25 name these; Phase 6 ran `pip-audit`/`npm audit` manually once (see §13) but neither is
  wired into the workflow yet.
- **No Playwright E2E job, no load testing** — spec §24.3/§24.5's remaining gaps, unchanged.
- **Branch protection isn't (can't be) configured from the repo** — it's a GitHub UI/API action
  requiring an actual GitHub remote and admin access this session doesn't have; step-by-step
  guidance is in `README.md`'s new CI section for the user to apply once the repo is pushed.
- **No remote configured yet** — this is a local-only git repo (one commit) plus a CI workflow file
  that will only actually run once pushed to a GitHub remote with Actions enabled.

### Verified

`ruff check`, `pytest tests/ -q` (59 passed), `tsc -b`, `oxlint`, `npm run test` (32 passed), and
`npm run build` all run locally exactly as the workflow YAML invokes them. The alembic gate was
proven against real throwaway MySQL databases on this machine using the same env var names and
command sequence as the workflow file (not just "the YAML looks right") — this is what actually
caught the three migration bugs above. `git log`/`git status` confirm a clean single-commit history
with nothing untracked or stray left behind (temporary throwaway databases and the one-off
regeneration script were cleaned up; `env.py` reverted to its original form).

---

## Stack deviations from spec §5 (and why)

| Spec says | Built instead | Why |
|---|---|---|
| `asyncmy` MySQL driver | `aiomysql` | Simpler pure-Python install on Windows without a Docker/Linux build toolchain; same SQLAlchemy async interface |
| Docker Compose (MySQL, Redis, ES, MinIO, Celery) | Native local MySQL 8 only | Docker isn't installed on this machine (user chose "run natively" when asked) |
| Redis (cache, sessions, rate limits, Celery broker) | Not present | No Docker/Redis. Auth (§8) now genuinely wants it (rate limiting, `perm_ver` cache) but was built without it — progressive lockout uses a DB table instead, and permissions are re-queried fresh each time |
| Celery + beat | Not present | No background jobs exist yet (no orders/emails/invoices) |
| Elasticsearch + MySQL FULLTEXT fallback | Token-AND/OR `LIKE` relevance search on `title`/`search_keywords` | No Elasticsearch; the spec's own MySQL FULLTEXT ngram fallback was built and empirically found unusable (see §11's "real bug" writeup) and replaced with precise LIKE-based matching — the `ft_products` FULLTEXT index still exists on the schema but isn't queried |
| MailHog (dev) / SMTP (prod) | Console-log mail backend (§8) | No SMTP server in this native setup; verification/reset links are read out of the structured log instead of a real inbox |
| 9-stage ingestion CLI | 1 consolidated script | Faster to build and iterate on for the current scope; `profile`, `media`, `index` stages don't apply without ES/image transcoding |
| Image pipeline → WebP/AVIF, 5 sizes, blurhash | Original Flipkart CDN JPEGs, one upgraded resolution | No image processing pipeline built; CDN images work today but aren't self-hosted or format-optimised |
| Brand fuzzy-merge (rapidfuzz ≥92) | Exact case-insensitive dedup only | Time-boxed; ~325 raw brand strings likely still contain near-duplicates (e.g. differently-truncated variants of the same real brand) that a fuzzy pass would catch |
| Currency: recommendation to convert to BDT at ingest | Left as INR (source currency) | Spec calls this an open question (§30.2), not a decision; converting would mean fabricating an exchange rate, so the real source currency was kept instead |

---

## Dev environment gotcha

`uvicorn --reload` (WatchFiles) on this Windows setup does **not** reliably pick up every file
change — observed it catching 1 reload event out of 4 consecutive backend edits, with no error or
warning, just silently continuing to serve the old code. If a backend change doesn't seem to take
effect, don't assume the code is wrong — check `netstat -ano | grep :8000` for the PID, kill it, and
start uvicorn fresh rather than trusting the reloader.

## Known gaps / next steps

- Git repository now exists (§15) with a working GitHub Actions CI pipeline — no remote pushed yet,
  so Actions haven't actually run in GitHub itself (only locally-simulated, which is how three real
  migration-chain bugs were caught and fixed — see §15). Branch protection needs manual setup once
  pushed (guidance in README).
- Test suite: pytest (59 tests, backend) and vitest (32 tests, frontend) now exist and are green —
  see §12/§14 above for full details, coverage numbers, and the real bugs they caught. No
  Playwright E2E suite yet.
- **Two open security findings, not yet fixed, both deliberately** — see §13 above for full
  detail: react-router 7.18.1 (GHSA-qwww-vcr4-c8h2, CSRF bypass) needs a major-version migration
  across every route/nav call; `starlette` 0.41.3 (~10 CVEs, transitively pinned by
  `fastapi==0.115.6`) needs a FastAPI major-version migration — confirmed risky firsthand when an
  unrelated dependency install silently bumped starlette and broke the app outright.
- Security headers, an in-process rate limiter, sitemap/robots/structured-data SEO, an axe-core
  accessibility sweep (fixed real heading-order and unlabeled-control issues), and a Prometheus
  `/metrics` endpoint are all now built — see §13 above. No OTel tracing, no Grafana, no SAST/DAST,
  no CI/CD — all blocked on missing infra or the still-nonexistent git repository.
- Product `color`/variant model is simplified: each real product got one `base_color` (from the
  source `Color` attribute) with size-only variants, not true multi-colour variant rows — the source
  dataset represents one colour per listing, not a colour×size matrix.
- No rapidfuzz brand deduplication — worth revisiting before this data feeds a recommendation engine,
  since near-duplicate brand strings would fragment brand-based features.
- Initial JS bundle ~137 KB gzipped (spec budget: 180 KB) — fine today, will need route-level code
  splitting once auth/cart/checkout pages land.
- Phase 2 (auth/RBAC) is now functional end-to-end (§8 above) — frontend and backend built in
  separate sessions now verified working together. `getCurrentUser()`'s 404-as-guest shim has been
  removed now that the backend returns real 401s (was previously a temporary workaround, documented
  as a gap in the prior session — now resolved).
- `PasswordStrengthMeter` (frontend) and the server-side policy check in `core/security.py` are both
  independent lightweight heuristics, not zxcvbn — consistent client/server behaviour, but neither
  matches spec §11.3's zxcvbn-score-≥3 requirement exactly.
- Phase 3 (Commerce) is now functional end-to-end (§9 above) — full gap list for what it deviates
  from spec is there, not repeated here.
- Phase 4 (Admin & Operations) is now functional end-to-end for its scoped-down core (§10 above) —
  full gap list (what's deliberately out of scope, no permission-change propagation, no
  idempotency on admin mutations, dashboard is aggregate-queries-only) is there, not repeated here.
- Phase 5 (Search, Recommendations & Discovery) is now functional end-to-end for its scoped-down
  core (§11 above) — full gap list (no Elasticsearch/synonyms/semantic search, on-demand not
  precomputed frequently-bought-together, signed-in-only recently-viewed, single-list wishlist) is
  there, not repeated here. Storefront search is now real token-precise relevance search with a
  broadened fallback, not the plain `LIKE` filter this note used to describe. Phase 6 (Hardening &
  Launch) is the next logical phase per the spec's own roadmap (§29) and hasn't been started.
- Review moderation is now built end-to-end — see §14 below. Support-ticket tooling remains
  entirely unbuilt (no schema, no endpoints, no UI) — out of scope for that session.
