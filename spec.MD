# BlackCart — Enterprise E-Commerce Platform

**Technical & Product Specification**

| Field | Value |
|---|---|
| Document version | 2.0 |
| Status | Draft for implementation |
| Product name | BlackCart (working title) |
| Document owner | Engineering Lead |
| Last updated | 2026-07-23 |
| Intended audience | Backend, Frontend, DevOps, QA, Product |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Goals, Non-Goals & Success Criteria](#2-goals-non-goals--success-criteria)
3. [Personas & Role-Based Access Control](#3-personas--role-based-access-control)
4. [System Architecture](#4-system-architecture)
5. [Technology Stack](#5-technology-stack)
6. [Environments & Configuration](#6-environments--configuration)
7. [Dataset Ingestion Pipeline](#7-dataset-ingestion-pipeline)
8. [Database Design](#8-database-design)
9. [Domain Model & Business Rules](#9-domain-model--business-rules)
10. [API Design](#10-api-design)
11. [Authentication & Session Management](#11-authentication--session-management)
12. [Simulated Payment Gateway](#12-simulated-payment-gateway)
13. [Order Fulfillment & Delivery Simulation](#13-order-fulfillment--delivery-simulation)
14. [Search & Discovery](#14-search--discovery)
15. [Caching Strategy](#15-caching-strategy)
16. [Background Jobs & Scheduling](#16-background-jobs--scheduling)
17. [Frontend Architecture](#17-frontend-architecture)
18. [Design System](#18-design-system)
19. [Responsive Design & Accessibility](#19-responsive-design--accessibility)
20. [SEO & Structured Data](#20-seo--structured-data)
21. [Observability](#21-observability)
22. [Security](#22-security)
23. [Performance Budgets & Capacity](#23-performance-budgets--capacity)
24. [Testing Strategy](#24-testing-strategy)
25. [CI/CD](#25-cicd)
26. [Deployment, Backup & Disaster Recovery](#26-deployment-backup--disaster-recovery)
27. [Repository Structure](#27-repository-structure)
28. [Feature Flags](#28-feature-flags)
29. [Delivery Roadmap](#29-delivery-roadmap)
30. [Risks & Open Questions](#30-risks--open-questions)
31. [Appendices](#31-appendices)

---

## 1. Executive Summary

BlackCart is a full-stack, enterprise-grade e-commerce platform built to production standards. It uses the [Flipkart Fashion Products Dataset](https://www.kaggle.com/datasets/aaditshukla/flipkart-fasion-products-dataset) as seed catalogue data and simulates the payment and logistics layers, but every other subsystem — authentication, cart, checkout, order lifecycle, inventory, admin operations, observability, deployment — is implemented as it would be for a live commercial platform.

The simulated boundaries are deliberately isolated behind interfaces (`PaymentProvider`, `ShippingProvider`) so that swapping in Stripe, SSLCommerz, bKash Checkout, or a real courier API is a configuration and adapter change rather than a rewrite.

**Design philosophy:** monolith-first with clean module boundaries. The backend is a modular monolith (FastAPI) with a strict layering of `api → service → repository → model`. Modules are separated well enough that any bounded context (catalogue, orders, payments, search) could be extracted into its own service later without touching call sites.

**Visual philosophy:** pure black, monochrome, typography-driven. The interface recedes; product photography is the only source of colour.

---

## 2. Goals, Non-Goals & Success Criteria

### 2.1 Goals

| # | Goal |
|---|---|
| G1 | A shopper can discover, filter, search, evaluate, cart, checkout, pay (simulated), track and return an order without a dead end in the flow |
| G2 | An administrator can run the entire business — catalogue, inventory, pricing, promotions, orders, users, content — from a single dashboard |
| G3 | The system is secure by default: OWASP Top 10 addressed with documented, testable controls |
| G4 | The system is observable: every request traceable, every failure alertable, every business metric measurable |
| G5 | The system is deployable end-to-end with one command locally and one pipeline run in CI |
| G6 | Code quality gates (types, lint, coverage, security scan) are enforced automatically, not by convention |

### 2.2 Non-Goals (v1)

- Real money movement, PCI-DSS scope, or storage of real card data
- Multi-tenant / marketplace seller onboarding (single-merchant model only)
- Native mobile applications (responsive web only)
- Real-time chat support (ticket system only)
- Multi-currency and multi-language storefront (single currency, English; architecture leaves room — see §28)
- Kubernetes orchestration (Docker Compose targeted; Helm chart is a stretch goal)

### 2.3 Success Criteria

| Metric | Target |
|---|---|
| Lighthouse Performance (PLP, mobile, throttled) | ≥ 90 |
| Lighthouse Accessibility | ≥ 95 |
| Largest Contentful Paint (p75, 4G) | < 2.5 s |
| API p95 latency (read endpoints, warm cache) | < 200 ms |
| API p95 latency (write endpoints) | < 500 ms |
| Backend unit + integration coverage | ≥ 80 % lines, 100 % of service layer |
| Critical E2E journeys green in CI | 100 % |
| High/critical vulnerabilities in dependency scan | 0 |
| Cold `docker compose up` to seeded, browsable storefront | < 10 minutes |

---

## 3. Personas & Role-Based Access Control

### 3.1 Personas

| Persona | Description | Primary needs |
|---|---|---|
| Guest | Unauthenticated visitor | Browse, search, cart (local), read reviews |
| Customer | Registered shopper | Everything above + checkout, orders, wishlist, reviews, returns |
| Support Agent | Handles tickets and order queries | Read-only orders/users, ticket management, order note creation |
| Catalogue Manager | Merchandiser | Product/category/brand CRUD, inventory, banners, promotions |
| Operations Manager | Fulfilment | Order status transitions, shipments, refunds, invoices |
| Admin | Store operator | All business operations, coupons, analytics |
| Super Admin | Platform owner | All of the above + user role assignment, feature flags, system settings, audit log access |

### 3.2 Permission Model

Permissions are **granular strings** (`resource:action`), grouped into roles. Roles are stored in the DB, permissions are seeded constants. This avoids hard-coded role checks scattered through the codebase.

```
Permission format: <domain>:<resource>:<action>
Examples:
  catalog:product:create
  catalog:product:delete
  order:order:transition
  order:refund:issue
  iam:user:assign_role
  system:feature_flag:write
  system:audit_log:read
```

### 3.3 RBAC Matrix

| Permission | Customer | Support | Catalogue Mgr | Ops Mgr | Admin | Super Admin |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| catalog:product:read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| catalog:product:write | | | ✓ | | ✓ | ✓ |
| catalog:product:delete | | | ✓ | | ✓ | ✓ |
| catalog:inventory:write | | | ✓ | ✓ | ✓ | ✓ |
| order:order:read_own | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| order:order:read_all | | ✓ | | ✓ | ✓ | ✓ |
| order:order:transition | | | | ✓ | ✓ | ✓ |
| order:refund:issue | | | | ✓ | ✓ | ✓ |
| promo:coupon:write | | | ✓ | | ✓ | ✓ |
| review:review:moderate | | ✓ | | | ✓ | ✓ |
| support:ticket:manage | | ✓ | | | ✓ | ✓ |
| cms:page:write | | | ✓ | | ✓ | ✓ |
| iam:user:read | | ✓ | | | ✓ | ✓ |
| iam:user:assign_role | | | | | | ✓ |
| system:feature_flag:write | | | | | | ✓ |
| system:audit_log:read | | | | | ✓ | ✓ |
| analytics:dashboard:read | | | ✓ | ✓ | ✓ | ✓ |

**Enforcement:** a FastAPI dependency `require(*permissions)` resolves the current principal, loads cached role→permission sets from Redis, and returns `403 FORBIDDEN` with a stable error code. Every admin route declares its permissions explicitly; a test asserts that no router under `/api/v1/admin` is missing a permission dependency.

---

## 4. System Architecture

### 4.1 Component Diagram

```
                            ┌───────────────────────┐
                            │       Browser         │
                            │  React 19 SPA (Vite)  │
                            └───────────┬───────────┘
                                        │ HTTPS
                            ┌───────────▼───────────┐
                            │        Nginx          │
                            │  TLS · gzip/brotli    │
                            │  static assets · CSP  │
                            │  rate limit (edge)    │
                            └─────┬───────────┬─────┘
                     /api/v1/*    │           │  /*  (SPA fallback)
                            ┌─────▼─────┐     └──► built frontend bundle
                            │  FastAPI  │
                            │ (uvicorn/ │
                            │ gunicorn) │
                            └──┬──┬──┬──┘
              ┌────────────────┘  │  └────────────────┐
              │                   │                   │
     ┌────────▼────────┐  ┌───────▼──────┐   ┌────────▼────────┐
     │     MySQL 8     │  │    Redis 7   │   │  Elasticsearch  │
     │  primary store  │  │ cache·session│   │   8 (optional)  │
     │                 │  │ ratelimit·   │   │  product index  │
     │                 │  │ celery broker│   └─────────────────┘
     └─────────────────┘  └───────┬──────┘
                                  │
                          ┌───────▼────────┐      ┌──────────────┐
                          │ Celery workers │      │ MinIO / local│
                          │  + Celery beat │◄────►│ object store │
                          └────────────────┘      └──────────────┘
                                  │
                   ┌──────────────┼──────────────┐
                   │              │              │
             email (MailHog)  invoices       image pipeline
             delivery sim     (WeasyPrint)   (Pillow → WebP)
```

### 4.2 Backend Layering

```
app/api/v1/routers/*        HTTP concerns only: validation, status codes, auth deps
        ↓ (DTOs: Pydantic schemas)
app/services/*              Business rules, transactions, orchestration, events
        ↓ (domain entities)
app/repositories/*          Query construction, persistence. Only layer touching Session
        ↓
app/models/*                SQLAlchemy 2.0 declarative mappings
```

**Hard rules enforced by lint/import-linter:**

- Routers must not import `sqlalchemy` or repositories directly.
- Repositories must not import services.
- Models contain no business logic beyond derived properties and constraints.
- Transaction boundaries live in the service layer (`async with uow:`), never in repositories.
- Any cross-module call goes through the target module's *service* interface, never its repository.

### 4.3 Unit of Work & Transactions

A `UnitOfWork` context manager owns the `AsyncSession`, commits on clean exit, rolls back on exception, and collects domain events for post-commit dispatch (Celery tasks are enqueued only after commit, preventing "job runs before the row exists" races).

```python
async with uow:
    order = await order_service.create(uow, cart, address, payment_intent)
    uow.add_event(OrderPlaced(order_id=order.id))
# commit happens here → events dispatched here
```

### 4.4 Request Lifecycle

1. Nginx terminates TLS, applies edge rate limit, adds security headers, proxies `/api/v1/*`.
2. `RequestIDMiddleware` accepts or generates `X-Request-ID`, binds it to a contextvar.
3. `TracingMiddleware` opens an OpenTelemetry span.
4. `AuthMiddleware`/dependency resolves the principal from the `access_token` cookie or `Authorization` header.
5. `CSRFMiddleware` validates the double-submit token on cookie-authenticated state-changing verbs.
6. `RateLimitMiddleware` applies per-principal and per-IP token buckets in Redis.
7. Router → Pydantic request validation → permission dependency → service → repository.
8. Response passes through `ResponseEnvelopeMiddleware` and structured access logging.
9. Errors are converted by a global exception handler into the standard error envelope (§10.5).

---

## 5. Technology Stack

### 5.1 Frontend

| Package | Version | Purpose |
|---|---|---|
| react / react-dom | 19.x | UI runtime, Actions & `use()` for form transitions |
| vite | 6.x | Dev server, build, code splitting |
| typescript | 5.x (`strict: true`) | Type safety |
| tailwindcss | 4.x | Utility styling, design tokens as CSS variables |
| shadcn/ui + radix-ui | latest | Accessible headless primitives |
| @tanstack/react-query | 5.x | Server state, caching, optimistic updates |
| react-router | 7.x | Routing, lazy route modules |
| axios | 1.x | HTTP client with interceptors (refresh, CSRF, request-id) |
| react-hook-form | 7.x | Form state |
| zod | 3.x | Schema validation, shared with generated API types |
| framer-motion | 11.x | Motion, respecting `prefers-reduced-motion` |
| zustand | 5.x | Client-only state (cart drawer, filters, theme, recently viewed) |
| react-hot-toast | 2.x | Notifications |
| embla-carousel-react | 8.x | Hero and product carousels |
| @tanstack/react-virtual | 3.x | Virtualised long lists (admin tables, PLP) |
| recharts | 2.x | Admin analytics charts (monochrome palette) |
| vitest + @testing-library/react | latest | Unit/component tests |
| playwright | 1.x | E2E |
| msw | 2.x | Network mocking in tests and Storybook |

**State ownership rule:** anything that comes from the server lives in React Query. Anything purely local lives in Zustand or component state. There is no duplication of server data into Zustand.

### 5.2 Backend

| Package | Version | Purpose |
|---|---|---|
| python | 3.12 | Runtime |
| fastapi | 0.115+ | HTTP framework |
| uvicorn[standard] / gunicorn | latest | ASGI server, process manager |
| sqlalchemy | 2.0 (async, `asyncmy` driver) | ORM |
| alembic | 1.13+ | Migrations |
| pydantic | 2.x + pydantic-settings | Validation, typed settings |
| redis (redis-py asyncio) | 5.x | Cache, rate limits, locks, sessions |
| celery | 5.4+ | Background tasks |
| celery beat / redbeat | latest | Scheduling |
| passlib[bcrypt] / argon2-cffi | latest | Password hashing (Argon2id primary, bcrypt legacy verify) |
| pyjwt | 2.x | JWT sign/verify |
| elasticsearch[async] | 8.x | Search (optional) |
| pillow + pillow-simd | latest | Image processing |
| weasyprint | latest | PDF invoices |
| slowapi / custom limiter | latest | Rate limiting |
| structlog | latest | Structured JSON logging |
| opentelemetry-* | latest | Tracing, metrics |
| prometheus-fastapi-instrumentator | latest | Metrics endpoint |
| sentry-sdk | latest | Error tracking |
| pytest / pytest-asyncio / httpx | latest | Testing |
| factory-boy / faker | latest | Test data |
| ruff, mypy (strict), bandit, pip-audit | latest | Quality gates |

### 5.3 Data & Infrastructure

| Component | Choice | Notes |
|---|---|---|
| Primary DB | MySQL 8.0+ | InnoDB, `utf8mb4_0900_ai_ci`, strict mode ON |
| Cache/broker | Redis 7 | AOF everysec, `maxmemory-policy allkeys-lru` for cache DB |
| Search | Elasticsearch 8 (optional) | Fallback: MySQL `FULLTEXT` with `ngram` parser |
| Object storage | MinIO (S3 API) or local volume | Abstracted behind `StorageBackend` interface |
| Mail | MailHog (dev) / SMTP (prod) | Abstracted behind `MailBackend` |
| Reverse proxy | Nginx 1.25+ | TLS, caching, compression, security headers |
| Containers | Docker + Docker Compose v2 | Multi-stage builds, non-root users |
| CI/CD | GitHub Actions | See §25 |

---

## 6. Environments & Configuration

### 6.1 Environments

| Env | Purpose | Data | Debug | External calls |
|---|---|---|---|---|
| `local` | Developer machine | Seeded subset (2k products) | on | all mocked |
| `test` | CI | Ephemeral, per-run migrations | on | all mocked |
| `staging` | Pre-prod validation | Full seed + synthetic orders | off | sandbox |
| `production` | Live | Real | off | sandbox (simulated gateway) |

### 6.2 Configuration Rules

- All configuration is read from environment variables through a single `Settings` (pydantic-settings) object. No module reads `os.environ` directly.
- `Settings` validates at startup and **fails fast** on missing/invalid required values.
- Secrets are never committed. `.env.example` documents every key with a safe placeholder.
- Config is immutable at runtime; changing behaviour at runtime is done via feature flags (§28), not env re-reads.

### 6.3 Environment Variable Reference

| Variable | Example | Required | Description |
|---|---|:--:|---|
| `APP_ENV` | `production` | ✓ | Environment name |
| `APP_SECRET_KEY` | `<64-hex>` | ✓ | Master secret for signing |
| `APP_BASE_URL` | `https://blackcart.example` | ✓ | Canonical public URL |
| `API_PREFIX` | `/api/v1` | | API mount path |
| `DATABASE_URL` | `mysql+asyncmy://user:pw@mysql:3306/blackcart` | ✓ | Primary DB DSN |
| `DATABASE_POOL_SIZE` | `20` | | SQLAlchemy pool size |
| `DATABASE_MAX_OVERFLOW` | `10` | | Overflow connections |
| `REDIS_URL` | `redis://redis:6379/0` | ✓ | Cache DB |
| `REDIS_BROKER_URL` | `redis://redis:6379/1` | ✓ | Celery broker |
| `REDIS_RESULT_URL` | `redis://redis:6379/2` | ✓ | Celery results |
| `JWT_ACCESS_TTL_SECONDS` | `900` | | Access token lifetime |
| `JWT_REFRESH_TTL_SECONDS` | `1209600` | | Refresh token lifetime |
| `JWT_ALGORITHM` | `HS256` (or `RS256`) | | Signing algorithm |
| `JWT_PRIVATE_KEY_PATH` | `/run/secrets/jwt_priv.pem` | | Required when RS256 |
| `COOKIE_DOMAIN` | `.blackcart.example` | | Cookie scope |
| `COOKIE_SECURE` | `true` | | Secure flag |
| `COOKIE_SAMESITE` | `lax` | | SameSite policy |
| `CORS_ORIGINS` | `https://blackcart.example` | ✓ | Comma-separated allowlist |
| `SEARCH_BACKEND` | `elasticsearch` \| `mysql` | | Search driver |
| `ELASTICSEARCH_URL` | `http://elasticsearch:9200` | | ES endpoint |
| `STORAGE_BACKEND` | `minio` \| `local` | | Storage driver |
| `S3_ENDPOINT` / `S3_BUCKET` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` | — | | MinIO/S3 config |
| `MAIL_BACKEND` | `smtp` \| `console` | | Mail driver |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | — | | SMTP config |
| `PAYMENT_SIMULATOR_SUCCESS_RATE` | `0.85` | | Probability of simulated success |
| `PAYMENT_SIMULATOR_LATENCY_MS` | `1200` | | Simulated gateway latency |
| `DELIVERY_SIMULATOR_SPEED` | `1.0` | | Time compression for delivery simulation |
| `RATE_LIMIT_DEFAULT` | `100/minute` | | Default bucket |
| `SENTRY_DSN` | — | | Error tracking |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | | Tracing |
| `LOG_LEVEL` | `INFO` | | Logging threshold |
| `ADMIN_API_KEY_PEPPER` | `<hex>` | | Pepper for hashed admin API keys |
| `BACKUP_S3_BUCKET` | `blackcart-backups` | | Backup destination |

---

## 7. Dataset Ingestion Pipeline

### 7.1 Source Data

The Flipkart Fashion Products dataset is a JSON/CSV export with fields approximating:

`_id, actual_price, average_rating, brand, category, crawled_at, description, discount, images, out_of_stock, pid, product_details, seller, selling_price, sub_category, title, url`

It is dirty in predictable ways: prices as strings with currency symbols and thousands separators, `product_details` as a list of single-key dicts, duplicated `pid`s, dead image URLs, HTML entities in titles, inconsistent brand casing, missing ratings.

### 7.2 ETL Stages

Implemented as an idempotent, resumable CLI: `python -m scripts.ingest --stage <name>`.

| Stage | Command | Responsibility |
|---|---|---|
| 1. Acquire | `ingest fetch` | Download/verify dataset, checksum, store raw in `data/raw/` |
| 2. Profile | `ingest profile` | Emit a data-quality report: null rates, cardinality, outliers, duplicate keys |
| 3. Clean | `ingest clean` | Normalise types, strip currency symbols, decode HTML entities, trim, unify casing |
| 4. Normalise | `ingest normalise` | Split into brands / categories / products / variants / images / attributes |
| 5. Enrich | `ingest enrich` | Derive slug, SKU, gender, colour, material, size list, SEO fields, search keywords |
| 6. Media | `ingest media` | Download images, validate, transcode to WebP/AVIF, generate 5 sizes, upload to storage |
| 7. Load | `ingest load` | Bulk `INSERT ... ON DUPLICATE KEY UPDATE` in batches of 1,000 inside transactions |
| 8. Index | `ingest index` | Bulk-index into Elasticsearch, refresh aliases |
| 9. Verify | `ingest verify` | Assert row counts, orphan checks, price sanity, image reachability |

### 7.3 Cleaning Rules

| Field | Rule |
|---|---|
| `title` | Decode entities, collapse whitespace, title-case only if fully upper/lower, max 255 chars |
| `actual_price` / `selling_price` | Strip `₹`, `,`, spaces → `DECIMAL(12,2)`. Reject non-numeric → row quarantined |
| Price sanity | If `selling_price > actual_price`, swap. If either ≤ 0, quarantine |
| `discount` | Recomputed from prices; source value discarded |
| `average_rating` | Clamp to [0,5]; null → `NULL`, never 0 |
| `brand` | Trim, collapse spaces, canonical casing, alias map (`"Adidas Originals"` → `Adidas`), fuzzy-merge (`rapidfuzz` ≥ 92) with a human-reviewed override file |
| `category` / `sub_category` | Mapped to a curated 3-level taxonomy via `data/taxonomy_map.yaml`; unmapped values go to `Uncategorised` and are reported |
| `product_details` | Flattened list-of-dicts → `product_attributes` rows (`name`, `value`), keys normalised (`Ideal For` → `gender`, `Fabric` → `material`) |
| `images` | Deduped, HEAD-checked, first reachable becomes thumbnail; products with zero valid images are quarantined |
| `out_of_stock` | Maps to stock 0; otherwise stock is randomised in a deterministic seeded range (5–200) since the dataset has none |
| Duplicates | Keyed on `(brand, normalised_title)`; keep the record with the most attributes and images |

### 7.4 Derived Fields

- **slug**: `slugify(brand + '-' + title)` + short hash suffix on collision. Immutable once assigned.
- **sku**: `BC-{BRAND3}-{CAT3}-{base36(id)}` for products, `-{SIZE}-{COLOR3}` suffix for variants.
- **gender**: from `Ideal For` attribute → `men | women | unisex | boys | girls | kids`.
- **search_keywords**: brand + title tokens + category path + colour + material, deduped.
- **seo_title / seo_description**: templated, truncated to 60/155 chars.

### 7.5 Quarantine & Reporting

Rejected rows are written to `data/quarantine/{stage}/{timestamp}.jsonl` with a `reason` field. Ingestion prints a summary table and exits non-zero if the rejection rate exceeds a configurable threshold (default 5%), so a corrupted source file cannot silently produce a half-empty catalogue.

---

## 8. Database Design

### 8.1 Conventions

- Table names: plural `snake_case`. Column names: `snake_case`.
- Primary keys: `BIGINT UNSIGNED AUTO_INCREMENT`. Public identifiers in URLs use `slug` or a `ULID` stored in `public_id CHAR(26)` — internal IDs are never exposed in customer-facing URLs for enumeration resistance.
- Money: `DECIMAL(12,2)`, never float. Currency stored per-row as `CHAR(3)` for future multi-currency.
- Timestamps: `TIMESTAMP(6)` UTC, `created_at` / `updated_at` on every table.
- Soft delete: `deleted_at TIMESTAMP(6) NULL` on catalogue and user tables; a global SQLAlchemy filter excludes soft-deleted rows unless explicitly requested.
- Every FK is declared with an explicit `ON DELETE` action; no implicit cascades on financial records (`RESTRICT`).
- Enum-like columns use `VARCHAR` + `CHECK` constraint (portable, migratable) rather than MySQL `ENUM`.
- Optimistic locking: `version INT NOT NULL DEFAULT 0` on `products`, `variants`, `orders`.

### 8.2 Entity Relationship Overview

```
users ─┬─< addresses
       ├─< carts ─< cart_items >─ product_variants
       ├─< orders ─┬─< order_items >─ product_variants
       │           ├─< payments ─< payment_events
       │           ├─< shipments ─< shipment_events
       │           ├─< refunds
       │           └─< order_status_history
       ├─< wishlists ─< wishlist_items >─ products
       ├─< reviews >─ products
       ├─< support_tickets ─< ticket_messages
       ├─< refresh_tokens
       └─< user_roles >─ roles ─< role_permissions >─ permissions

brands ─< products >─ categories (self-referencing tree)
products ─┬─< product_variants ─< inventory_movements
          ├─< product_images
          ├─< product_attributes
          └─< product_tags >─ tags

coupons ─< coupon_redemptions >─ orders
cms_pages, banners, newsletter_subscribers, audit_logs, feature_flags, settings
```

### 8.3 Core Tables

#### users

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | BIGINT UNSIGNED | PK, AI | |
| public_id | CHAR(26) | UNIQUE, NOT NULL | ULID |
| first_name | VARCHAR(80) | NOT NULL | |
| last_name | VARCHAR(80) | NULL | |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Stored lowercase |
| email_verified_at | TIMESTAMP(6) | NULL | |
| phone | VARCHAR(24) | NULL, UNIQUE | E.164 |
| phone_verified_at | TIMESTAMP(6) | NULL | |
| password_hash | VARCHAR(255) | NOT NULL | Argon2id |
| password_changed_at | TIMESTAMP(6) | NOT NULL | Invalidates older tokens |
| mfa_secret | VARBINARY(255) | NULL | Encrypted at rest |
| mfa_enabled | BOOLEAN | NOT NULL DEFAULT 0 | |
| mfa_recovery_codes | JSON | NULL | Hashed |
| status | VARCHAR(20) | NOT NULL DEFAULT 'active' | `active/suspended/deleted` |
| failed_login_count | SMALLINT | NOT NULL DEFAULT 0 | |
| locked_until | TIMESTAMP(6) | NULL | Lockout |
| last_login_at | TIMESTAMP(6) | NULL | |
| last_login_ip | VARBINARY(16) | NULL | Packed |
| marketing_opt_in | BOOLEAN | NOT NULL DEFAULT 0 | |
| created_at / updated_at / deleted_at | TIMESTAMP(6) | | |

Indexes: `UNIQUE(email)`, `UNIQUE(phone)`, `INDEX(status, created_at)`, `UNIQUE(public_id)`.

#### roles / permissions / user_roles / role_permissions

Standard join-table RBAC. `roles(id, code UNIQUE, name, description, is_system)`, `permissions(id, code UNIQUE, description)`, `user_roles(user_id, role_id, granted_by, granted_at)` PK on the pair, `role_permissions(role_id, permission_id)` PK on the pair.

#### addresses

`id, user_id FK→users ON DELETE CASCADE, label, recipient_name, phone, country_code CHAR(2), division, district, city, area, postal_code, street_line1, street_line2, landmark, latitude DECIMAL(10,7), longitude DECIMAL(10,7), is_default_shipping BOOL, is_default_billing BOOL, created_at, updated_at, deleted_at`

Indexes: `INDEX(user_id, is_default_shipping)`. Constraint: at most one default per type per user, enforced in the service layer inside a transaction.

#### brands

`id, name UNIQUE, slug UNIQUE, logo_url, description, is_active, sort_order, created_at, updated_at, deleted_at`

#### categories

`id, parent_id FK→categories ON DELETE RESTRICT, name, slug UNIQUE, path VARCHAR(512), depth TINYINT, description, image_url, icon, is_active, sort_order, seo_title, seo_description, created_at, updated_at, deleted_at`

`path` stores a materialised path (`/men/clothing/t-shirts`) so a subtree query is a single indexed `LIKE '/men/clothing/%'` rather than a recursive CTE on every request. Re-parenting rewrites descendant paths in one statement inside a transaction.

Indexes: `UNIQUE(slug)`, `INDEX(parent_id, sort_order)`, `INDEX(path(191))`.

#### products

| Column | Type | Notes |
|---|---|---|
| id | BIGINT UNSIGNED PK | |
| public_id | CHAR(26) UNIQUE | |
| slug | VARCHAR(255) UNIQUE NOT NULL | URL key |
| title | VARCHAR(255) NOT NULL | |
| subtitle | VARCHAR(255) NULL | |
| description | MEDIUMTEXT NULL | Sanitised HTML subset |
| brand_id | BIGINT UNSIGNED FK→brands RESTRICT | |
| category_id | BIGINT UNSIGNED FK→categories RESTRICT | Leaf category |
| gender | VARCHAR(12) NULL | CHECK in enum |
| material | VARCHAR(120) NULL | |
| base_color | VARCHAR(40) NULL | |
| currency | CHAR(3) NOT NULL DEFAULT 'BDT' | |
| mrp | DECIMAL(12,2) NOT NULL | List price |
| price | DECIMAL(12,2) NOT NULL | Current selling price |
| discount_percent | DECIMAL(5,2) GENERATED ALWAYS AS (...) STORED | Derived, indexed |
| tax_class | VARCHAR(20) NOT NULL DEFAULT 'standard' | |
| rating_avg | DECIMAL(3,2) NULL | Denormalised |
| rating_count | INT UNSIGNED NOT NULL DEFAULT 0 | Denormalised |
| review_count | INT UNSIGNED NOT NULL DEFAULT 0 | Denormalised |
| sold_count | INT UNSIGNED NOT NULL DEFAULT 0 | Denormalised, for "best selling" |
| view_count | INT UNSIGNED NOT NULL DEFAULT 0 | Batched increments |
| stock_total | INT NOT NULL DEFAULT 0 | Sum of variant stock, maintained by trigger/service |
| status | VARCHAR(20) NOT NULL DEFAULT 'draft' | `draft/active/archived` |
| is_featured / is_trending / is_new_arrival | BOOLEAN | Merchandising flags |
| featured_from / featured_until | TIMESTAMP(6) NULL | Scheduling |
| thumbnail_url | VARCHAR(512) NULL | |
| seo_title / seo_description | VARCHAR(255) | |
| search_keywords | TEXT | |
| attributes_json | JSON | Denormalised copy for fast PDP render |
| version | INT NOT NULL DEFAULT 0 | Optimistic lock |
| published_at | TIMESTAMP(6) NULL | |
| created_at / updated_at / deleted_at | TIMESTAMP(6) | |

Indexes:
```sql
UNIQUE KEY uq_products_slug (slug),
KEY ix_products_listing (status, deleted_at, category_id, price),
KEY ix_products_brand (brand_id, status),
KEY ix_products_price (price),
KEY ix_products_rating (rating_avg DESC, rating_count DESC),
KEY ix_products_sold (sold_count DESC),
KEY ix_products_new (published_at DESC),
KEY ix_products_flags (is_featured, featured_from, featured_until),
FULLTEXT KEY ft_products (title, search_keywords) WITH PARSER ngram
```

#### product_variants

`id, product_id FK CASCADE, sku VARCHAR(64) UNIQUE, size VARCHAR(24), color VARCHAR(40), color_hex CHAR(7), barcode, mrp, price, stock INT NOT NULL DEFAULT 0, reserved INT NOT NULL DEFAULT 0, low_stock_threshold INT DEFAULT 5, weight_grams INT, is_active BOOL, position SMALLINT, version INT, created_at, updated_at, deleted_at`

`available = stock - reserved` is a generated stored column with `CHECK (stock >= reserved)` and `CHECK (stock >= 0)`.

Indexes: `UNIQUE(sku)`, `UNIQUE(product_id, size, color)`, `INDEX(product_id, is_active)`, `INDEX(stock)`.

#### product_images

`id, product_id FK CASCADE, variant_id FK SET NULL, url, url_webp, url_avif, blurhash CHAR(40), width, height, bytes, alt_text, sort_order, is_primary, created_at`

`blurhash` powers instant low-quality placeholders without a network round trip.

#### product_attributes

`id, product_id FK CASCADE, name VARCHAR(80), value VARCHAR(255), group_name VARCHAR(60), is_filterable BOOL, sort_order`. Index `(product_id)`, `(name, value)` for facet queries.

#### inventory_movements

Append-only ledger — the single source of truth for stock changes.

`id, variant_id FK RESTRICT, delta INT NOT NULL, reason VARCHAR(30), reference_type VARCHAR(30), reference_id BIGINT, balance_after INT NOT NULL, actor_user_id NULL, note, created_at`

Reasons: `ingest_seed, admin_adjust, order_reserve, order_release, order_fulfil, return_restock, damage, recount`. Any discrepancy between `variants.stock` and the ledger sum is caught by a nightly reconciliation job that alerts rather than silently correcting.

#### carts / cart_items

`carts(id, public_id ULID, user_id FK SET NULL, session_token CHAR(64) NULL, status VARCHAR(20) DEFAULT 'active', currency, coupon_code, expires_at, converted_order_id NULL, created_at, updated_at)`

`cart_items(id, cart_id FK CASCADE, variant_id FK RESTRICT, quantity INT CHECK(quantity BETWEEN 1 AND 10), unit_price_snapshot DECIMAL(12,2), added_at, updated_at)` with `UNIQUE(cart_id, variant_id)`.

Guest carts are keyed by `session_token` in an HttpOnly cookie and merged on login (§9.3). Abandoned carts expire after 30 days via a scheduled job.

#### orders

| Column | Type | Notes |
|---|---|---|
| id | BIGINT UNSIGNED PK | |
| order_number | VARCHAR(24) UNIQUE | `BC-20260723-7F3K9Q` |
| user_id | FK→users RESTRICT | |
| status | VARCHAR(24) NOT NULL | See §9.5 state machine |
| payment_status | VARCHAR(24) NOT NULL | `pending/authorised/paid/failed/refunded/partially_refunded` |
| fulfilment_status | VARCHAR(24) NOT NULL | `unfulfilled/partial/fulfilled` |
| currency | CHAR(3) NOT NULL | |
| subtotal | DECIMAL(12,2) | Sum of line totals |
| discount_total | DECIMAL(12,2) | Coupon + promo |
| shipping_fee | DECIMAL(12,2) | |
| tax_total | DECIMAL(12,2) | |
| grand_total | DECIMAL(12,2) | `CHECK (grand_total >= 0)` |
| paid_total | DECIMAL(12,2) | |
| refunded_total | DECIMAL(12,2) | |
| coupon_code | VARCHAR(40) NULL | |
| shipping_address_json | JSON NOT NULL | **Immutable snapshot**, not an FK |
| billing_address_json | JSON NOT NULL | Snapshot |
| customer_email | VARCHAR(255) | Snapshot |
| customer_phone | VARCHAR(24) | Snapshot |
| customer_note | VARCHAR(500) NULL | |
| internal_note | TEXT NULL | Admin-only |
| promised_delivery_from / _to | DATE | Delivery window |
| delivered_at | TIMESTAMP(6) NULL | |
| cancelled_at / cancel_reason | | |
| placed_ip | VARBINARY(16) | Fraud signals |
| user_agent_hash | CHAR(64) | |
| idempotency_key | CHAR(64) NULL UNIQUE | Prevents duplicate orders |
| version | INT | Optimistic lock |
| created_at / updated_at | TIMESTAMP(6) | |

Address snapshots are stored as JSON because an order must render exactly as it was placed even if the customer later edits or deletes the address. This is a deliberate denormalisation and is documented as such.

Indexes: `UNIQUE(order_number)`, `INDEX(user_id, created_at DESC)`, `INDEX(status, created_at)`, `INDEX(payment_status)`, `UNIQUE(idempotency_key)`.

#### order_items

`id, order_id FK CASCADE, product_id FK RESTRICT, variant_id FK RESTRICT, sku_snapshot, title_snapshot, brand_snapshot, image_snapshot, attributes_snapshot JSON, unit_price, unit_mrp, quantity, discount_amount, tax_amount, line_total, fulfilled_quantity, refunded_quantity, created_at`

Every display field is snapshotted. Renaming a product must never alter an old invoice.

#### order_status_history

`id, order_id FK CASCADE, from_status, to_status, actor_type (system|admin|customer), actor_user_id, reason, metadata JSON, created_at` — the audit trail behind the customer-facing tracking timeline.

#### payments / payment_events

`payments(id, order_id FK RESTRICT, provider VARCHAR(30), method VARCHAR(30), transaction_id VARCHAR(64) UNIQUE, status, amount, currency, card_last4 CHAR(4) NULL, card_brand NULL, authorised_at, captured_at, failed_at, failure_code, failure_message, idempotency_key UNIQUE, raw_response JSON, created_at, updated_at)`

`payment_events(id, payment_id FK CASCADE, event_type, payload JSON, signature, received_at, processed_at)` — the simulated webhook log, structured identically to how a real gateway integration would record callbacks.

**No PAN, CVV, or expiry is ever stored, even simulated.** Only `card_last4` and `card_brand`.

#### shipments / shipment_events

`shipments(id, order_id FK CASCADE, carrier, tracking_number UNIQUE, status, shipped_at, estimated_delivery_at, delivered_at, recipient_signature, created_at)`

`shipment_events(id, shipment_id FK CASCADE, status, location, description, occurred_at, created_at)` — drives the tracking map/timeline.

#### refunds

`id, order_id FK RESTRICT, payment_id FK RESTRICT, amount, reason, status, requested_by_user_id, approved_by_user_id, transaction_id, processed_at, created_at`

#### coupons / coupon_redemptions

`coupons(id, code UNIQUE, description, discount_type ('percent'|'fixed'|'free_shipping'), discount_value, max_discount_amount, min_order_amount, applies_to ('all'|'category'|'brand'|'product'), applies_to_ids JSON, usage_limit_total, usage_limit_per_user, used_count, stackable BOOL, starts_at, expires_at, is_active, created_by, created_at, updated_at)`

`coupon_redemptions(id, coupon_id FK, user_id FK, order_id FK, discount_amount, redeemed_at)` with `INDEX(coupon_id, user_id)` for per-user limit checks and `UNIQUE(order_id, coupon_id)`.

#### reviews

`id, product_id FK CASCADE, user_id FK CASCADE, order_item_id FK SET NULL, rating TINYINT CHECK(1..5), title, comment TEXT, images JSON, is_verified_purchase BOOL, status ('pending'|'approved'|'rejected'|'hidden'), helpful_count, reported_count, moderated_by, moderated_at, created_at, updated_at`

`UNIQUE(product_id, user_id, order_item_id)` — one review per purchased line item.

#### Supporting tables

| Table | Purpose |
|---|---|
| `wishlists` / `wishlist_items` | Named lists, `UNIQUE(wishlist_id, product_id)` |
| `recently_viewed` | `(user_id, product_id, viewed_at)`, capped at 50 per user by job |
| `refresh_tokens` | `id, user_id, token_hash UNIQUE, family_id, parent_id, device_label, ip, user_agent_hash, expires_at, revoked_at, revoked_reason` — rotation with reuse detection |
| `email_verification_tokens`, `password_reset_tokens` | `token_hash`, single-use, TTL, `used_at` |
| `audit_logs` | `actor_user_id, actor_role, action, resource_type, resource_id, before JSON, after JSON, ip, user_agent, request_id, created_at` |
| `login_attempts` | `email_hash, ip, success, reason, created_at` for lockout & alerting |
| `support_tickets` / `ticket_messages` | Subject, status, priority, assignee, threaded messages, attachments |
| `cms_pages` | Slug, title, body, status, SEO fields, published_at |
| `banners` | Placement, image, link, sort, `starts_at`/`ends_at`, active |
| `newsletter_subscribers` | Email, status, confirmed_at, unsubscribed_at, token |
| `tags` / `product_tags` | Free-form merchandising tags |
| `feature_flags` | Key, enabled, rollout_percent, targeting JSON, updated_by |
| `settings` | Key/value store for tunable store config (shipping rates, tax rates) |
| `search_queries` | Logged queries with result counts for zero-result analysis |
| `stock_alerts` | Back-in-stock notification requests |
| `idempotency_keys` | Key, endpoint, user, request_hash, response_snapshot, status, expires_at |

### 8.4 Migration Policy

- Every schema change ships as an Alembic revision with a working `downgrade()`.
- Migrations are **backwards compatible within a release**: expand → migrate data → contract, across at least two deploys for destructive changes.
- No migration may run a long blocking `ALTER` on a large table without `ALGORITHM=INPLACE, LOCK=NONE` verification noted in the revision docstring.
- Data backfills over 100k rows are separate, batched, resumable Celery tasks — never inline in a migration.
- CI asserts `alembic upgrade head` then `alembic downgrade -1` then `upgrade head` succeeds on a fresh DB, and that autogenerate produces an empty diff against the models.

### 8.5 Data Retention

| Data | Retention |
|---|---|
| Orders, payments, invoices | 7 years (financial record) |
| Audit logs | 2 years, then archived to cold storage |
| Access logs | 90 days |
| Guest carts | 30 days |
| Recently viewed | 180 days |
| Deleted accounts | PII anonymised within 30 days of request; order rows retained with pseudonymised customer reference |
| Password reset / verification tokens | Purged 24h after expiry |

---

## 9. Domain Model & Business Rules

### 9.1 Pricing Rules

Order of computation, always performed **server-side**; client-computed totals are never trusted:

```
line_subtotal   = unit_price × quantity
item_discount   = product/category promotion applicable to the line
subtotal        = Σ(line_subtotal − item_discount)
coupon_discount = evaluated against subtotal, capped by max_discount_amount
                  and never exceeding subtotal
discount_total  = Σ item_discount + coupon_discount
taxable_base    = subtotal − discount_total
tax_total       = Σ per-line tax by tax_class (rates from settings)
shipping_fee    = shipping rule engine (§9.2); 0 if free-shipping coupon
grand_total     = taxable_base + tax_total + shipping_fee
```

Rounding: half-up to 2 decimals **at each line**, then summed — matching what the customer sees on each row. All money arithmetic uses `Decimal`, never `float`. A property test asserts `Σ lines + tax + shipping − discounts == grand_total` for randomly generated carts.

**Price integrity:** `cart_items.unit_price_snapshot` is captured when the item is added. At checkout, if the live price differs, the customer is shown an explicit "price changed" confirmation step. Prices are re-read and re-validated at order creation — the snapshot is a UX device, never the authority.

### 9.2 Shipping Rules

Configurable in `settings`, evaluated in priority order:

1. Free-shipping coupon → 0
2. Order subtotal ≥ free-shipping threshold → 0
3. Zone-based flat rate by `division` (inside city / outside city / remote)
4. Weight surcharge above a threshold, computed from variant `weight_grams`
5. Cash-on-delivery surcharge, if applicable

Delivery window: `promised_delivery_from = today + zone_min_days`, `_to = today + zone_max_days`, skipping configured non-working days.

### 9.3 Cart Rules

- Guest carts live under a `cart_session` HttpOnly cookie; they are real DB rows, not localStorage, so they survive device refreshes and can be recovered.
- **Merge on login:** union by variant. For a variant in both carts, `quantity = min(guest_qty + user_qty, max_per_line, available_stock)`. The merged cart's coupon is revalidated and dropped with a toast if no longer eligible.
- Maximum 10 units per line, 50 lines per cart (configurable), enforced by both a DB `CHECK` and the service layer.
- Adding an out-of-stock or inactive variant returns `409 ITEM_UNAVAILABLE` — it is never silently added.
- Cart mutation responses always return the **entire recalculated cart**, so the client never has to guess totals.

### 9.4 Inventory Rules

Stock is protected by an explicit reserve/commit/release cycle:

| Event | Action |
|---|---|
| Checkout initiated | `reserved += qty` under `SELECT ... FOR UPDATE` on the variant rows, sorted by id to avoid deadlocks; reservation TTL 15 min |
| Payment succeeded | `stock -= qty`, `reserved -= qty`, ledger entry `order_fulfil` |
| Payment failed / abandoned / TTL expired | `reserved -= qty`, ledger entry `order_release` (via scheduled sweeper) |
| Order cancelled pre-shipment | Release or restock depending on stage |
| Return accepted | `stock += qty`, ledger entry `return_restock` |

Oversell is structurally prevented by `CHECK (stock >= reserved)` plus row-level locking. A concurrency test fires 50 simultaneous checkouts against a variant with stock 10 and asserts exactly 10 succeed.

Low-stock: when `available <= low_stock_threshold` crosses downward, a domain event triggers an admin notification and flags the variant in the inventory dashboard.

### 9.5 Order State Machine

```
                    ┌──────────┐
                    │  DRAFT   │  (cart converted, payment not attempted)
                    └────┬─────┘
                         ▼
                 ┌───────────────┐   payment failed    ┌──────────┐
                 │ PENDING_      ├────────────────────►│  FAILED  │
                 │ PAYMENT       │                     └──────────┘
                 └───────┬───────┘
                         │ payment success / COD accepted
                         ▼
                   ┌───────────┐      customer/admin      ┌───────────┐
                   │ CONFIRMED ├─────────────────────────►│ CANCELLED │
                   └─────┬─────┘                          └───────────┘
                         ▼                                      ▲
                   ┌───────────┐                                │
                   │ PROCESSING│ (picking)                       │ admin only
                   └─────┬─────┘                                │
                         ▼                                      │
                   ┌───────────┐                                │
                   │  PACKED   ├────────────────────────────────┘
                   └─────┬─────┘
                         ▼
                   ┌───────────┐
                   │  SHIPPED  │
                   └─────┬─────┘
                         ▼
                ┌──────────────────┐        failed attempt
                │ OUT_FOR_DELIVERY ├──────────────┐
                └─────┬────────────┘              ▼
                      ▼                    ┌──────────────┐
                ┌───────────┐              │ DELIVERY_    │
                │ DELIVERED │◄─────────────┤ FAILED       │ (retry ≤3)
                └─────┬─────┘   retry      └──────┬───────┘
                      │                           ▼
        return window │                     ┌───────────┐
                      ▼                     │ RETURNED  │
                ┌───────────┐               └─────┬─────┘
                │ RETURN_   │                     ▼
                │ REQUESTED ├──► RETURN_APPROVED ─► REFUNDED
                └───────────┘         │
                                      └──► RETURN_REJECTED ─► DELIVERED
```

**Transition rules:**

- Transitions are declared in a single `ORDER_TRANSITIONS: dict[Status, set[Status]]` table. Any transition not in the table raises `409 INVALID_TRANSITION`. There is no ad-hoc `order.status = "shipped"` anywhere in the codebase.
- Every transition writes an `order_status_history` row and emits a domain event.
- Customer-initiated cancellation is permitted only in `PENDING_PAYMENT`, `CONFIRMED`, `PROCESSING`. After `PACKED`, cancellation becomes a return request.
- `SHIPPED` requires a shipment row with a tracking number.
- `REFUNDED` requires a refund row whose sum ≤ `paid_total`.
- Return window: 7 days after `delivered_at` (configurable per category).

### 9.6 Coupon Rules

Validation runs as an ordered chain, and the **first failure returns a specific reason code** so the UI can explain precisely why a code was rejected:

`EXISTS → ACTIVE → WITHIN_DATE_WINDOW → GLOBAL_LIMIT → PER_USER_LIMIT → MIN_ORDER_AMOUNT → SCOPE_MATCH → STACKABILITY → COMPUTE`

Redemption is recorded inside the order transaction with `SELECT ... FOR UPDATE` on the coupon row, so a limited coupon cannot be over-redeemed by concurrent checkouts. Cancelled or refunded orders release the redemption.

### 9.7 Review Rules

- Only users with a `DELIVERED` order item for that product may review it (`is_verified_purchase = true`); unverified reviews are disabled in v1.
- New reviews enter `pending` and require moderation before publication; the author always sees their own pending review.
- On approval/rejection, a job recomputes `rating_avg`, `rating_count`, `review_count` for the product and reindexes it.
- Editing within 24 hours returns the review to `pending`.

### 9.8 Domain Events

Events are emitted post-commit and consumed by Celery workers. This keeps the request path fast and makes side effects retryable and observable.

| Event | Consumers |
|---|---|
| `UserRegistered` | Send verification email, welcome sequence |
| `EmailVerified` | Grant first-order coupon |
| `OrderPlaced` | Order confirmation email, invoice generation, ES sold-count update, analytics |
| `PaymentSucceeded` | Commit inventory, transition order, receipt email |
| `PaymentFailed` | Release reservation, recovery email |
| `OrderStatusChanged` | Customer notification, tracking timeline update |
| `ShipmentDispatched` | Tracking email/SMS, start delivery simulation |
| `OrderDelivered` | Review request email (delayed 3 days), return window timer |
| `RefundIssued` | Refund receipt, restock |
| `ProductUpdated` | Reindex search, bust caches, regenerate sitemap entry |
| `StockLow` | Admin alert |
| `StockReplenished` | Back-in-stock notifications to `stock_alerts` |
| `ReviewApproved` | Recompute rating aggregates, reindex |

---

## 10. API Design

### 10.1 Conventions

- Base path `/api/v1`. Breaking changes require `/api/v2`; both versions run side by side for at least one deprecation cycle with `Deprecation` and `Sunset` response headers.
- Resource names plural, nouns only. Verbs appear only as sub-resources for genuine actions: `POST /orders/{n}/cancel`.
- All request and response bodies are `application/json`, `snake_case` keys.
- Public resources are addressed by `slug` or `public_id`, never by internal auto-increment ids.
- `GET` is always safe and cacheable; `PUT` and `DELETE` are idempotent; `POST` becomes idempotent through the `Idempotency-Key` header.
- Timestamps are RFC 3339 UTC with `Z`. Money is a string decimal (`"1299.00"`) plus a `currency` field — never a float.

### 10.2 Standard Response Envelope

Success:
```json
{
  "data": { },
  "meta": { "request_id": "01J8...", "timestamp": "2026-07-23T09:12:44Z" }
}
```

Collections:
```json
{
  "data": [ ],
  "meta": {
    "page": 2, "per_page": 24, "total": 1183, "total_pages": 50,
    "has_next": true, "next_cursor": "eyJpZCI6MTIzfQ",
    "request_id": "01J8...", "timestamp": "..."
  },
  "facets": { "brands": [...], "sizes": [...], "price_range": {...} }
}
```

### 10.3 Pagination

Two modes, chosen per endpoint:

- **Offset** (`?page=&per_page=`) for admin tables where a jump-to-page control is required. `per_page` capped at 100.
- **Cursor** (`?cursor=&limit=`) for the storefront product listing and infinite scroll. The cursor is an opaque base64 of the last sort key + id, which keeps results stable while the catalogue changes underneath and avoids deep-offset scans.

### 10.4 Filtering & Sorting

```
GET /api/v1/products
  ?category=men-tshirts
  &brand=nike,puma
  &price_min=500&price_max=2500
  &rating_min=4
  &gender=men
  &color=black,white
  &size=M,L
  &discount_min=20
  &in_stock=true
  &tag=new-season
  &q=oversized+tee
  &sort=-popularity
  &cursor=...&limit=24
```

Sort keys: `relevance` (default when `q` present), `-popularity` (default otherwise), `price`, `-price`, `-rating`, `-created_at`, `-discount`. `-` prefix means descending. Unknown filter or sort keys return `422` rather than being silently ignored — silent ignoring hides client bugs.

### 10.5 Error Envelope

```json
{
  "error": {
    "code": "COUPON_EXPIRED",
    "message": "This coupon expired on 30 June 2026.",
    "details": [
      { "field": "coupon_code", "issue": "expired", "meta": { "expired_at": "2026-06-30T23:59:59Z" } }
    ],
    "request_id": "01J8...",
    "documentation_url": "https://docs.blackcart.example/errors/COUPON_EXPIRED"
  }
}
```

- `code` is a stable, machine-readable `SCREAMING_SNAKE` string. Clients branch on `code`, never on `message`.
- `message` is human-readable and safe to display; it never leaks stack traces, SQL, internal hostnames, or whether an email exists in the system.
- HTTP status usage: `400` malformed, `401` unauthenticated, `403` unauthorised, `404` not found, `409` state conflict, `410` gone, `422` validation, `423` account locked, `429` rate limited, `500` unexpected, `503` dependency unavailable.

### 10.6 Idempotency

State-changing `POST` endpoints that create money-relevant resources (`/orders`, `/payments`, `/refunds`) require an `Idempotency-Key` header (client-generated UUIDv4). The server stores key → request hash → response snapshot for 24 hours.

- Same key + same request body → the original response is replayed with `Idempotency-Replayed: true`.
- Same key + different body → `409 IDEMPOTENCY_KEY_REUSE`.
- Concurrent request with the same key → `409 REQUEST_IN_PROGRESS`.

### 10.7 Rate Limits

| Scope | Limit | Window | Key |
|---|---|---|---|
| Global anonymous | 100 req | 1 min | IP |
| Global authenticated | 300 req | 1 min | user id |
| `POST /auth/login` | 5 req | 15 min | IP + email hash |
| `POST /auth/register` | 3 req | 1 hour | IP |
| `POST /auth/password/forgot` | 3 req | 1 hour | IP + email hash |
| `POST /auth/refresh` | 30 req | 1 hour | user id |
| `GET /products` (search `q`) | 60 req | 1 min | IP |
| `POST /orders` | 10 req | 10 min | user id |
| `POST /reviews` | 5 req | 1 day | user id |
| Admin write endpoints | 600 req | 1 min | user id |

Implemented as a Redis sliding-window counter. Responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, and `429` responses include `Retry-After`.

### 10.8 Endpoint Catalogue

#### Auth — `/api/v1/auth`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/register` | — | Create account, send verification email |
| POST | `/login` | — | Issue access + refresh cookies |
| POST | `/logout` | ✓ | Revoke current refresh token |
| POST | `/logout-all` | ✓ | Revoke entire token family |
| POST | `/refresh` | cookie | Rotate refresh token, issue new access |
| POST | `/email/verify` | — | Consume verification token |
| POST | `/email/resend` | — | Resend verification (rate limited) |
| POST | `/password/forgot` | — | Send reset link (always `202`, no enumeration) |
| POST | `/password/reset` | — | Consume reset token, revoke all sessions |
| POST | `/password/change` | ✓ | Requires current password |
| GET | `/me` | ✓ | Current principal + permissions |
| POST | `/mfa/setup` | ✓ | Return TOTP secret + QR |
| POST | `/mfa/enable` | ✓ | Verify code, return recovery codes |
| POST | `/mfa/disable` | ✓ | Requires password + code |
| GET | `/sessions` | ✓ | List active devices |
| DELETE | `/sessions/{id}` | ✓ | Revoke a device |

#### Catalogue — public

| Method | Path | Description |
|---|---|---|
| GET | `/products` | Paginated, filtered, faceted listing |
| GET | `/products/{slug}` | Full PDP payload (variants, images, attributes, aggregates) |
| GET | `/products/{slug}/related` | Similar products |
| GET | `/products/{slug}/frequently-bought-together` | Co-purchase recommendations |
| GET | `/products/{slug}/reviews` | Paginated approved reviews with rating histogram |
| GET | `/products/{slug}/availability` | Live per-variant stock (uncached, short TTL) |
| GET | `/categories` | Full tree |
| GET | `/categories/{slug}` | Category + breadcrumbs + facet metadata |
| GET | `/brands` | Brand index |
| GET | `/search` | Search with highlighting |
| GET | `/search/suggest` | Autocomplete: products, brands, categories, queries |
| GET | `/home` | Composed homepage payload (banners, rails), heavily cached |

#### Cart — `/api/v1/cart`

| Method | Path | Description |
|---|---|---|
| GET | `/` | Current cart with recalculated totals |
| POST | `/items` | Add `{variant_id, quantity}` |
| PATCH | `/items/{id}` | Update quantity |
| DELETE | `/items/{id}` | Remove line |
| DELETE | `/` | Empty cart |
| POST | `/coupon` | Apply coupon |
| DELETE | `/coupon` | Remove coupon |
| POST | `/estimate-shipping` | Quote by postal code / division |
| POST | `/merge` | Explicit guest→user merge (also automatic on login) |

#### Checkout & Orders

| Method | Path | Description |
|---|---|---|
| POST | `/checkout/session` | Validate cart, reserve stock, return checkout snapshot + expiry |
| POST | `/checkout/session/{id}/address` | Attach shipping/billing address |
| POST | `/checkout/session/{id}/shipping` | Select shipping method |
| POST | `/orders` | Create order (Idempotency-Key required) |
| GET | `/orders` | Customer order history |
| GET | `/orders/{order_number}` | Order detail with timeline |
| POST | `/orders/{order_number}/cancel` | Cancel if state permits |
| POST | `/orders/{order_number}/reorder` | Rebuild cart from order |
| GET | `/orders/{order_number}/invoice` | PDF stream |
| GET | `/orders/{order_number}/tracking` | Shipment events |
| POST | `/orders/{order_number}/returns` | Request return for selected items |

#### Payments

| Method | Path | Description |
|---|---|---|
| GET | `/payments/methods` | Enabled methods with fees/eligibility |
| POST | `/payments/intents` | Create intent for an order |
| POST | `/payments/intents/{id}/confirm` | Submit simulated payment details |
| GET | `/payments/{transaction_id}` | Payment status (polling) |
| POST | `/payments/webhook/simulator` | Signed simulated callback |
| GET | `/payments/{transaction_id}/receipt` | PDF receipt |

#### Account

`GET/PATCH /profile`, `GET/POST/PATCH/DELETE /addresses[/{id}]`, `POST /addresses/{id}/default`, `GET/POST/DELETE /wishlist[/items/{product_id}]`, `GET /recently-viewed`, `GET/POST /reviews`, `PATCH/DELETE /reviews/{id}`, `POST /reviews/{id}/helpful`, `GET/POST /support/tickets`, `POST /support/tickets/{id}/messages`, `POST /newsletter/subscribe`, `POST /newsletter/unsubscribe`, `POST /stock-alerts`.

#### Admin — `/api/v1/admin`

| Area | Endpoints |
|---|---|
| Dashboard | `GET /dashboard/summary`, `/dashboard/sales-series`, `/dashboard/top-products`, `/dashboard/top-customers`, `/dashboard/funnel` |
| Products | `GET/POST /products`, `GET/PATCH/DELETE /products/{id}`, `POST /products/{id}/restore`, `POST /products/{id}/duplicate`, `POST /products/bulk`, `POST /products/import` (CSV), `GET /products/export`, `POST /products/{id}/images`, `PATCH /products/{id}/images/reorder` |
| Variants | `POST /products/{id}/variants`, `PATCH/DELETE /variants/{id}` |
| Inventory | `GET /inventory`, `POST /inventory/adjust`, `GET /inventory/low-stock`, `GET /inventory/movements` |
| Categories | `GET/POST /categories`, `PATCH/DELETE /categories/{id}`, `POST /categories/reorder` |
| Brands | Full CRUD |
| Orders | `GET /orders`, `GET /orders/{id}`, `POST /orders/{id}/transition`, `POST /orders/{id}/shipment`, `POST /orders/{id}/refund`, `PATCH /orders/{id}/notes`, `GET /orders/export`, `POST /orders/bulk-transition` |
| Users | `GET /users`, `GET/PATCH /users/{id}`, `POST /users/{id}/suspend`, `POST /users/{id}/roles`, `POST /users/{id}/force-password-reset`, `GET /users/{id}/orders` |
| Reviews | `GET /reviews`, `POST /reviews/{id}/approve`, `/reject`, `/hide` |
| Coupons | Full CRUD + `GET /coupons/{id}/redemptions` |
| Content | Banners CRUD, CMS pages CRUD, homepage rail configuration |
| Support | Ticket list, assign, reply, close |
| Analytics | `GET /analytics/sales`, `/revenue`, `/inventory`, `/customers`, `/search-terms`, `/zero-result-queries`, `/conversion` |
| System | `GET /audit-logs`, `GET/PATCH /feature-flags`, `GET/PATCH /settings`, `POST /search/reindex`, `POST /cache/purge` |

#### Operational

`GET /healthz` (liveness, no dependencies), `GET /readyz` (checks DB, Redis, ES, storage), `GET /metrics` (Prometheus, internal network only), `GET /version` (git SHA, build time), `GET /docs` & `/openapi.json` (disabled in production or behind admin auth).

### 10.9 Sample Payloads

**`POST /api/v1/orders`**
```json
{
  "checkout_session_id": "01J8XK2P9V3QZ7M4N6R8T0W1Y",
  "shipping_address_id": 42,
  "billing_address_id": 42,
  "shipping_method": "standard",
  "payment_method": "bkash",
  "customer_note": "Please call before delivery",
  "accept_terms": true
}
```

**`201 Created`**
```json
{
  "data": {
    "order_number": "BC-20260723-7F3K9Q",
    "status": "pending_payment",
    "payment_status": "pending",
    "currency": "BDT",
    "totals": {
      "subtotal": "4297.00",
      "discount_total": "429.70",
      "shipping_fee": "60.00",
      "tax_total": "193.37",
      "grand_total": "4120.67"
    },
    "items": [
      {
        "sku": "BC-NIK-TSH-3F9K2-M-BLK",
        "title": "Nike Sportswear Oversized Tee",
        "variant": { "size": "M", "color": "Black" },
        "unit_price": "1299.00",
        "quantity": 2,
        "line_total": "2598.00",
        "image": "https://cdn.../nike-tee-400.webp"
      }
    ],
    "payment": {
      "intent_id": "pi_01J8XK...",
      "next_action": { "type": "redirect_to_simulator", "url": "/checkout/pay/pi_01J8XK..." }
    },
    "promised_delivery": { "from": "2026-07-26", "to": "2026-07-29" }
  },
  "meta": { "request_id": "01J8XK...", "timestamp": "2026-07-23T09:12:44Z" }
}
```

### 10.10 OpenAPI & Client Generation

FastAPI generates the OpenAPI 3.1 schema. CI runs `openapi-typescript` to produce `frontend/src/types/api.d.ts`, and fails the build if the committed types differ from the generated ones. This makes backend/frontend contract drift a build error rather than a runtime bug.

---

## 11. Authentication & Session Management

### 11.1 Token Design

| Token | Lifetime | Storage | Claims |
|---|---|---|---|
| Access | 15 min | HttpOnly, Secure, SameSite=Lax cookie (`access_token`) | `sub` (public_id), `sid`, `roles`, `perm_ver`, `iat`, `exp`, `jti`, `iss`, `aud` |
| Refresh | 14 days (sliding, absolute max 90 days) | HttpOnly, Secure, SameSite=Strict, `Path=/api/v1/auth` cookie | `sub`, `family`, `jti`, `exp` |
| CSRF | Matches session | Non-HttpOnly cookie + `X-CSRF-Token` header | Random 32 bytes |

Cookies are the default transport (immune to XSS token theft); `Authorization: Bearer` is accepted for API clients and admin API keys. Only the cookie path enforces CSRF.

### 11.2 Refresh Rotation & Reuse Detection

Every refresh issues a new refresh token and revokes the old one, linked by `family_id`. If a token that has already been rotated is presented again, the entire family is revoked immediately, all sessions for that user are terminated, a `SESSION_REUSE_DETECTED` security event is logged, and the user is emailed. This turns a stolen refresh token from a persistent compromise into a single detectable event.

### 11.3 Password Policy

- Minimum 12 characters; maximum 128 (bcrypt-style truncation avoided by Argon2id).
- Requires at least three of: lowercase, uppercase, digit, symbol — rather than all four, which research shows pushes users toward predictable patterns.
- Blocklist check against the top 100k breached passwords (local bloom filter) and against the user's own email/name.
- zxcvbn strength score ≥ 3 required; the meter is advisory in UI and enforced server-side.
- Hashing: Argon2id (`time_cost=3, memory_cost=64MB, parallelism=4`), rehash-on-login when parameters change. bcrypt hashes from legacy imports verify and upgrade transparently.
- Password change or reset revokes all refresh tokens except the current session and sends a notification email.

### 11.4 Account Protection

- Progressive lockout: after 5 failed attempts within 15 minutes, lock for 15 minutes; escalating to 1 hour after 10. Lockout is keyed on `(email_hash, ip)` to prevent an attacker locking out a victim by guessing from another IP.
- Login responses are constant-time and identical for "unknown email" and "wrong password" (`INVALID_CREDENTIALS`).
- All auth emails (verification, reset, new-device login, password change) are transactional and rate limited.
- Optional TOTP MFA with 10 single-use recovery codes; mandatory for any user holding an admin role.
- New-device detection via `user_agent_hash` + IP ASN; triggers an email notification.

### 11.5 Admin API Keys

Machine access to admin endpoints uses API keys: displayed once at creation, stored as `argon2(key + pepper)`, scoped to a permission subset, IP-allowlistable, with expiry and last-used tracking. Sent as `X-API-Key`. Keys never grant `iam:*` or `system:*` permissions.

---

## 12. Simulated Payment Gateway

### 12.1 Principles

The simulator implements the same interaction shape as a real PSP — intent creation, client confirmation, asynchronous webhook, idempotent capture — so the integration code is production-shaped. It is isolated behind:

```python
class PaymentProvider(Protocol):
    async def create_intent(self, order: Order, method: PaymentMethod) -> PaymentIntent: ...
    async def confirm(self, intent_id: str, payload: ConfirmPayload) -> PaymentResult: ...
    async def capture(self, transaction_id: str, amount: Decimal) -> PaymentResult: ...
    async def refund(self, transaction_id: str, amount: Decimal, reason: str) -> RefundResult: ...
    def verify_webhook(self, body: bytes, signature: str) -> WebhookEvent: ...
```

`SimulatedProvider` is the v1 implementation. A `StripeProvider` can be dropped in without touching the order service.

### 12.2 Supported Methods

| Method | Behaviour |
|---|---|
| Dummy Visa / MasterCard | Card form with Luhn validation; outcome driven by test card numbers |
| bKash / Nagad / Rocket | Redirect-style page → OTP entry → callback |
| UPI | VPA entry → simulated approval delay |
| Stripe sandbox simulation | Hosted-page look-alike with 3DS challenge step |
| Cash on Delivery | No gateway call; order confirmed immediately, `payment_status=pending` until delivery, optional COD fee and order-value cap |

### 12.3 Deterministic Test Cases

Deterministic outcomes make E2E tests reliable; random outcomes are used only in demo mode.

| Input | Outcome |
|---|---|
| Card `4242 4242 4242 4242` | Success |
| Card `4000 0000 0000 0002` | Declined (`CARD_DECLINED`) |
| Card `4000 0000 0000 9995` | Insufficient funds |
| Card `4000 0000 0000 0069` | Expired card |
| Card `4000 0000 0000 3220` | Requires 3DS challenge, then success |
| Card `4000 0000 0000 0119` | Processing error (`GATEWAY_ERROR`) |
| Wallet OTP `123456` | Success |
| Wallet OTP `000000` | Failure |
| Any other input | Outcome sampled at `PAYMENT_SIMULATOR_SUCCESS_RATE` |

### 12.4 Payment Lifecycle

```
create_intent → INTENT_CREATED (order: PENDING_PAYMENT, stock reserved)
      ↓ customer confirms
   PROCESSING  (simulated latency, poll or SSE)
      ↓
  ┌───────────┬──────────────┬────────────┐
  ▼           ▼              ▼            ▼
SUCCEEDED   FAILED      REQUIRES_ACTION  EXPIRED (15 min)
  ↓           ↓              ↓            ↓
capture   release stock   3DS challenge  release stock
  ↓                          ↓
order CONFIRMED         retry confirm
```

### 12.5 Webhook Simulation

After a terminal outcome, a Celery task posts a signed event to `POST /api/v1/payments/webhook/simulator` with `X-Signature: t=<ts>,v1=<hmac_sha256>`. The handler:

1. Verifies the HMAC in constant time and rejects timestamps older than 5 minutes (replay protection).
2. Deduplicates on `event_id`.
3. Records a `payment_events` row before processing.
4. Applies the state change idempotently, tolerating out-of-order delivery (a `succeeded` after a `processing` is fine; a `processing` after `succeeded` is ignored).
5. Returns `200` quickly; heavy work is queued.

Retries follow real PSP semantics: exponential backoff at 1m, 5m, 30m, 2h, 6h, then dead-letter with an admin alert.

### 12.6 Transaction IDs & Receipts

Format: `TXN` + base32(ULID) truncated to 12, e.g. `TXN938472983KQ`. Guaranteed unique by DB constraint with retry.

Receipts are PDFs generated by WeasyPrint from an HTML template, stored in object storage, and served through a short-lived signed URL. They contain order number, transaction id, masked method (`•••• 4242`), itemised totals, tax breakdown, merchant details, and a `SIMULATED — NOT A REAL PAYMENT` watermark in non-production environments.

---

## 13. Order Fulfillment & Delivery Simulation

### 13.1 Simulator

A `ShippingProvider` interface with a `SimulatedCarrier` implementation. On `ShipmentDispatched`, a Celery chain schedules the event sequence, compressed by `DELIVERY_SIMULATOR_SPEED` (in dev, a 3-day delivery plays out in ~3 minutes):

| Offset | Event | Location |
|---|---|---|
| T+0 | Shipment created, label generated | Origin warehouse |
| T+2h | Picked up by carrier | Origin hub |
| T+8h | In transit | Sorting facility |
| T+20h | Arrived at destination hub | Destination city |
| T+30h | Out for delivery | Local depot |
| T+34h | Delivered | Customer address |

Configurable failure injection: a small percentage of shipments produce `DELIVERY_FAILED` (recipient unavailable) with up to 3 automatic retries, then return-to-sender — so the failure paths in the UI are exercised rather than theoretical.

### 13.2 Tracking Number

Format `BC` + 10 alphanumeric + check digit (mod-36), e.g. `BC7K3M9QX2P4`. Displayed with a copy button, a vertical timeline, and an estimated-delivery countdown.

### 13.3 Admin Fulfilment Workflow

1. New orders appear in an **Ops queue** with SLA colouring (breach risk highlighted).
2. Bulk-select → transition to `PROCESSING`.
3. Pick list PDF generated per batch, grouped by warehouse location.
4. Packing slip printed; scan-to-confirm each SKU (barcode input field).
5. Transition to `PACKED`, then `SHIPPED` with carrier + tracking number → simulation starts.
6. Delivery confirmation flows back through webhook-style events.
7. Exceptions (failed delivery, damaged, lost) open a support ticket automatically.

---

## 14. Search & Discovery

### 14.1 Backends

`SEARCH_BACKEND` selects the driver behind a `SearchBackend` interface. Both implementations must satisfy the same contract test suite, so the fallback is genuinely equivalent in behaviour, only weaker in ranking.

**Elasticsearch (preferred)** — index `products_v{n}` behind alias `products`. Reindex writes to a new version and atomically swaps the alias; zero downtime, instant rollback.

**MySQL fallback** — `FULLTEXT ... WITH PARSER ngram` in boolean mode, with scoring approximated by `MATCH() AGAINST()` relevance plus popularity boosts. Facets computed by parallel `GROUP BY` queries against the filtered set, cached.

### 14.2 Index Mapping (Elasticsearch)

```json
{
  "settings": {
    "analysis": {
      "analyzer": {
        "product_text": {
          "tokenizer": "standard",
          "filter": ["lowercase", "asciifolding", "fashion_synonyms", "english_stop", "english_stemmer"]
        },
        "autocomplete": {
          "tokenizer": "standard",
          "filter": ["lowercase", "asciifolding", "edge_ngram_2_20"]
        }
      },
      "filter": {
        "fashion_synonyms": {
          "type": "synonym_graph",
          "synonyms_path": "analysis/fashion_synonyms.txt"
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "id":            { "type": "keyword" },
      "slug":          { "type": "keyword" },
      "title":         { "type": "text", "analyzer": "product_text",
                         "fields": { "auto": { "type": "text", "analyzer": "autocomplete" },
                                     "raw": { "type": "keyword" } } },
      "description":   { "type": "text", "analyzer": "product_text" },
      "brand":         { "type": "text", "fields": { "raw": { "type": "keyword" } } },
      "category_path": { "type": "keyword" },
      "gender":        { "type": "keyword" },
      "colors":        { "type": "keyword" },
      "sizes":         { "type": "keyword" },
      "material":      { "type": "keyword" },
      "tags":          { "type": "keyword" },
      "price":         { "type": "scaled_float", "scaling_factor": 100 },
      "discount_percent": { "type": "float" },
      "rating_avg":    { "type": "half_float" },
      "rating_count":  { "type": "integer" },
      "sold_count":    { "type": "integer" },
      "in_stock":      { "type": "boolean" },
      "status":        { "type": "keyword" },
      "published_at":  { "type": "date" },
      "popularity":    { "type": "rank_feature" }
    }
  }
}
```

Synonyms cover fashion vocabulary: `tee ⇄ t-shirt ⇄ tshirt`, `trousers ⇄ pants`, `kurti ⇄ kurta`, `sneakers ⇄ trainers ⇄ shoes`, `frock ⇄ dress`, plus common misspellings.

### 14.3 Query Strategy

- `multi_match` `best_fields` across `title^5`, `brand^3`, `category_path^2`, `tags^2`, `description^1`.
- Fuzziness `AUTO` with `prefix_length: 2` — tolerant of typos without matching nonsense on short queries.
- `rank_feature` boost on `popularity` (log saturation) and a mild recency boost on `published_at`.
- Post-filters for facet computation so facet counts reflect the un-narrowed set for the facet being displayed.
- Zero results → suggestion via `phrase_suggester` ("Did you mean…"), then a fallback broadened query, and the query is logged to `search_queries` for merchandising review.
- Every search response is capped at 10,000 results; deeper access uses `search_after`.

### 14.4 Autocomplete

`GET /search/suggest?q=nik` returns, in one response: top 5 matching products (with thumbnail and price), top 3 brands, top 3 categories, and up to 4 popular past queries. Debounced 200 ms client-side, cached 60 s server-side.

### 14.5 Recommendations

| Rail | Algorithm (v1) |
|---|---|
| Similar products | `more_like_this` on title/category/brand, filtered to same gender and ±40 % price band |
| Frequently bought together | Co-occurrence counts from `order_items`, computed nightly into a `product_affinity` table, min support threshold 3 |
| Recently viewed | Per-user list from `recently_viewed`, client-hydrated |
| Trending | Views + sales in a rolling 7-day window, decay-weighted |
| Personalised home rail | Category affinity from the user's view/purchase history; falls back to trending for new users |

Semantic search (embedding-based kNN) is specified as an optional phase 5 enhancement behind a feature flag, using a sentence-transformer model to populate a `dense_vector` field.


---

## 15. Caching Strategy

### 15.1 Layers

| Layer | Scope | TTL | Invalidation |
|---|---|---|---|
| Browser | Hashed static assets | 1 year, immutable | Filename hash |
| Browser | HTML shell | no-cache | — |
| CDN / Nginx | Product images | 30 days | Versioned URL |
| Nginx micro-cache | `GET /api/v1/products`, `/home` | 10 s | Time |
| Redis | Application cache | See below | Event-driven |
| React Query | Client server-state | `staleTime` per query | Mutation invalidation |
| SQLAlchemy | Identity map (per request) | request | — |

### 15.2 Redis Key Design

```
bc:v1:product:detail:{slug}                 TTL 10m
bc:v1:product:list:{filter_hash}            TTL 2m
bc:v1:product:facets:{filter_hash}          TTL 5m
bc:v1:category:tree                         TTL 1h
bc:v1:brand:list                            TTL 1h
bc:v1:home:payload:{variant}                TTL 5m
bc:v1:search:suggest:{q}                    TTL 1m
bc:v1:user:{id}:permissions                 TTL 15m
bc:v1:cart:{cart_id}:totals                 TTL 60s
bc:v1:ratelimit:{scope}:{key}               TTL window
bc:v1:lock:{resource}                       TTL 30s
bc:v1:idem:{key}                            TTL 24h
```

A global `bc:v1:` prefix means an emergency full flush is one `SCAN`-and-delete of a known namespace, and a version bump (`v1` → `v2`) invalidates everything atomically on deploy when cache shapes change.

### 15.3 Invalidation Rules

- Product write → delete `product:detail:{slug}`, purge `product:list:*` and `facets:*` by tag set, reindex ES, regenerate sitemap chunk.
- Category or brand write → purge `category:tree` / `brand:list` and all list caches.
- Order placed → invalidate the affected variants' availability keys only (not whole listings).
- **Never cache:** cart contents keyed by anything other than cart id, checkout sessions, payment status, admin endpoints, anything containing PII.

### 15.4 Stampede Protection

Hot keys use a lock-and-recompute pattern: on miss, acquire `bc:v1:lock:{key}` with a 30 s TTL; the winner recomputes while others serve the stale value (a soft TTL is stored alongside the value) or wait briefly. Prevents a cold homepage cache from producing a thundering herd against MySQL.

---

## 16. Background Jobs & Scheduling

### 16.1 Queues

| Queue | Concurrency | Contents |
|---|---|---|
| `critical` | 8 | Payment webhooks, order transitions, inventory commits |
| `default` | 6 | Emails, invoice generation, search indexing |
| `media` | 4 | Image processing, thumbnail generation |
| `bulk` | 2 | CSV import/export, dataset ingestion, backfills |
| `periodic` | 2 | Scheduled maintenance |

### 16.2 Task Reliability

- `acks_late=True`, `reject_on_worker_lost=True` — a task killed mid-flight is redelivered.
- All tasks are idempotent; each takes a natural key and checks for prior completion.
- Retry policy: exponential backoff with jitter, `max_retries=5`, then dead-letter queue with a Sentry alert.
- `task_time_limit` and `soft_time_limit` set per queue so a hung task cannot occupy a worker indefinitely.
- Tasks accept primitive arguments only (ids, not ORM objects) and reload state inside the task.
- Every task logs with the originating `request_id` for end-to-end tracing.

### 16.3 Scheduled Jobs (Celery Beat)

| Schedule | Task |
|---|---|
| Every minute | Expire stale checkout sessions, release reservations |
| Every 5 min | Process pending payment webhooks, retry dead letters |
| Every 15 min | Flush batched view counters to DB |
| Hourly | Refresh trending products, recompute homepage rails |
| Hourly | Reconcile inventory ledger vs. variant stock, alert on drift |
| Every 6 h | Reindex products changed since last run |
| Daily 02:00 | Full MySQL backup → object storage, verify restore on a scratch DB |
| Daily 02:30 | Rebuild `product_affinity` (frequently bought together) |
| Daily 03:00 | Purge expired tokens, old idempotency keys, expired guest carts |
| Daily 04:00 | Regenerate sitemap.xml + image sitemap |
| Daily 09:00 | Low-stock digest email to catalogue managers |
| Daily 10:00 | Abandoned-cart recovery emails (carts idle 24 h, max 2 per cart) |
| Daily 11:00 | Review-request emails for orders delivered 3 days ago |
| Weekly Mon 06:00 | Business summary email, ES index health check, dependency audit |
| Monthly | Archive audit logs older than 2 years, rotate API key usage report |

---

## 17. Frontend Architecture

### 17.1 Route Map

| Path | Page | Rendering notes |
|---|---|---|
| `/` | Home | Prefetched hero, lazy rails below the fold |
| `/c/:categorySlug` | Category listing | Cursor pagination, filters in URL |
| `/search?q=` | Search results | Debounced, URL-synced |
| `/p/:productSlug` | Product detail | Critical image preloaded, reviews lazy |
| `/cart` | Cart | Optimistic quantity updates |
| `/checkout` | Checkout | 3-step wizard, guarded route |
| `/checkout/pay/:intentId` | Payment simulator | Isolated route, no nav chrome |
| `/order/confirmation/:orderNumber` | Confirmation | |
| `/account` | Dashboard | Nested layout |
| `/account/orders`, `/orders/:orderNumber` | Orders, detail + tracking | |
| `/account/addresses`, `/wishlist`, `/reviews`, `/settings`, `/support` | Account sections | |
| `/auth/login`, `/register`, `/forgot`, `/reset/:token`, `/verify/:token` | Auth | |
| `/pages/:slug` | CMS page | |
| `/admin/*` | Admin SPA | Separate lazy bundle, role-guarded |

**URL is the source of truth for listing state.** Filters, sort, and pagination live in the query string so results are shareable, bookmarkable, and back-button correct.

### 17.2 Data Layer

- One `apiClient` (Axios) with interceptors: attach `X-Request-ID` and CSRF token; on `401`, attempt a single refresh and replay the original request, with a mutex so concurrent 401s trigger only one refresh; on repeated failure, clear the session and redirect to login preserving `returnTo`.
- React Query key convention: `['products', 'list', filters]`, `['products', 'detail', slug]`, `['cart']`, `['orders', 'list', params]`. Invalidation targets the narrowest prefix that is actually stale.
- `staleTime`: 5 min for catalogue, 0 for cart/orders/checkout.
- Optimistic updates for cart quantity, wishlist toggle, and review helpfulness, each with a rollback on error and a toast.
- Prefetch on hover/viewport for product cards, so PDP navigation feels instant.

### 17.3 Component Organisation

```
components/
  ui/            shadcn primitives (button, dialog, sheet, input, ...)
  layout/        Header, Footer, MobileNav, AdminShell, Breadcrumbs
  product/       ProductCard, ProductGrid, Gallery, VariantSelector,
                 PriceBlock, RatingStars, StockBadge, ReviewList
  cart/          CartDrawer, CartLine, CouponInput, OrderSummary
  checkout/      AddressForm, AddressBook, ShippingSelector,
                 PaymentMethodPicker, ReviewStep
  filters/       FilterSidebar, FilterChips, PriceRange, ActiveFilters
  feedback/      EmptyState, ErrorState, Skeleton*, Toast
  admin/         DataTable, StatCard, ChartCard, BulkActionBar, StatusPill
```

Rules: components under `ui/` are presentational and take no data-fetching responsibility. Feature components may use hooks. Pages compose; they do not style.

### 17.4 Forms

`react-hook-form` + `zodResolver`, with Zod schemas **derived from the generated OpenAPI types** where possible so client validation cannot drift from server validation. Server field errors from the `422` envelope are mapped back onto form fields by `details[].field`. Submit buttons disable and show inline spinners; double submission is additionally guarded by an idempotency key on money-relevant forms.

### 17.5 Performance Techniques

- Route-level code splitting; the admin bundle is never shipped to shoppers.
- `@tanstack/react-virtual` for grids over 100 items and all admin tables.
- Images: `<picture>` with AVIF → WebP → JPEG, `srcset` at 5 widths, `loading="lazy"` except the LCP image which is `fetchpriority="high"` and preloaded, `width`/`height` always set to eliminate CLS, blurhash placeholder while loading.
- Fonts: variable font, `font-display: swap`, subset, self-hosted, preloaded.
- `content-visibility: auto` on below-fold sections.
- Bundle budget enforced in CI: initial JS ≤ 180 KB gzipped, total CSS ≤ 40 KB gzipped.

### 17.6 Error Handling

Error boundaries at route level and around each independent rail, so a failing recommendations widget cannot blank the product page. Every error state offers a retry. Network failures are distinguished from application errors in the UI copy. A global boundary reports to Sentry with the `request_id` for correlation with backend logs.

---

## 18. Design System

### 18.1 Colour Tokens

```css
:root {
  /* Surfaces */
  --bg:              #000000;  /* page background */
  --surface:         #0B0B0B;  /* cards, panels */
  --surface-raised:  #111111;  /* hover, popovers, modals */
  --surface-sunken:  #060606;  /* wells, inputs */

  /* Text */
  --text:            #FFFFFF;  /* primary — 21:1 on --bg */
  --text-secondary:  #BDBDBD;  /* secondary — 11.4:1 on --bg */
  --text-tertiary:   #8A8A8A;  /* metadata — 5.3:1, large text only */
  --text-disabled:   #5A5A5A;  /* non-informational only */

  /* Lines */
  --border:          #202020;
  --border-strong:   #333333;
  --focus-ring:      #FFFFFF;

  /* Accent (monochrome) */
  --accent:          #FFFFFF;
  --accent-fg:       #000000;

  /* Semantic — desaturated, used sparingly, never as the sole signal */
  --success:         #4ADE80;
  --warning:         #FACC15;
  --danger:          #F87171;
  --info:            #93C5FD;

  /* Effects */
  --overlay:         rgba(0,0,0,0.72);
  --shadow-1:        0 1px 2px rgba(0,0,0,0.6);
  --shadow-2:        0 8px 24px rgba(0,0,0,0.7);
  --radius-sm: 4px; --radius: 8px; --radius-lg: 16px; --radius-full: 9999px;
}
```

**Rule:** the storefront chrome is monochrome. Semantic colours appear only in status pills, form validation, and admin charts — and are always paired with an icon or text label so colour is never the only carrier of meaning (WCAG 1.4.1).

Because pure black backgrounds can cause smearing on OLED and harsh halation for some readers, cards sit on `--surface` rather than `--bg`, and long-form text is `--text-secondary` at a slightly reduced weight rather than pure white.

### 18.2 Typography

| Token | Size / Line height | Weight | Use |
|---|---|---|---|
| `display` | 56 / 60 (clamp to 36 mobile) | 600 | Hero |
| `h1` | 36 / 44 | 600 | Page title |
| `h2` | 28 / 36 | 600 | Section |
| `h3` | 22 / 30 | 500 | Card title |
| `body-lg` | 18 / 28 | 400 | Lead paragraph |
| `body` | 16 / 26 | 400 | Default |
| `body-sm` | 14 / 22 | 400 | Secondary |
| `caption` | 12 / 18 | 400 | Metadata |
| `price` | 20 / 24 | 600, tabular-nums | Prices |
| `mono` | 14 / 20 | 400 | Order/tracking numbers |

Typeface: a geometric/neo-grotesque variable font (Inter or Geist) with `font-feature-settings: "tnum"` on all numeric data so prices and totals align in columns.

### 18.3 Spacing, Motion, Elevation

- 4 px base scale: `0, 4, 8, 12, 16, 24, 32, 48, 64, 96`.
- Container max width 1440 px, gutters 16/24/32 px by breakpoint.
- Motion: 150 ms for micro-interactions, 250 ms for panels, 400 ms for page transitions; easing `cubic-bezier(0.2, 0, 0, 1)`. All motion wrapped in `@media (prefers-reduced-motion: reduce)` which reduces transforms to opacity-only or none.
- Elevation is conveyed by surface lightness and border, not by coloured glow.

### 18.4 Component Standards

| Component | Standard |
|---|---|
| Button | 44 px min touch target; variants: primary (white on black), secondary (outlined), ghost, destructive; loading state preserves width to prevent layout shift |
| Input | `--surface-sunken` background, 1 px `--border`, focus adds 2 px `--focus-ring` offset ring, error state adds icon + message with `aria-describedby` |
| Product card | 3:4 image, brand, title (2-line clamp), price block with MRP struck through and discount %, rating, wishlist toggle, quick-add on hover (keyboard reachable, not hover-only) |
| Skeletons | Match final layout dimensions exactly; shimmer disabled under reduced motion |
| Empty states | Icon + one-line explanation + a primary action; never a bare "No data" |
| Data table (admin) | Sticky header, column visibility, sort indicators, row selection, bulk action bar, keyboard row navigation, saved views |

---

## 19. Responsive Design & Accessibility

### 19.1 Breakpoints

| Name | Width | Grid |
|---|---|---|
| `xs` | 320–479 | 1 col products, bottom tab nav |
| `sm` | 480–767 | 2 col |
| `md` | 768–1023 | 3 col, filters in a slide-over sheet |
| `lg` | 1024–1279 | 4 col, persistent filter sidebar |
| `xl` | 1280–1535 | 4–5 col |
| `2xl` | ≥ 1536 | 5 col, max container 1440 |

Foldables are handled via the CSS Viewport Segments API where available, with a safe fallback: no critical control is ever placed across the fold seam.

Mobile-specific: sticky add-to-cart bar on PDP, bottom sheet for variant selection, one-thumb-reachable primary actions, `inputmode`/`autocomplete` attributes on every checkout field (`cc-number`, `postal-code`, `tel`) to trigger correct keyboards and autofill.

### 19.2 Accessibility Requirements (WCAG 2.2 AA)

| Area | Requirement |
|---|---|
| Contrast | Text ≥ 4.5:1, large text and UI components ≥ 3:1 — verified by automated token tests |
| Keyboard | Every interactive element reachable and operable; logical tab order; no traps; visible skip-to-content link |
| Focus | 2 px `--focus-ring` with 2 px offset, never `outline: none` without a replacement; focus is never obscured (WCAG 2.2 §2.4.11) |
| Target size | ≥ 24×24 CSS px minimum (WCAG 2.2 §2.5.8), 44×44 for primary mobile actions |
| Semantics | Landmark regions, one `h1` per page, ordered heading hierarchy, real `<button>`/`<a>` elements |
| Forms | Every input has a persistent visible label; errors announced via `role="alert"`; `aria-invalid` and `aria-describedby` wired |
| Live regions | Cart updates, filter result counts, and async statuses announced politely |
| Images | Meaningful `alt` from product title + variant; decorative images `alt=""` |
| Carousels | Pause control, keyboard arrows, no auto-advance longer than 5 s, announced slide position |
| Modals | Focus trap, `Esc` to close, focus returned to the trigger, `aria-modal` |
| Motion | Full `prefers-reduced-motion` support |
| Zoom | Usable at 400 % zoom / 320 px width with no horizontal scrolling |
| Screen readers | Tested on NVDA + Firefox, VoiceOver + Safari (desktop and iOS) |

Automated `axe-core` checks run in component tests and in every Playwright E2E journey; the build fails on any serious or critical violation. Automated checks are treated as a floor — a manual keyboard-only pass of the full purchase journey is part of every release checklist.

---

## 20. SEO & Structured Data

### 20.1 Rendering

The SPA is served with prerendered HTML for crawlable routes (home, category, product, CMS) via a prerender step in the build or an SSR-lite edge worker. Product and category pages must return meaningful HTML and a `200` status without JavaScript execution.

### 20.2 Per-Page Requirements

| Page | Title | Description | Canonical |
|---|---|---|---|
| Home | `BlackCart — Fashion, Minimal.` | Store description | `/` |
| Category | `{Category} for {Gender} — Buy Online \| BlackCart` | Templated with count | `/c/{slug}` (filters excluded) |
| Product | `{Brand} {Title} — {Category} \| BlackCart` | First 155 chars of description | `/p/{slug}` |
| Search | `Search: {q}` + `noindex` | — | — |

Faceted URLs are `noindex, follow` except for a curated allowlist of high-value facets (e.g. brand within category), which get self-referencing canonicals. Pagination uses `rel="next"/"prev"` and canonicalises to itself, never to page 1.

### 20.3 Structured Data (JSON-LD)

- `Product` with nested `Offer` (`price`, `priceCurrency`, `availability`, `itemCondition`, `priceValidUntil`, `shippingDetails`, `hasMerchantReturnPolicy`) and `AggregateRating` + `Review` — emitted **only** when real ratings exist.
- `BreadcrumbList` on category and product pages.
- `Organization` + `WebSite` with `SearchAction` on the homepage.
- `FAQPage` on the FAQ CMS page.
- `ItemList` on category pages.

All JSON-LD is generated from the same data the page renders, and validated in CI against schema.org via a structured-data linter.

### 20.4 Technical SEO

- `sitemap.xml` as a sitemap index → chunked child sitemaps (max 50k URLs each) for products, categories, brands, CMS; regenerated nightly and on catalogue change. Includes an image sitemap.
- `robots.txt` disallows `/admin`, `/checkout`, `/account`, `/api`, `/search`, and cart URLs; references the sitemap index.
- Open Graph and Twitter Card tags with a generated product OG image (product shot on black with brand and price).
- Hreflang scaffolding present but inert until i18n ships.
- 301 redirects on slug change, tracked in a `redirects` table; a slug is never reused.
- Soft-404 avoidance: out-of-stock products stay indexed with `availability: OutOfStock`; deleted products return `410 Gone`.
- Core Web Vitals monitored in the field via `web-vitals` beacon → analytics.

---

## 21. Observability

### 21.1 Structured Logging

JSON to stdout, one event per line, collected by the container runtime.

```json
{
  "timestamp": "2026-07-23T09:12:44.812Z",
  "level": "info",
  "logger": "app.services.order",
  "event": "order_created",
  "request_id": "01J8XK2P9V3QZ7M4N6R8T0W1Y",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "user_id": "01J8...",
  "order_number": "BC-20260723-7F3K9Q",
  "grand_total": "4120.67",
  "currency": "BDT",
  "duration_ms": 87,
  "env": "production",
  "version": "1.4.2+a3f9c1"
}
```

**Redaction is enforced by a structlog processor, not by discipline:** `password`, `token`, `authorization`, `cookie`, `card_number`, `cvv`, `secret`, `api_key`, and any key matching `*_token` are replaced with `***`. Email addresses and phone numbers are hashed in non-audit logs. A test asserts that a log record containing a password field never emits the value.

### 21.2 Metrics (Prometheus)

| Metric | Type | Labels |
|---|---|---|
| `http_requests_total` | counter | method, route, status |
| `http_request_duration_seconds` | histogram | method, route |
| `db_query_duration_seconds` | histogram | operation |
| `db_pool_connections` | gauge | state |
| `cache_operations_total` | counter | operation, result (hit/miss) |
| `celery_task_duration_seconds` | histogram | task, queue |
| `celery_queue_depth` | gauge | queue |
| `search_query_duration_seconds` | histogram | backend |
| `search_zero_results_total` | counter | — |
| `orders_created_total` | counter | payment_method |
| `order_value_total` | counter | currency |
| `payment_attempts_total` | counter | method, outcome |
| `checkout_funnel_step_total` | counter | step |
| `inventory_oversell_attempts_total` | counter | — |
| `auth_failures_total` | counter | reason |

### 21.3 Tracing

OpenTelemetry auto-instrumentation for FastAPI, SQLAlchemy, Redis, HTTPX, and Celery. `trace_id` propagates from the browser (via `traceparent`) through the API and into background tasks, so a slow checkout can be examined as a single trace spanning the HTTP request, the DB writes, and the async payment task.

### 21.4 Dashboards & Alerts

Grafana dashboards: **Golden Signals** (rate, errors, duration, saturation), **Business** (orders/hour, GMV, conversion funnel, AOV), **Infrastructure** (CPU, memory, connections, queue depth), **Search**, **Payments**.

| Alert | Condition | Severity |
|---|---|---|
| API error rate | 5xx > 1 % over 5 min | Page |
| API latency | p95 > 1 s over 10 min | Page |
| Payment failure spike | failure rate > 25 % over 10 min | Page |
| DB connections | > 85 % of pool for 5 min | Page |
| Celery queue depth | `critical` queue > 100 for 5 min | Page |
| Dead-letter tasks | any new entry | Ticket |
| Disk usage | > 80 % | Ticket |
| Cache hit rate | < 70 % for 30 min | Ticket |
| Zero-result searches | > 10 % of queries for 1 h | Ticket |
| Inventory drift | ledger vs. stock mismatch | Ticket |
| Backup job | failure or missing daily artefact | Page |
| Certificate expiry | < 14 days | Ticket |

### 21.5 SLOs

| Service | SLI | Target |
|---|---|---|
| Storefront read API | Availability | 99.9 % monthly |
| Checkout/payment API | Availability | 99.95 % monthly |
| Storefront read API | p95 latency < 300 ms | 99 % of 5-min windows |
| Search | p95 latency < 400 ms | 99 % |
| Order confirmation email | Delivered within 5 min | 99 % |

Error budget policy: if a month's budget is more than 50 % consumed, feature work pauses in favour of reliability work.

---

## 22. Security

### 22.1 Threat Model Summary

| Threat | Control |
|---|---|
| Credential stuffing | Rate limits, lockout, breached-password blocklist, MFA, new-device alerts |
| Session hijacking | HttpOnly + Secure + SameSite cookies, short access TTL, refresh rotation with reuse detection |
| XSS | React escaping by default, no `dangerouslySetInnerHTML` except on server-sanitised CMS HTML, strict CSP, sanitisation on ingest and on render |
| CSRF | Double-submit token + SameSite, origin/referer validation on state-changing requests |
| SQL injection | ORM with bound parameters; raw SQL forbidden by lint rule and code review |
| IDOR | Every resource fetch is scoped by the owning principal in the repository query itself, not checked afterwards; ULID public ids resist enumeration |
| Mass assignment | Explicit Pydantic request schemas; ORM models are never populated from raw request dicts |
| Price/total tampering | All money computed server-side from DB prices; client totals are display-only |
| Coupon abuse | Server-side validation, per-user limits, row locking, redemption audit |
| Oversell / race conditions | Row-level locks, DB `CHECK` constraints, reservation ledger |
| Malicious upload | MIME sniffing + extension allowlist + re-encode through Pillow, size caps, randomised filenames, served from a separate origin with `Content-Disposition` |
| SSRF | No user-supplied URLs fetched server-side; ingestion image fetching runs against an allowlist with private-IP blocking |
| Enumeration | Uniform responses on login/forgot-password/registration |
| DoS | Edge and application rate limits, query complexity caps, pagination limits, request body size cap (1 MB, 10 MB for uploads) |
| Privilege escalation | Permission dependency on every admin route, role assignment restricted to Super Admin, audit logged |
| Dependency compromise | Pinned lockfiles, `pip-audit` + `npm audit` + Dependabot, SBOM generated per build |
| Insider/misuse | Immutable audit log with before/after diffs, admin action alerting |

### 22.2 Security Headers (Nginx)

```nginx
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
add_header X-Content-Type-Options            "nosniff" always;
add_header X-Frame-Options                   "DENY" always;
add_header Referrer-Policy                   "strict-origin-when-cross-origin" always;
add_header Permissions-Policy                "camera=(), microphone=(), geolocation=(self), payment=()" always;
add_header Cross-Origin-Opener-Policy        "same-origin" always;
add_header Cross-Origin-Resource-Policy      "same-origin" always;
add_header Content-Security-Policy "
  default-src 'self';
  script-src 'self' 'nonce-$request_id';
  style-src 'self' 'nonce-$request_id';
  img-src 'self' data: blob: https://cdn.blackcart.example;
  font-src 'self';
  connect-src 'self' https://api.blackcart.example;
  frame-ancestors 'none';
  form-action 'self';
  base-uri 'self';
  object-src 'none';
  upgrade-insecure-requests;
  report-uri /api/v1/csp-report;
" always;
```

CSP uses nonces rather than `unsafe-inline`; the Vite build is configured to emit nonce-compatible output. CSP violations are reported to an endpoint and monitored — a spike is an early XSS signal.

### 22.3 Input Validation

Every request body, query parameter, path parameter, and header that influences behaviour passes through a Pydantic model with explicit types, bounds, and formats. Rejections return `422` with field-level detail. `model_config = ConfigDict(extra="forbid")` on all request schemas, so unexpected fields are an error rather than silently dropped — this catches both client bugs and probing.

Response models are declared on every route (`response_model=`), which prevents accidental leakage of internal fields such as `password_hash` even if a service returns a full ORM object.

### 22.4 File Upload Pipeline

1. Reject by extension allowlist (`jpg, jpeg, png, webp, avif`) and declared content type.
2. Verify real type by magic bytes; a mismatch is rejected and logged as a security event.
3. Cap size (10 MB) and dimensions (max 8000 px).
4. Strip all EXIF (including GPS) and re-encode through Pillow — this destroys any embedded payload.
5. Generate 5 sizes (`80, 200, 400, 800, 1600`) in WebP + AVIF, compute blurhash.
6. Store under a random ULID filename; the original client filename is kept only as metadata.
7. Optional ClamAV scan hook (`VIRUS_SCAN_ENABLED`) before publication.
8. Serve from a dedicated media origin with `X-Content-Type-Options: nosniff` and no cookies.

### 22.5 Secrets Management

Secrets come from environment variables sourced from Docker secrets or the platform's secret store; never from committed files. `gitleaks` runs in pre-commit and CI. Key rotation procedure is documented per secret with a supported dual-key window for JWT signing keys (`kid` in the header allows verification against both old and new during rotation).

### 22.6 Audit Logging

Every admin mutation writes an `audit_logs` row with actor, action, resource, before/after JSON diff (with sensitive fields redacted), IP, user agent, and request id — inside the same transaction as the change, so an audited action cannot succeed without its audit record. Audit logs are append-only: no `UPDATE`/`DELETE` grants on the table for the application DB user.

### 22.7 Pre-Release Security Checklist

- [ ] `bandit`, `pip-audit`, `npm audit`, `trivy` image scan — no high/critical
- [ ] `gitleaks` clean across full history
- [ ] Debug mode off, `/docs` gated, verbose errors disabled in production
- [ ] Default and seed credentials removed or rotated
- [ ] CORS allowlist contains no wildcards
- [ ] All admin routes assert a permission dependency (automated test)
- [ ] Rate limits verified by load test
- [ ] TLS: A+ on SSL Labs, HSTS preload submitted
- [ ] Backups restored successfully into a scratch environment within the last 30 days
- [ ] OWASP ASVS Level 2 checklist reviewed
- [ ] Manual test: IDOR probes on orders/addresses/reviews using another user's identifiers

---

## 23. Performance Budgets & Capacity

### 23.1 Frontend Budgets (enforced in CI)

| Metric | Budget |
|---|---|
| Initial JS (gzip) | ≤ 180 KB |
| Initial CSS (gzip) | ≤ 40 KB |
| LCP image | ≤ 150 KB |
| Total page weight (PLP, first view) | ≤ 1.2 MB |
| LCP (p75, mobile 4G) | ≤ 2.5 s |
| INP (p75) | ≤ 200 ms |
| CLS (p75) | ≤ 0.1 |
| TTFB (p75) | ≤ 600 ms |
| Requests before interactive | ≤ 30 |

### 23.2 Backend Targets

| Endpoint class | p50 | p95 | p99 |
|---|---|---|---|
| Cached reads (`/home`, `/categories`) | 20 ms | 80 ms | 200 ms |
| Product listing | 60 ms | 200 ms | 400 ms |
| Product detail | 40 ms | 150 ms | 300 ms |
| Search | 80 ms | 300 ms | 600 ms |
| Cart mutations | 60 ms | 250 ms | 500 ms |
| Order creation | 200 ms | 600 ms | 1200 ms |
| Admin list queries | 100 ms | 400 ms | 800 ms |

### 23.3 Capacity Assumptions

Design point: 500 concurrent shoppers, 50 orders/minute peak, 100k products, 1M order rows in year one.

- 4 API workers × 4 uvicorn processes; MySQL pool 20 + 10 overflow per worker.
- Read-heavy: ~95 % reads. Redis absorbs the homepage and listing load.
- MySQL sizing: 4 vCPU / 16 GB, `innodb_buffer_pool_size` ≈ 70 % of RAM.
- Horizontal scaling path: API is stateless (sessions in Redis, files in object storage), so scaling is adding containers behind Nginx. The known first bottleneck is MySQL writes on `orders`/`inventory_movements`; the documented next step is a read replica for analytics and listing queries.

### 23.4 Query Discipline

- Every list endpoint has an `EXPLAIN` recorded in the PR description showing index usage; `type: ALL` on a table over 10k rows blocks merge.
- N+1 detection: a test harness counts queries per endpoint and fails if a request exceeds its declared budget. Relationship loading is explicit (`selectinload`/`joinedload`), and lazy loading is disabled globally (`lazy="raise"`) so an accidental N+1 raises in tests instead of silently degrading production.
- Slow query log at 200 ms, reviewed weekly.

---

## 24. Testing Strategy

### 24.1 Test Pyramid

| Layer | Count target | Tooling | Runtime |
|---|---|---|---|
| Backend unit (services, pricing, state machine) | ~600 | pytest | < 60 s |
| Backend integration (repos, API, DB, Redis) | ~250 | pytest + testcontainers | < 5 min |
| Contract (OpenAPI ↔ client types) | auto | schemathesis | < 2 min |
| Frontend unit/component | ~400 | vitest + RTL + msw | < 90 s |
| E2E | ~40 journeys | Playwright | < 10 min |
| Visual regression | key pages × 3 viewports | Playwright snapshots | < 5 min |
| Accessibility | every E2E journey | axe-core | inline |
| Load | 5 scenarios | k6 | nightly |
| Security | SAST/DAST/deps | bandit, trivy, ZAP baseline | nightly |

### 24.2 Coverage Gates

Overall ≥ 80 % lines. `app/services/**` and `app/security/**` at 100 % branch coverage — pricing, permissions, and the order state machine are where a silent bug costs money or leaks data. Coverage may not decrease in a PR.

### 24.3 Critical Test Scenarios

**Pricing & cart**
- Coupon percent/fixed/free-shipping, each against min-order and cap boundaries
- Rounding: property test over random carts asserting the totals identity
- Price change between add-to-cart and checkout triggers confirmation
- Quantity and line-count limits at exact boundaries

**Inventory concurrency**
- 50 parallel checkouts on stock 10 → exactly 10 succeed, `reserved` returns to 0
- Reservation expiry releases stock exactly once
- Cancel/refund restock produces a balanced ledger

**Order lifecycle**
- Every legal transition succeeds; a sampled set of illegal transitions returns `409`
- Cancellation permitted before `PACKED`, refused after
- Duplicate `POST /orders` with the same idempotency key creates one order

**Payments**
- Each deterministic test card yields the expected terminal state
- Webhook replay, out-of-order delivery, and bad signature all handled correctly
- Payment success after intent expiry does not confirm the order

**Auth & security**
- Refresh reuse revokes the family
- Expired/tampered/`alg:none` tokens rejected
- IDOR: user A cannot read user B's order, address, cart, or review by id
- Missing CSRF token on a cookie-auth POST is rejected
- Rate limits return `429` with `Retry-After`
- Admin endpoint without permission returns `403`

**E2E journeys (Playwright)**
1. Guest browses → filters → adds to cart → registers → merges cart → checkout → pays → sees confirmation → tracks → receives delivery
2. COD order end-to-end with delivery simulation
3. Failed payment → retry with a working card → success
4. Cancel order before shipment → stock restored
5. Return request → admin approves → refund issued
6. Admin creates a product with variants and images → appears in search within the reindex window
7. Bulk CSV import → validation errors surfaced per row → successful rows imported
8. Coupon applied, then invalidated by cart change, with a clear message
9. Full keyboard-only purchase journey
10. Mobile viewport purchase journey

### 24.4 Test Data

Deterministic factories (`factory-boy`) with a fixed random seed. Each integration test runs inside a transaction rolled back at teardown; tests requiring commit use a per-test schema. No test depends on another test's data or on execution order. A `seed --profile=e2e` command produces a known fixture set for Playwright.

### 24.5 Load Scenarios (k6, nightly)

| Scenario | Profile | Pass criteria |
|---|---|---|
| Browse | 500 VU, 10 min, ramp | p95 < 300 ms, errors < 0.1 % |
| Search | 200 VU, 10 min | p95 < 500 ms |
| Flash sale | 1000 VU spike over 30 s on one product | No oversell, no 5xx, graceful 429s |
| Checkout | 100 VU sustained | p95 < 1 s, zero duplicate orders |
| Admin reporting | 20 VU heavy queries | No storefront latency regression |

---

## 25. CI/CD

### 25.1 Pipelines

**`pr.yml`** (every pull request, ~8 min target, jobs run in parallel):
1. `lint` — ruff, mypy `--strict`, eslint, prettier, stylelint
2. `test-backend` — pytest with MySQL + Redis services, coverage upload
3. `test-frontend` — vitest, coverage
4. `contract` — generate OpenAPI, regenerate TS types, fail on diff; schemathesis fuzzing
5. `security` — bandit, pip-audit, npm audit, gitleaks, trivy on built image
6. `build` — Docker images, bundle-size budget check
7. `e2e` — Playwright against a compose stack, artefacts (video, trace, axe report) on failure
8. `migrations` — upgrade → downgrade → upgrade; autogenerate diff must be empty

Branch protection requires all jobs green, one approving review, no direct pushes to `main`, and a linear history.

**`main.yml`** (on merge): all of the above, then build and push images tagged `sha-<short>` and `latest` to GHCR, generate an SBOM (syft) and sign the image (cosign), then deploy to staging, run smoke tests and a Lighthouse CI run against staging.

**`release.yml`** (on tag `v*`): promote the exact staging image digest — never a rebuild — to production, run migrations as a pre-deploy job, deploy with health-gated rollout, run smoke tests, and auto-rollback on failure. Publish release notes from conventional commits.

**`nightly.yml`**: k6 load suite, ZAP baseline scan, full E2E on the production-like stack, dependency freshness report, backup restore verification.

### 25.2 Deployment Safety

- Migrations run as a separate step before the new image serves traffic, and must be backwards compatible with the currently running version.
- Rolling deploy with `readyz` gating; a container is not added to the load balancer until dependencies check out.
- Automatic rollback if the error rate exceeds 2 % or `readyz` fails within 5 minutes of rollout.
- Every deploy is traceable: image digest, git SHA, and migration head are recorded and exposed at `/version`.

### 25.3 Code Quality Standards

- Conventional Commits; PR titles validated.
- PR template requires: what/why, test evidence, migration notes, `EXPLAIN` output for new queries, rollback plan.
- Pre-commit hooks: ruff, format, mypy on changed files, gitleaks, large-file guard.
- No `# type: ignore` or `eslint-disable` without an inline justification comment.
- Feature branches short-lived; long-running work goes behind a feature flag rather than a long-lived branch.

---

## 26. Deployment, Backup & Disaster Recovery

### 26.1 Compose Services

| Service | Image | Notes |
|---|---|---|
| `nginx` | nginx:1.27-alpine | TLS termination, static assets, security headers, rate limit |
| `api` | app backend (multi-stage) | gunicorn + uvicorn workers, non-root, read-only rootfs |
| `worker-critical` | same image | Celery, `-Q critical` |
| `worker-default` | same image | `-Q default,media` |
| `worker-bulk` | same image | `-Q bulk` |
| `beat` | same image | Celery beat with RedBeat lock (single scheduler guaranteed) |
| `mysql` | mysql:8.4 | Named volume, tuned `my.cnf`, healthcheck |
| `redis` | redis:7-alpine | AOF, maxmemory policy, healthcheck |
| `elasticsearch` | elasticsearch:8.x | Optional profile |
| `minio` | minio/minio | Optional profile |
| `otel-collector`, `prometheus`, `grafana` | — | Observability profile |
| `mailhog` | mailhog/mailhog | Dev profile only |

Compose profiles (`core`, `search`, `observability`, `dev`) let a developer run a minimal stack quickly and CI run exactly what it needs.

### 26.2 Container Hardening

Multi-stage builds (builder → slim runtime), non-root `UID 10001`, `read_only: true` with explicit `tmpfs` mounts, `cap_drop: ALL`, `no-new-privileges`, pinned base image digests, `.dockerignore` excluding tests/secrets/git, `HEALTHCHECK` on every service, and resource limits (`cpus`, `mem_limit`) declared so one runaway service cannot starve the host.

### 26.3 Backups

| Asset | Frequency | Retention | Method |
|---|---|---|---|
| MySQL full | Daily 02:00 | 30 days | `mysqldump --single-transaction` → gzip → encrypted → object storage |
| MySQL binlog | Continuous | 7 days | Point-in-time recovery |
| Object storage (media) | Daily incremental | 30 days | `mc mirror` to a second bucket |
| Redis | Hourly RDB | 48 hours | Cache is rebuildable; this is for convenience only |
| Configuration/secrets | On change | Versioned | Secret store versioning |

Backups are encrypted at rest (AES-256) and **verified by automated monthly restore** into a scratch environment followed by a row-count and checksum comparison. An untested backup is not a backup.

### 26.4 Recovery Objectives

| Scenario | RPO | RTO | Procedure |
|---|---|---|---|
| API container failure | 0 | < 1 min | Auto-restart / reschedule |
| Redis loss | 0 (cache) | < 5 min | Restart; caches repopulate; sessions require re-login |
| Elasticsearch loss | 0 | < 30 min | Rebuild index from MySQL; MySQL fallback serves search meanwhile |
| MySQL corruption | ≤ 5 min | < 2 h | Restore latest dump + replay binlog |
| Full host loss | ≤ 24 h | < 4 h | Rebuild from compose + restore backups |
| Bad deploy | 0 | < 10 min | Rollback to previous image digest |

### 26.5 Runbooks

Documented in `docs/runbooks/`, each with symptoms, diagnosis steps, resolution, and escalation: high error rate, payment gateway failures, queue backlog, database connection exhaustion, disk full, search index drift, oversell incident, suspected account compromise, cache stampede, certificate expiry.

---

## 27. Repository Structure

```
blackcart/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py                 # auth, permissions, pagination, db session
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       ├── public/             # auth, catalog, cart, checkout, orders, payments
│   │   │       └── admin/              # products, orders, users, analytics, system
│   │   ├── core/
│   │   │   ├── config.py               # Settings
│   │   │   ├── logging.py              # structlog setup + redaction processors
│   │   │   ├── errors.py               # exception hierarchy + handlers
│   │   │   ├── events.py               # domain event bus
│   │   │   ├── pagination.py
│   │   │   └── telemetry.py
│   │   ├── security/
│   │   │   ├── passwords.py  tokens.py  permissions.py
│   │   │   ├── csrf.py  ratelimit.py  sanitize.py  apikeys.py
│   │   ├── db/
│   │   │   ├── base.py  session.py  uow.py  types.py  seed/
│   │   ├── models/                     # SQLAlchemy mappings
│   │   ├── schemas/                    # Pydantic request/response DTOs
│   │   ├── repositories/               # query layer
│   │   ├── services/                   # business logic
│   │   │   ├── catalog/  cart/  checkout/  order/  payment/
│   │   │   ├── inventory/  promo/  review/  user/  admin/  analytics/
│   │   ├── integrations/
│   │   │   ├── payment/                # PaymentProvider + SimulatedProvider
│   │   │   ├── shipping/               # ShippingProvider + SimulatedCarrier
│   │   │   ├── search/                 # SearchBackend: ES + MySQL
│   │   │   ├── storage/                # StorageBackend: local + S3
│   │   │   └── mail/                   # MailBackend + templates
│   │   ├── tasks/                      # Celery tasks by domain
│   │   ├── middleware/
│   │   └── main.py
│   ├── alembic/versions/
│   ├── scripts/                        # ingest, seed, reindex, backup, admin bootstrap
│   ├── tests/{unit,integration,e2e,load,factories,conftest.py}
│   ├── pyproject.toml
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── app/                        # providers, router, error boundaries
│   │   ├── pages/{home,catalog,product,cart,checkout,account,auth,admin,cms}
│   │   ├── layouts/
│   │   ├── components/                 # see §17.3
│   │   ├── features/                   # colocated hooks+components per domain
│   │   ├── hooks/
│   │   ├── services/                   # apiClient + typed endpoint modules
│   │   ├── store/                      # zustand slices
│   │   ├── types/api.d.ts              # generated from OpenAPI (CI-verified)
│   │   ├── lib/                        # format, money, seo, analytics, a11y utils
│   │   ├── styles/tokens.css
│   │   └── main.tsx
│   ├── public/{robots.txt,favicon,...}
│   ├── e2e/                            # Playwright specs + fixtures
│   ├── vite.config.ts  tailwind.config.ts  tsconfig.json
│   └── Dockerfile
│
├── docker/
│   ├── docker-compose.yml
│   ├── docker-compose.override.yml     # local dev
│   ├── docker-compose.prod.yml
│   └── mysql/my.cnf  redis/redis.conf
├── nginx/{nginx.conf,conf.d/,ssl/}
├── infra/{prometheus/,grafana/dashboards/,otel/}
├── docs/
│   ├── spec.md  architecture.md  adr/  api.md
│   ├── runbooks/  onboarding.md  security.md  data-model.md
├── data/{raw/,taxonomy_map.yaml,brand_aliases.yaml,quarantine/}
├── .github/workflows/{pr.yml,main.yml,release.yml,nightly.yml}
├── Makefile
├── .env.example
└── README.md
```

`Makefile` targets: `make up`, `make down`, `make seed`, `make ingest`, `make migrate`, `make revision`, `make test`, `make test-e2e`, `make lint`, `make fmt`, `make reindex`, `make logs`, `make shell`, `make backup`, `make restore`.

**Architecture Decision Records** (`docs/adr/`) capture the reasoning behind consequential choices — modular monolith over microservices, cookie-based auth over localStorage tokens, address snapshots on orders, materialised category paths, ledger-based inventory. Each ADR records context, decision, alternatives considered, and consequences.

---

## 28. Feature Flags

Flags live in the `feature_flags` table, cached in Redis (30 s TTL), and are editable by Super Admins in the admin panel. Each supports a boolean toggle, a percentage rollout, and targeting rules (user id, role, email domain).

| Flag | Default | Purpose |
|---|---|---|
| `search.elasticsearch` | on | Fall back to MySQL search instantly if ES misbehaves |
| `search.semantic` | off | Embedding-based search (phase 5) |
| `checkout.express` | off | One-page checkout experiment |
| `payments.upi` / `payments.cod` / `payments.wallets` | on | Per-method kill switches |
| `recommendations.personalised` | off | Personalised homepage rail |
| `reviews.images` | off | Photo reviews |
| `reviews.auto_approve` | off | Skip moderation for verified purchasers |
| `catalog.infinite_scroll` | on | Infinite scroll vs. pagination |
| `promo.flash_sale` | off | Flash-sale banner and countdown |
| `ops.maintenance_mode` | off | Read-only storefront, checkout disabled with a clear message |
| `i18n.enabled` | off | Multi-language scaffolding |

Every flag has a named owner and a removal date recorded in the admin UI. Flags older than two releases past their removal date are surfaced in a weekly report — permanent flags are technical debt.

---

## 29. Delivery Roadmap

### Phase 0 — Foundations (Week 1–2)
Repo scaffolding, Docker Compose, CI skeleton, `Settings`, logging, error envelope, health endpoints, Alembic baseline, seed user/roles, frontend shell with tokens and layout.
**Exit:** `make up` serves an empty but styled storefront; CI green on an empty test suite.

### Phase 1 — Data & Catalogue (Week 3–4)
Ingestion pipeline through all 9 stages, catalogue schema and models, public product/category/brand endpoints with filtering, faceting, cursor pagination, image pipeline. Frontend: home, PLP with filters, PDP with gallery and variant selection.
**Exit:** browse 100k seeded products end-to-end with correct facets under the latency budget.

### Phase 2 — Identity (Week 5)
Registration, login, verification, password reset, refresh rotation with reuse detection, RBAC, rate limits, CSRF, sessions/devices UI, MFA.
**Exit:** full auth security test suite green, including IDOR and token-abuse cases.

### Phase 3 — Commerce (Week 6–8)
Cart (guest + merge), coupons, checkout session with stock reservation, order creation with idempotency, payment simulator with webhooks, order state machine, invoices, delivery simulation, order history and tracking.
**Exit:** E2E journeys 1–5 green; concurrency test proves no oversell.

### Phase 4 — Admin & Operations (Week 9–11)
Admin shell, dashboard and analytics, product/variant/inventory management, bulk import/export, order operations, refunds, user and role management, review moderation, coupons, banners, CMS, support tickets, audit log viewer.
**Exit:** the store can be operated entirely through the admin UI; every mutation is audited.

### Phase 5 — Search, Recommendations & Polish (Week 12–13)
Elasticsearch integration with alias-swap reindex, autocomplete, synonyms, zero-result handling, recommendation rails, wishlist, recently viewed, back-in-stock alerts, newsletter.
**Exit:** search relevance reviewed against a 50-query golden set; recommendation rails populated.

### Phase 6 — Hardening & Launch (Week 14–15)
Full accessibility audit and fixes, SEO and structured data, performance tuning to budget, load testing, security checklist and remediation, observability dashboards and alerts, backup/restore drill, runbooks, documentation, release pipeline.
**Exit:** all success criteria in §2.3 met; production release tagged.

Each phase ends with a demo, a written retrospective, and an updated ADR set. No phase is considered complete while its tests are skipped or its flags are permanently on.

---

## 30. Risks & Open Questions

### 30.1 Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Dataset quality worse than profiled (dead image URLs, sparse attributes) | Weak-looking catalogue, poor facets | High | Quarantine + reporting in ETL; curated taxonomy map; placeholder generation; accept a smaller, higher-quality subset over a large broken one |
| Scope creep from the long feature list | Missed timeline, half-finished features | High | Phase gates with explicit exit criteria; anything not in a phase goes behind a flag or to the backlog |
| Elasticsearch operational overhead in a small deployment | Memory pressure, flaky local dev | Medium | ES is optional behind a flag with a tested MySQL fallback that passes the same contract suite |
| Pure-black theme accessibility complaints (halation, OLED smear) | Usability harm | Medium | Surfaces above pure black, secondary text weight, contrast tested, optional dimmed variant considered post-launch |
| Inventory race conditions under flash-sale load | Oversell, customer harm | Medium | Row locks, DB constraints, ledger reconciliation, explicit concurrency tests, load scenario 3 |
| Simulated payment code drifting from real-gateway shape | Costly rewrite when a real PSP is added | Medium | Provider interface, webhook signatures, idempotency, and retry semantics modelled on real PSPs from day one |
| Denormalised counters (`rating_avg`, `sold_count`, `stock_total`) drifting | Wrong sorting and display | Medium | Nightly reconciliation jobs that alert on drift rather than silently rewriting |
| Test suite runtime growing past CI patience | Slow feedback, skipped tests | Medium | Parallelisation, testcontainers reuse, budget of 15 min for the PR pipeline |
| Single-node deployment as a SPOF | Downtime | Medium | Documented scale-out path; backups and RTO/RPO defined; stateless API |

### 30.2 Open Questions

1. **Currency and locale** — the dataset is INR-priced but the address model and payment methods (bKash, Nagad, Rocket) are Bangladesh-oriented. Decide: convert prices to BDT at a fixed seed rate, or keep INR and use Indian payment methods. *Recommendation: convert to BDT at ingest with the rate recorded, since the shipping and payment models are already BD-shaped.*
2. **Tax model** — flat VAT rate, or per-category rates? Affects `tax_class` seeding and invoice layout.
3. **Guest checkout** — permitted, or account required? Currently specified as account-required at order creation, with a guest cart.
4. **Review policy** — should unverified reviews be allowed later, and if so with what abuse controls?
5. **Prerendering approach** — build-time prerender for a 100k-product catalogue is impractical; confirm whether an SSR-lite edge layer is in scope for phase 6 or deferred.
6. **Return shipping cost** — who bears it, and does it differ by return reason?
7. **Data residency and privacy regime** — which framework governs (GDPR-style export/erasure endpoints are scaffolded but the retention table needs legal confirmation)?

---

## 31. Appendices

### A. Enumerations

| Enum | Values |
|---|---|
| `user.status` | `active`, `suspended`, `deleted` |
| `product.status` | `draft`, `active`, `archived` |
| `order.status` | `draft`, `pending_payment`, `confirmed`, `processing`, `packed`, `shipped`, `out_for_delivery`, `delivered`, `delivery_failed`, `cancelled`, `return_requested`, `return_approved`, `return_rejected`, `returned`, `refunded`, `failed` |
| `payment.status` | `pending`, `processing`, `requires_action`, `succeeded`, `failed`, `expired`, `refunded`, `partially_refunded` |
| `payment.method` | `visa`, `mastercard`, `upi`, `bkash`, `nagad`, `rocket`, `stripe_sim`, `cod` |
| `fulfilment.status` | `unfulfilled`, `partial`, `fulfilled` |
| `shipment.status` | `created`, `picked_up`, `in_transit`, `at_hub`, `out_for_delivery`, `delivered`, `failed`, `returned` |
| `review.status` | `pending`, `approved`, `rejected`, `hidden` |
| `coupon.discount_type` | `percent`, `fixed`, `free_shipping` |
| `inventory.reason` | `ingest_seed`, `admin_adjust`, `order_reserve`, `order_release`, `order_fulfil`, `return_restock`, `damage`, `recount` |
| `ticket.status` | `open`, `pending_customer`, `pending_agent`, `resolved`, `closed` |

### B. Error Code Reference

| Code | HTTP | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 422 | Request failed schema validation |
| `INVALID_CREDENTIALS` | 401 | Login failed (deliberately non-specific) |
| `TOKEN_EXPIRED` | 401 | Access token expired; refresh required |
| `TOKEN_INVALID` | 401 | Malformed, tampered, or revoked token |
| `SESSION_REUSE_DETECTED` | 401 | Refresh token replay; all sessions revoked |
| `ACCOUNT_LOCKED` | 423 | Too many failed attempts |
| `EMAIL_NOT_VERIFIED` | 403 | Action requires a verified email |
| `MFA_REQUIRED` | 401 | Second factor needed |
| `FORBIDDEN` | 403 | Missing permission |
| `CSRF_TOKEN_INVALID` | 403 | Double-submit check failed |
| `RESOURCE_NOT_FOUND` | 404 | Unknown resource |
| `RESOURCE_GONE` | 410 | Permanently removed |
| `ITEM_UNAVAILABLE` | 409 | Variant inactive or out of stock |
| `INSUFFICIENT_STOCK` | 409 | Requested quantity exceeds availability |
| `CART_EMPTY` | 409 | Checkout attempted on an empty cart |
| `PRICE_CHANGED` | 409 | Cart price differs from live price |
| `COUPON_NOT_FOUND` / `_EXPIRED` / `_LIMIT_REACHED` / `_NOT_ELIGIBLE` / `_MIN_ORDER_NOT_MET` | 422 | Coupon validation chain failures |
| `CHECKOUT_SESSION_EXPIRED` | 409 | Reservation window lapsed |
| `INVALID_TRANSITION` | 409 | Illegal order state change |
| `ORDER_NOT_CANCELLABLE` | 409 | Past the cancellation stage |
| `PAYMENT_FAILED` | 402 | Gateway declined |
| `PAYMENT_ALREADY_CAPTURED` | 409 | Duplicate capture attempt |
| `REFUND_EXCEEDS_PAYMENT` | 422 | Refund total too large |
| `IDEMPOTENCY_KEY_REUSE` | 409 | Same key, different payload |
| `REQUEST_IN_PROGRESS` | 409 | Concurrent identical request |
| `RATE_LIMITED` | 429 | Bucket exhausted |
| `PAYLOAD_TOO_LARGE` | 413 | Body exceeds limit |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Bad upload type |
| `DEPENDENCY_UNAVAILABLE` | 503 | DB/Redis/ES/storage down |
| `MAINTENANCE_MODE` | 503 | Storefront read-only |
| `INTERNAL_ERROR` | 500 | Unexpected; `request_id` provided for support |

### C. Glossary

| Term | Definition |
|---|---|
| **Variant** | A specific purchasable SKU of a product (size + colour). Stock lives here, not on the product. |
| **Reservation** | Temporarily held stock during checkout; converts to a decrement on payment or is released on expiry. |
| **Checkout session** | A short-lived server-side snapshot of cart, addresses, shipping, and totals with reserved stock. |
| **Snapshot field** | A value copied onto an order at placement so later catalogue edits cannot alter history. |
| **Idempotency key** | Client-generated identifier that makes a retried `POST` safe. |
| **Token family** | A chain of rotated refresh tokens; reuse of any ancestor revokes the whole chain. |
| **Materialised path** | Denormalised ancestor path on categories enabling single-index subtree queries. |
| **Ledger** | Append-only `inventory_movements` table; the authoritative history of stock changes. |
| **Alias swap** | Atomic Elasticsearch reindex technique pointing an alias at a freshly built index. |
| **Error budget** | Permitted unreliability within an SLO period; exhaustion pauses feature work. |

### D. Definition of Done

A feature is done when:

1. Code merged behind a flag if user-visible and incomplete.
2. Unit + integration tests written, meaningful, and passing; service-layer branches fully covered.
3. E2E coverage added for any new user journey.
4. `axe-core` clean; keyboard-only path verified manually.
5. OpenAPI updated; generated TS types committed and CI-verified.
6. Migration written with a working downgrade and `EXPLAIN` evidence for new queries.
7. Metrics, structured logs, and any needed alerts added.
8. Error cases produce specific, actionable codes and human-readable messages.
9. Documentation updated (`api.md`, `data-model.md`, runbook if operationally relevant).
10. Performance measured against the relevant budget.
11. Security implications considered and recorded in the PR (authz, input validation, data exposure).
12. Reviewed and approved; CI fully green.

---

*End of specification.*