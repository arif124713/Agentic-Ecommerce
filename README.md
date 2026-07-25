# BlackCart

Full spec: [`spec.MD`](./spec.MD). This README covers what's actually built so far and how to run it.

## Status

**Phase 0 (Foundations) + start of Phase 1 (Data & Catalogue)**, per the spec's roadmap (§29). Running
**natively on Windows** — no Docker/Redis/Celery/Elasticsearch yet (see "What's deferred" below).

Built so far:
- FastAPI backend: `Settings`, structured logging, standard error envelope + response envelope
  middleware, request-ID propagation, `/healthz` and `/readyz`, Alembic migrations.
- Catalogue schema (brands, categories, products, variants, images, attributes) with the materialised
  category path from spec §8.3, and public read endpoints (`/products`, `/products/{slug}`,
  `/categories`, `/brands`) with filtering, brand facets, and cursor-free pagination.
- **Real data**: the actual Kaggle Flipkart Fashion Products dataset (30,000 raw records) is
  downloaded and ingested via `backend/scripts/ingest_flipkart.py` — a condensed version of the
  clean → normalise → enrich → load pipeline from spec §7. 8,136 real products loaded after
  quarantining 1,627 malformed rows and deduping ~20K near-identical listings (rejection/dedup
  reasoning in spec §7.3/§7.5). Real Flipkart CDN product photos, titles, brands, prices, and
  descriptions; variant stock/sizes/ratings-count are synthesized per-pid (deterministically seeded)
  since the source dataset has none — this is explicitly what spec §7.3 prescribes for that gap.
  A lighter synthetic-only seed (`scripts/seed.py`) still exists as a fallback.
- React 19 + Vite + TypeScript + Tailwind v4 frontend styled with the exact black/monochrome design
  tokens from spec §18: Home, category listing (PLP) with filters/sort/facets, and product detail (PDP)
  with colour/size selection.

### About the source data

This dataset (see the Kaggle page) is heavily skewed towards menswear (~93% of titles/attributes
resolve to "Men") and has real, spec-anticipated dirtiness: ~325 brand names are truncated at the
source (e.g. "REEB", "Pu", "ECKO Unl" — not a bug introduced here, verified against the raw JSON),
~2,068 records have no brand at all (mapped to "Unbranded"), and some Flipkart CDN image URLs from
this 2021 crawl may be dead. Category taxonomy was hand-mapped from the observed
`(category, sub_category)` pairs into a gender (top) × leaf structure — see `CATEGORY_MAP` in the
ingestion script.

## Running it

**Backend** (from `backend/`, using the existing `myenv` venv at the repo root):
```
../myenv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend** (from `frontend/`):
```
npm run dev
```
Vite proxies `/api/v1/*` to `http://127.0.0.1:8000` (see `vite.config.ts`), so just open
`http://localhost:5173`.

**Database**: uses your local MySQL 8 install (`blackcart` database, credentials from `.env` /
`mysql_password`). Migrations: `alembic upgrade head` from `backend/`. Real data:
`python scripts/ingest_flipkart.py` from `backend/` (re-running truncates and reloads the catalogue
tables; takes ~5s). Raw dataset lives in `data/raw/` (gitignored — see below), quarantine reports in
`data/quarantine/`.

## What's deferred

The full spec assumes Docker Compose orchestrating MySQL, Redis, Elasticsearch, MinIO, and Celery.
Docker isn't installed on this machine, so for now:
- **Redis / Celery** — not wired up. Rate limiting, sessions-as-cache, and background jobs (email,
  invoices, delivery simulation) aren't implemented yet. When ready, install Docker or Redis natively
  and this is the next thing to build.
- **Elasticsearch** — not wired up; the spec's MySQL `FULLTEXT` fallback search isn't implemented yet
  either (current listing uses a basic `LIKE` filter behind the `q` param).
- **Full 9-stage ingestion CLI** (spec §7 specifies separate `fetch`/`profile`/`clean`/`normalise`/
  `enrich`/`media`/`load`/`index`/`verify` subcommands) — condensed into one script for now. No
  image transcoding to WebP/AVIF/5-sizes yet; images are served straight from the Flipkart CDN.
  No brand fuzzy-merge (rapidfuzz) — brands are deduped exactly (case-insensitive) only.
- **Auth, cart, checkout, payments, admin** — not started (Phase 2 onward).

## Secrets

`.env` (git-ignored) holds `mysql_password` and `kaggle_api_key` — both real secrets. `data/raw/`
(the downloaded dataset) is also git-ignored since it's regeneratable and large. Neither should ever
be committed.

## Known gaps to close next

- Initial JS bundle is ~137 KB gzipped against the spec's 180 KB budget — fine today, but there's no
  route-level code splitting yet, so it'll blow the budget once auth/cart/checkout pages land.
- No test suite yet (`pytest` and `vitest`/`playwright` are spec'd but nothing is written).
- No git repository initialized yet.

## Directory layout

Matches spec §27. See `backend/app` and `frontend/src` for the code; `docs/` is scaffolded for ADRs.
