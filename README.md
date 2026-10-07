# Siwan Matrimony

A production-ready community matrimonial web platform built with Django 6, PostgreSQL, and Bootstrap 5. It features admin-moderated onboarding, secure request-based contact exchange, bi-directional relationship blocking, multi-field community search, and a complete UPI QR membership and payment system.

Live Production URL: [https://siwan-matrimony.onrender.com/](https://siwan-matrimony.onrender.com/)

---

## 🌟 Key Features

### 1. User Authentication & Profile Verification
- Custom user model (`CustomUser`) extending Django's `AbstractUser`.
- Admin approval gating before matchmaking access.
- Cryptographically signed email verification via Resend API.
- Profile completeness validation and photo upload via Cloudinary CDN.

### 2. Matchmaking & Filtering
- Filter prospective matches by gender, age range, height range, city, and caste community.
- Database query optimization with `select_related` to eliminate N+1 queries.
- Prioritized placement for verified VIP/Gold members.

### 3. Community Search Engine
- Dedicated multi-field search engine across names, professions, cities, and castes.
- Automatic exclusion of blocked profiles.

### 4. Contact Requests & Anti-Spam
- Request-based contact discovery system.
- Daily rate limiting (max 3 contact attempts per day for free tier).
- Soft delete, unmatch, and cancel pending request options.

### 5. Premium Memberships & UPI QR Payments
- Multi-tier membership plans: **Silver**, **Gold VIP ⭐**, and **Diamond Elite 💎**.
- Dynamic NPCI-compliant UPI QR code generation (`upi://pay`) for Google Pay, PhonePe, Paytm, and BHIM.
- 12-digit UTR (UPI Reference) transaction logging and admin verification workflow.
- **Perks for Premium Members:**
  - Unlimited daily contact requests.
  - Direct contact unlock (phone numbers and emails) without waiting for request acceptance.
  - Verified VIP badges displayed on profile cards and search results.
- Built-in Sandbox Demo Mode for instant test activation during evaluations.

### 6. Safety & Moderation
- Bi-directional user blocking (neither user can view or interact with the other).
- Community reporting system with automatic suspension threshold (5+ reports).
- Django Admin panel customization with one-click payment and membership approval actions.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.12 / 3.13, Django 6.0
- **Database:** PostgreSQL (Neon Cloud)
- **Containerization:** Docker & Docker Compose
- **Media & CDN:** Cloudinary Storage
- **Static Assets:** WhiteNoise
- **Email Service:** Resend API
- **Production Host:** Render (Gunicorn WSGI)
- **Frontend:** Django Templates, Bootstrap 5.3, Inter & Playfair Display fonts

---

## 🐳 Running with Docker (Recommended)

Run the entire application in a container with a single command:

```bash
# Clone the repository
git clone https://github.com/aditya081105/matrimony-site.git
cd matrimony-site

# Build and start the container
docker compose up --build
```

The application will be accessible at: `http://localhost:8000`

---

## 💻 Local Development Setup (Without Docker)

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

# 4. Setup environment variables in .env
SECRET_KEY=your_secret_key
DATABASE_URL=your_postgres_database_url
RESEND_API_KEY=your_resend_api_key
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# 5. Apply migrations
python manage.py migrate

# 6. Run automated test suite
python manage.py test

# 7. Start development server
python manage.py runserver
```

---

## 🧪 Automated Testing

The project includes unit and integration tests covering:
- Authentication & custom user models
- Contact request workflows, daily throttling, and bi-directional blocking
- Search query matching and filtering
- Membership plan seeding, checkout, UTR tracking, and subscription activation

Run the test suite:
```bash
python manage.py test
```

---

## 👤 Author

**Aditya Kumar**
- GitHub: [@aditya081105](https://github.com/aditya081105)
- Repository: [matrimony-site](https://github.com/aditya081105/matrimony-site)

---

## ⚖️ License & Commercial Protection

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](LICENSE) file for details.

> **Commercial Use & Resale Warning:**  
> This project is strictly protected. Unauthorized commercial resale, including listing this codebase on marketplaces like Codester, Envato Market, or Fiverr, is a direct violation of copyright laws and will face immediate DMCA takedown action.

