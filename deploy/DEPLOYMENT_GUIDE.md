# Production Deployment & Hardening Guide

This document defines the step-by-step deployment and verification process for deploying releases to the production VPS (`140.238.167.173`).

---

## 1. Pre-Deployment Database Backup

Always take a full SQL snapshot before pulling code updates or running migrations:

```bash
# Define backup timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="/var/backups/poorvanchal"
sudo mkdir -p "$BACKUP_DIR"

# PostgreSQL snapshot
sudo -u postgres pg_dump poorvanchal_db | gzip > "$BACKUP_DIR/poorvanchal_db_${TIMESTAMP}.sql.gz"

# Verify backup was created and has non-zero size
ls -lh "$BACKUP_DIR/poorvanchal_db_${TIMESTAMP}.sql.gz"
```

---

## 2. Pulling Verified Git Release

```bash
cd /var/www/poorvanchalmatrimony

# Fetch tags and latest commits from main
git fetch origin
git checkout main
git pull origin main

# Confirm commit hash matches verified pull request
git log -n 1 --oneline
```

---

## 3. Python Virtual Environment & Dependency Upgrades

Upgrade dependencies to the exact audited security pins:

```bash
cd /var/www/poorvanchalmatrimony
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

---

## 4. Database Migrations

Apply pending database schema changes (e.g. constraints, new fields):

```bash
cd /var/www/poorvanchalmatrimony
./venv/bin/python manage.py migrate
```

---

## 5. Deployment System Check Gate

Run Django's deployment security check to ensure no production misconfigurations exist:

```bash
cd /var/www/poorvanchalmatrimony
./venv/bin/python manage.py check --deploy --fail-level WARNING
```

---

## 6. Static Asset Compilation

Recompile and cache versioned static assets:

```bash
cd /var/www/poorvanchalmatrimony
./venv/bin/python manage.py collectstatic --noinput
```

---

## 7. File Permissions & Environment Hardening

Ensure the environment secrets file is locked down to read/write by owner only:

```bash
cd /var/www/poorvanchalmatrimony
sudo chown $(whoami):$(whoami) .env
chmod 600 .env
sudo chown -R $(whoami):nginx /var/www/poorvanchalmatrimony
chmod 755 /var/www/poorvanchalmatrimony
```

---

## 8. Graceful Service Reload

```bash
# Reload systemd and restart application service
sudo systemctl daemon-reload
sudo systemctl restart poorvanchal.service

# Check service status
sudo systemctl status poorvanchal.service --no-pager

# Test and reload Nginx
sudo nginx -t
sudo systemctl reload nginx
```

---

## 9. Post-Deployment Verification

Verify application health via local HTTP check:

```bash
# Local upstream response check
curl -I http://127.0.0.1:8001/

# Public HTTPS health check
curl -I https://poorvanchalmatrimony.social/
```
