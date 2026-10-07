# Siwan Matrimony

[![Django CI Pipeline](https://github.com/aditya081105/matrimony-site/actions/workflows/ci.yml/badge.svg)](https://github.com/aditya081105/matrimony-site/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Django 6.0](https://img.shields.io/badge/Django-6.0-green.svg)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon%20Cloud-blue.svg)](https://neon.tech/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

A full-stack community matrimonial web platform built with Django 6, PostgreSQL, and Bootstrap 5. Designed for localized community networking with mutual interest matching, privacy controls, manual UPI QR verification flow, transactional email alerts, and cache-aside read optimization.

**Live Production URL:** [https://siwan-matrimony.onrender.com/](https://siwan-matrimony.onrender.com/)

---

## Technical Overview & Key Implementations

### 1. Database Concurrency Control & Transactions
- **Atomic State Transitions:** Critical business logic (interest acceptance, mutual auto-matching, subscription activation) is wrapped inside `transaction.atomic()` blocks.
- **Row-Level Locking:** Uses `select_for_update()` on sender user rows during request creation and on `Subscription` models during payment activation to eliminate race conditions, duplicate state mutations, and quota-bypassing races.

### 2. Query Optimization & PostgreSQL Trigram GIN Search
- **N+1 Prevention:** Views make extensive use of `select_related()` (for `Profile`, `City`, `Caste`, `Subscription`) across relational lookups to keep query counts bounded. Unit tests enforce this via `assertNumQueries` and `CaptureQueriesContext`.
- **PostgreSQL Trigram GIN Indexing (`pg_trgm`):** Implemented `user_fn_trgm_idx` and `user_occ_trgm_idx` using the `pg_trgm` extension with `gin_trgm_ops` operator class.
  - Replaces sequential table scans with `Bitmap Index Scan on user_fn_trgm_idx` for similarity (`%`) and `ILIKE` searches.
  - Confirmed via `EXPLAIN ANALYZE`: query planning executes in ~0.10ms and index scan in ~0.01ms.
- **Compound B-Tree Indexing:** Multi-column indexes target frequent filter vectors:
  - `user_match_idx`: `(is_active, is_approved, is_suspended, gender)`
  - `user_city_gender_idx`: `(city, gender)`
  - `user_caste_gender_idx`: `(caste, gender)`
  - `req_receiver_status_idx`: `(receiver, status)`
- **Search Ordering & Pagination:** Search queries enforce explicit ordering (`-similarity`, `-date_joined`) with server-side pagination (12 profiles per page) to prevent unindexed unbounded result sets.

### 3. Caching & Multi-Worker State
- **Redis Cache Backend:** Configured with `django-redis` when `REDIS_URL` is provided, ensuring cache invalidations are synchronized across multi-worker Gunicorn processes, with automatic fallback to `LocMemCache` in local development.
- **Cache-Aside Pattern:** Frequently read, infrequently modified taxonomy data (Cities, Castes, Active Membership Plans) utilizes a cache-aside pattern with automatic signal-based invalidation (`post_save` and `post_delete` signals) ensuring stale data is evicted immediately upon admin updates.

### 4. Background Email Processing with Retry Backoff
- **Decoupled Delivery:** Transactional email dispatch (email verification tokens and contact form inquiries) is offloaded to a background `ThreadPoolExecutor` worker pool, preventing third-party SMTP/API network latency from blocking web worker request cycles.
- **Exponential Backoff Retries:** Worker jobs implement a 3-attempt retry loop with exponential delay (`time.sleep(1.5 * attempt)`) to survive transient network or provider glitches.
- **Deterministic Testing:** Automatically falls back to synchronous execution during automated test runs to maintain deterministic test assertions.

### 5. Security & Verification
- **State Mutation Protection:** All state-modifying actions (`send_request`, `update_request`, `cancel_request`, `unmatch`, `block_user`, `unblock_user`, `toggle_save`) strictly enforce HTTP POST with CSRF tokens (`@require_POST`), preventing GET-based CSRF and link pre-fetching attacks.
- **Expiring Email Verification:** Verification links use Django's `TimestampSigner` with a 24-hour expiration window (`max_age=86400`) and rate-limiting cooldown to prevent verification link reuse or flooding.
- **Payment Reference Integrity:** UPI UTR submissions enforce 12-character alphanumeric format validation (`^[A-Za-z0-9]{12}$`) and a database `UniqueConstraint` on active orders to reject duplicate or racing submissions.
- **Profile Access Gate:** Public profile viewing verifies that the targeted user has been approved by administrators before revealing details.
- **Bidirectional Privacy:** Blocking isolates both users symmetrically across searches and contact request paths.

---

## Architecture Trade-offs & Known Bottlenecks

This project was built to address real-world community matrimonial needs with practical trade-offs. Below is an honest engineering evaluation of current design choices and how they would evolve under higher scale:

### 1. In-Process Worker Pool vs. Distributed Task Queue
- **Current State:** Transactional emails run in an in-memory `ThreadPoolExecutor` (3 workers) with a 3-attempt exponential backoff retry loop.
- **Trade-off:** Minimal infrastructure footprint and zero Redis dependency, but jobs lack persistence across process restarts, dead-letter storage, or centralized queue monitoring.
- **Scale Path:** For multi-instance deployments or high transactional email volumes, transition to Celery or RQ backed by Redis with persistent broker storage and DLQs.

### 2. PostgreSQL Trigram Search vs. Dedicated Search Cluster
- **Current State:** Search queries utilize PostgreSQL `pg_trgm` GIN indexes (`gin_trgm_ops`) on full name and occupation for fuzzy and substring matching.
- **Trade-off:** Fast, sub-millisecond query execution within the existing relational database without additional infrastructure overhead.
- **Scale Path:** Adopt an external dedicated search engine (Meilisearch or Elasticsearch) if multi-lingual phonetic transliteration or complex facet aggregations are required at scale.

### 3. Offline UPI QR Flow vs. Payment Gateway Webhooks
- **Current State:** NPCI-compliant UPI QR codes are rendered dynamically with encoded order tags; users submit their bank UTR for manual admin verification.
- **Trade-off:** Completely eliminates 2-3% payment gateway transaction fees and merchant onboarding friction for a non-profit community platform, but requires human review.
- **Scale Path:** Implement automated payment gateway webhooks (Razorpay / Cashfree) backed by an idempotency key and a strict payment status state machine.

### 4. Cache Backend Scope
- **Current State:** Cache-aside operates using Django's default cache framework backend.
- **Trade-off:** Zero external service configuration required for local development and single-dyno hosting.
- **Scale Path:** In multi-container environments, swap the backend to shared Redis/Memcached so cache invalidations are synchronized across all web instances.

---

## Core Platform Features

- **Authentication & Profiles:** Custom user model extending `AbstractUser`, phone number validation against Indian telecom numbering (`^[6-9]\d{9}$`), Cloudinary image management, and time-stamped email verification.
- **Matchmaking & Discovery:** Filter by age, height, city, and caste. Mutual interest matching automatically detects reciprocal requests and creates match connections.
- **Privacy & Rate Limiting:** Sensitive contact details are shielded until mutual approval. Free users are throttled to 3 requests/day across profiles, Silver members to 10/day, and Gold members enjoy unlimited requests, with an additional per-target throttle of 3 attempts/day.
- **UPI Subscriptions:** Tiered plans (Silver, Gold, Diamond VIP) with dynamic QR codes, 12-character UTR submission, duplicate prevention via database constraints, and row-locked subscription activation.

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.12 / 3.13, Django 6.0 |
| **Database** | PostgreSQL (Neon Cloud Serverless), dj-database-url |
| **Concurrency & Workers** | Python `concurrent.futures`, Django `transaction.atomic()`, Row Locks (`select_for_update`) |
| **Caching** | Django Cache Framework (Cache-Aside with signal-based invalidation) |
| **Observability** | Custom `RequestIDMiddleware`, structured logging with `X-Request-ID` telemetry |
| **Media & Assets** | Cloudinary CDN Storage, WhiteNoise |
| **Email Delivery** | Gmail SMTP / Resend API |
| **CI/CD** | GitHub Actions (`.github/workflows/ci.yml`) with PostgreSQL 15 service |
| **Containerization** | Docker (Gunicorn WSGI), Docker Compose |
| **Frontend** | Django Templates, Bootstrap 5.3 |

---

## Quickstart & Local Setup

### Option A: Running with Docker

```bash
# 1. Clone repository
git clone https://github.com/aditya081105/matrimony-site.git
cd matrimony-site

# 2. Build and launch container
docker compose up --build
```
Access the application at: `http://localhost:8000`

---

### Option B: Local Virtual Environment Setup

```bash
# 1. Clone repository
git clone https://github.com/aditya081105/matrimony-site.git
cd matrimony-site

# 2. Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables in .env
SECRET_KEY=your_secret_key
DATABASE_URL=postgresql://user:password@host/dbname
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# 5. Run database migrations
python manage.py migrate

# 6. Execute automated test suite
python manage.py test

# 7. Start development server
python manage.py runserver
```

---

## Automated Test Suite

The test suite contains **39 automated tests** covering:
- Authentication constraints, phone regex checks, and unapproved profile access security.
- Expiring token email verification via `TimestampSigner` and rate-limiting cooldown.
- HTTP POST enforcement and 405 rejection for state-mutating endpoints (`send_request`, `block_user`, `unblock_user`, `unmatch`, `cancel_request`, `toggle_save`).
- Mutual request matching, bidirectional blocking, and daily request quota enforcement across membership tiers.
- Reverse OneToOne `select_related` query bounding (`assertNumQueries` / `CaptureQueriesContext`).
- Cache-aside hit/miss lifecycle and signal-driven cache invalidation.
- Membership order creation, strict 12-character alphanumeric UTR validation, duplicate UTR database rejection, and subscription lifecycle transitions.
- Concurrency quota race testing using `TransactionTestCase` and `@skipUnlessDBFeature('has_select_for_update')`, executed against PostgreSQL in GitHub Actions CI.

```bash
python manage.py test
```

---

## Load Testing & Performance Benchmarking

A Locust load-testing suite (`locustfile.py`) is included to benchmark concurrency, p50/p95 latency, and cache hit performance under simulated traffic.

```bash
# Run headless load test with 50 concurrent users spawning at 10 users/sec:
locust -f locustfile.py --headless -u 50 -r 10 --run-time 20s --host http://127.0.0.1:8000 --csv=benchmark_results --only-summary
```

### Empirical Benchmark Results (50 Concurrent Users, 0% Failure Rate)

| Endpoint | Method | Requests | Req/s | Median (p50) | 90th % | 95th % | Max Latency | Failures |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Homepage** (`/`) | GET | 133 | 6.98 | 3 ms | 11 ms | 27 ms | 34 ms | 0 (0.0%) |
| **Membership Plans** (`/payments/plans/`) | GET | 81 | 4.25 | 4 ms | 12 ms | 28 ms | 680 ms* | 0 (0.0%) |
| **Search Profiles** (`/search/?q=...`) | GET | 115 | 6.03 | 7 ms | 42 ms | 49 ms | 52 ms | 0 (0.0%) |
| **Matchmaking Feed** (`/matchmaking/`) | GET | 80 | 4.20 | 7 ms | 19 ms | 43 ms | 47 ms | 0 (0.0%) |
| **About / Terms / Privacy** | GET | 93 | 4.89 | 3 ms | 7 ms | 26 ms | 32 ms | 0 (0.0%) |
| **Aggregated Total** | - | **502** | **26.33** | **6 ms** | **20 ms** | **38 ms** | **680 ms** | **0 (0.0%)** |

*\*Note: The max latency outlier on `/payments/plans/` represents the initial database connection handshake and cold-start cache population.*

---

## Author

**Aditya Kumar**
- GitHub: [@aditya081105](https://github.com/aditya081105)
- Repository: [matrimony-site](https://github.com/aditya081105/matrimony-site)

---

## License

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](LICENSE) file for details.
