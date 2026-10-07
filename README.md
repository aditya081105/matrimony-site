# Siwan Matrimony

[![Django CI/CD Pipeline](https://github.com/aditya081105/matrimony-site/actions/workflows/django.yml/badge.svg)](https://github.com/aditya081105/matrimony-site/actions/workflows/django.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Django 6.0](https://img.shields.io/badge/Django-6.0-green.svg)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon%20Cloud-blue.svg)](https://neon.tech/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

A high-concurrency, enterprise-grade matrimonial platform engineered with Django 6, PostgreSQL, and Bootstrap 5. Designed for localized community scale with bi-directional relationship matching, dynamic NPCI-compliant UPI QR subscription billing, asynchronous task processing, cache-aside data retrieval, and distributed request tracing.

**Live Production URL:** [https://siwan-matrimony.onrender.com/](https://siwan-matrimony.onrender.com/)

---

## Architecture & Engineering Highlights

This platform is engineered to meet Tier-1 production standards, focusing on high availability, database query efficiency, and concurrency safeguards.

### 1. ACID Transactions & Concurrency Safeguards
- **Row-Level Locking:** Uses PostgreSQL `select_for_update()` during contact request state transitions and subscription upgrades to eliminate double-submit and race-condition vulnerabilities.
- **Atomic Operations:** Critical business logic (request acceptance, wallet/quota consumption, order verification) is strictly encapsulated within `transaction.atomic()` boundaries.

### 2. Decoupled Asynchronous Worker Queue
- **Non-Blocking HTTP Cycle:** Offloads external I/O (transactional email dispatch via Gmail SMTP / Resend API) to a background `ThreadPoolExecutor` worker pool.
- **Latency Optimization:** User-facing HTTP requests complete in **~30ms**, completely preventing Gunicorn worker thread starvation during third-party network latency.
- **Deterministic Testing:** Automatically falls back to synchronous execution during unit test runs to ensure 100% deterministic assertions.

### 3. Database Optimization & Compound B-Tree Indexing
- **Compound Indexes:** High-frequency filter vectors are indexed using multi-column B-Trees:
  - `user_match_idx`: `(is_active, is_approved, is_suspended, gender)`
  - `user_city_gender_idx`: `(city, gender)`
  - `user_caste_gender_idx`: `(caste, gender)`
  - `req_receiver_status_idx`: `(receiver, status)`
- **Zero N+1 Queries:** Database queries utilize `select_related()` and `prefetch_related()` across profile relations (`Profile`, `City`, `Caste`, `Subscription`, `Plan`). Bounded query counts are validated through automated `CaptureQueriesContext` assertions.

### 4. High-Performance Caching (Cache-Aside Pattern)
- **Sub-Millisecond Read Paths:** Frequently read metadata (Cities, Castes, Active Membership Plans) are served through a Cache-Aside layer.
- **Event-Driven Invalidation:** Automated Django `post_save` and `post_delete` signals purge stale cache keys the instant an administrator modifies pricing or taxonomy data.

### 5. Enterprise Observability & Tracing
- **Request Tracing Middleware:** Injects a unique `X-Request-ID` UUID into every HTTP request and response header.
- **Latency Tracking:** Logs structured performance telemetry (HTTP method, URI, status code, latency in milliseconds, user identification) for auditability and distributed log correlation.

### 6. Automated CI/CD Pipeline
- **GitHub Actions Integration:** Full test suite execution, Django system checks, and dependency audits trigger on every push and pull request to `main`.

---

## Core Platform Features

### Authentication & Profile Trust
- **Custom User Model:** Built on `CustomUser` (extending `AbstractUser`) with strict phone number validation against authentic Indian telecom series (`^[6-9]\d{9}$`).
- **Cryptographic Email Verification:** Tokenized, signed verification links with session-level 60-second rate-limiting to prevent quota abuse.
- **Cloudinary CDN Integration:** Secure photo uploads with automatic face-detection cropping, responsive variants, and WebP delivery.
- **Open Taxonomy:** Free-text Caste and Sub-Caste (Gotra) fields tailored to local community nuances without rigid drop-down constraints.

### Matchmaking & Discovery
- **Localized Bilingual UI:** Seamless English and Hindi toggle with custom translation persistence.
- **Search Engine:** Multi-field search querying across names, occupations, cities, castes, and bio content.
- **Deterministic Pagination:** Ordered result sets ensuring consistent pagination across all filter combinations.

### Contact Requests & Privacy
- **Privacy Shield:** Personal contact numbers and sensitive details remain locked until contact requests are mutually approved or unlocked via premium membership.
- **Anti-Spam Daily Limits:** Free-tier accounts are restricted to 3 contact attempts per day.
- **Bi-Directional Blocking:** Mutual privacy isolation—blocking prevents both parties from viewing each other in search results, matchmaking, or direct messaging.
- **Abuse Reporting:** Community moderation queue with automated suspension thresholds.

### UPI QR Payment & Subscription Engine
- **NPCI UPI QR Code Generation:** Real-time generation of `upi://pay` QR codes with encoded merchant IDs, order reference tags, and precise plan prices for Google Pay, PhonePe, Paytm, and BHIM.
- **12-Digit UTR Tracking:** Users submit their bank UPI transaction reference (UTR) for administrative verification.
- **Automated Lifecycle Management:** Multi-tier membership management (**Silver**, **Gold**, **Diamond VIP**) with automated expiration, renewal extensions, and tier badges.

---

## Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend** | Python 3.12 / 3.13, Django 6.0 |
| **Database** | PostgreSQL (Neon Cloud Serverless), dj-database-url |
| **Concurrency & Workers** | Python `concurrent.futures`, Django Signals, Database Row Locks |
| **Caching** | Django Cache Framework (Cache-Aside Pattern) |
| **Observability** | Custom `RequestIDMiddleware`, Structured Logging |
| **Media & CDN** | Cloudinary CDN Storage |
| **Static Delivery** | WhiteNoise |
| **Email Infrastructure** | Gmail SMTP / Resend API |
| **CI/CD** | GitHub Actions (`.github/workflows/django.yml`) |
| **Containerization** | Docker, Docker Compose |
| **Frontend** | Django Templates, Bootstrap 5.3, Inter & Playfair Display typography |

---

## Quickstart & Local Setup

### Option A: Running with Docker (Recommended)

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

The test suite contains **32 automated tests** covering:
- Authentication, phone validation, and user model constraints.
- Email verification cooldown rate-limiting.
- Concurrency locks, transaction atomicity, and request workflows.
- Reverse OneToOne `select_related` query bounding (`assertNumQueries` / `CaptureQueriesContext`).
- Cache-Aside hit/miss lifecycle and signal-based invalidation.
- Membership order creation, UPI UTR verification, and tier lifecycle transitions.

```bash
python manage.py test
```

---

## Author

**Aditya Kumar**
- GitHub: [@aditya081105](https://github.com/aditya081105)
- Repository: [matrimony-site](https://github.com/aditya081105/matrimony-site)

---

## License & Commercial Notice

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](LICENSE) file for details.

> **Notice:** Commercial resale, unauthorized repackaging, or redistributing this codebase on digital asset marketplaces (Envato, Codester, Fiverr) without explicit permission is strictly prohibited and subject to DMCA takedown action.
