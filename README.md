# Poorvanchal Matrimony

[![Django CI Pipeline](https://github.com/aditya081105/matrimony-site/actions/workflows/ci.yml/badge.svg)](https://github.com/aditya081105/matrimony-site/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Django 6.0](https://img.shields.io/badge/Django-6.0.8-green.svg)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20NVMe-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7%20In--Memory-red.svg)](https://redis.io/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

A full-stack community matrimonial web platform built with Django 6, PostgreSQL, and Bootstrap 5. Designed for localized community networking with mutual interest matching, privacy controls, manual UPI QR verification flow, transactional email alerts, and cache-aside read optimization.

**Production Domain:** [https://poorvanchalmatrimony.social](https://poorvanchalmatrimony.social)

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

### 5. Security, Privacy & Anti-Abuse Architecture
- **Unified Privacy & Visibility Engine:** Centralized visibility logic (`can_view`, `visible_profiles`, `get_profile_privacy_context`) guards all profile views and search feeds. High-sensitivity attributes (exact date of birth, parents' names) are masked until mutual interest approval or premium membership.
- **IPv6 /64 & CGNAT-Aware Lockout Protection:** Aggregates IPv6 addresses by `/64` CIDR prefix, applies a 100 failed attempts/hour IP threshold to accommodate CGNAT and campus proxies without accidental lockouts, and tracks account-level failures (50 failures/hour triggers security alerts without locking out legitimate account holders).
- **Payment & Subscription State Machine:** Payment transitions (`approve()`, `reject()`) are encapsulated in atomic state machines protected by database row-level locking (`select_for_update()`). Enforces a strict 3-order concurrent pending cap and an active order UTR `UniqueConstraint` to eliminate race conditions and double-spending.
- **Image Decompression Bomb Guard:** Pillow image processing limits dimension parsing to 16 megapixels (`MAX_IMAGE_PIXELS = 16_000_000`), strips EXIF metadata, normalizes uploads to RGB JPEG, and restricts uploads to active, approved users.
- **Scraping Defense & Rate-Limiting:** Profile browsing is throttled to 120 views/hour per authenticated user (exempting admin/staff), with silent contact form honeypots and IP-level burst protections.
- **Subresource Integrity (SRI):** Cryptographic SHA-384 hashes and `crossorigin="anonymous"` verify integrity across all external CDN scripts and styles.
- **State Mutation Protection:** All state-modifying actions (`send_request`, `update_request`, `cancel_request`, `unmatch`, `block_user`, `unblock_user`, `toggle_save`) strictly enforce HTTP POST with CSRF tokens (`@require_POST`), preventing GET-based CSRF and link pre-fetching attacks.
- **Secure Email Verification & Timing-Safe Resets:** Verification links use Django's `TimestampSigner` with a 24-hour expiration window (`max_age=86400`) and rate-limiting cooldown. Password reset codes use 6-digit tokens compared via `secrets.compare_digest` with 5-attempt throttling.

### 6. Production Hardening & Operational Standards
Production operational hardening details:
- **Systemd Process Sandboxing:** Gunicorn runs under a dedicated service (`poorvanchal.service`) with `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectSystem=full`, and restrictive umask `0027`.
- **Persistent SELinux Policies:** Configured with `etc_t` file context on production `.env` (`chmod 600`) to permit systemd `EnvironmentFile` reading without triggering AVC denials under enforcing mode.
- **TLS 1.3 & Reverse Proxy Security:** Nginx configured with automated Certbot SSL certificates, Cloudflare real-IP restoration (`set_real_ip_from`), HSTS (`max-age=31536000`), secure cookies (`SESSION_COOKIE_SECURE = True`), and strict deployment security checks (`manage.py check --deploy --fail-level WARNING`).
- **Database Backup Snapshotting:** Automated pre-deployment SQL snapshots (`pg_dump | gzip`) with non-zero integrity verification.


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
- **Current State:** NPCI-compliant UPI QR codes are generated dynamically with encoded transaction tags and amount. Users complete payment via their preferred UPI app and submit their 12-character bank UTR (Unique Transaction Reference) for verification.
- **Verification State Machine & Concurrency Integrity:**
  - Orders progress through a finite state machine: `pending` -> `verified` | `rejected`.
  - Format validation strictly enforces 12-character alphanumeric tokens (`^[A-Za-z0-9]{12}$`).
  - Active orders enforce a database `UniqueConstraint` on UTR to prevent double-spending or replay attacks.
  - Verification executes within an atomic transaction with row-level locks (`select_for_update()`) on `PaymentOrder` and `Subscription` models to prevent race conditions during activation.
  - Financial audit trails are preserved: `PaymentOrder.user` uses `on_delete=models.SET_NULL` so payment and UTR accounting records survive user account deletions.
- **Bank Reconciliation Workflow:**
  - Administrators cross-check submitted UTRs directly against bank account statements before executing verification.
  - Upon approval, the user's tier privileges (contact quota, badge, direct contact unlock) activate immediately.
- **Trade-off:** Completely eliminates 2-3% payment gateway intermediary fees and merchant onboarding friction for a non-profit community platform, with the trade-off of requiring human reconciliation.
- **Scale Path:** Transition to automated payment gateway webhooks (Razorpay / Cashfree / Stripe) backed by cryptographic signature verification, idempotency keys, and automated reconciliation daemons.

### 4. Cache Backend Architecture
- **Current State:** Redis Cache (via `django-redis`) provides shared cache-aside invalidation, OTP rate limiting, and multi-worker session state, falling back to in-memory `LocMemCache` during local test runs.
- **Trade-off:** High-performance in-memory caching synchronized across all Gunicorn workers without data drift.
- **Scale Path:** For multi-region clustering, introduce Redis Sentinel or Redis Cluster.

---

## Core Platform Features

- **Authentication & Profiles:** Custom user model extending `AbstractUser`, phone number validation against Indian telecom numbering (`^[6-9]\d{9}$`), Pillow image verification with EXIF metadata stripping and UUID anonymization, and time-stamped email verification.
- **Matchmaking & Discovery:** Filter by age, height, city, and caste. Mutual interest matching automatically detects reciprocal requests and creates match connections.
- **Privacy & Rate Limiting:** Sensitive contact details are shielded until mutual approval or verified Gold/Diamond membership. Free users are throttled to 3 requests/day across profiles, Silver members to 10/day, and Gold members enjoy unlimited requests.
- **UPI Subscriptions:** Tiered plans (Silver, Gold, Diamond VIP) with dynamic QR codes, 12-character UTR submission, duplicate prevention via database constraints, and row-locked subscription activation.

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.12 / 3.13, Django 6.0.8 |
| **Database** | PostgreSQL 16 (Self-hosted on NVMe), dj-database-url |
| **Concurrency & Workers** | Python `concurrent.futures`, Django `transaction.atomic()`, Row Locks (`select_for_update`) |
| **Caching** | Redis 7 (`django-redis` cache-aside with signal-based invalidation) |
| **Observability** | Custom `RequestIDMiddleware`, structured logging with `X-Request-ID` telemetry |
| **Media & Assets** | Local NVMe Storage with Nginx direct static serving & security headers, WhiteNoise |
| **Email Delivery** | Dedicated Gmail SMTP / Resend API |
| **CI/CD** | GitHub Actions (`.github/workflows/ci.yml`) with PostgreSQL 15 service |
| **Deployment** | Nginx Reverse Proxy, Systemd Daemon (Gunicorn WSGI), Cloudflare Edge WAF |
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

The test suite contains **137 automated tests** (0 failures, 1 skipped) covering:
- **Authentication & Lockout:** IPv6 `/64` CIDR normalization, CGNAT 100/hr IP threshold, account-level failure tracking (50/hr alert without lockout DoS), and timing-safe password resets.
- **Payment & Subscription State Machine:** Atomic `approve()` and `reject()` methods with row-level locks (`select_for_update`), 3-order concurrent pending cap, and active UTR database uniqueness.
- **Privacy & Unified Visibility:** Centralized `can_view`, `visible_profiles`, and `get_profile_privacy_context` with mutual-match masking for parents' names and exact DOB.
- **Image Security & Moderation:** Pillow decompression bomb protection (16M pixel cap), EXIF metadata stripping, upload rate limits, and suspended user upload blocking.
- **Rate Limiting & Anti-Scraping:** Profile browsing limited to 120 views/hour per user (with staff/admin exemption), contact form honeypot, and IP-level limits.
- **Database Integrity:** Database `UniqueConstraint` on `Lower('email')` and `phone_number`.
- **Edge Cases & Query Defense:** Safe handling for age/height bounds catching `OverflowError` and HTTP 404 for invalid request actions.
- **Subresource Integrity (SRI):** Cryptographic SHA-384 hashes and `crossorigin="anonymous"` on all CDN assets.
- **Deployment & Production Security:** Strict `manage.py check --deploy --fail-level WARNING` and environment configuration validation.

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
