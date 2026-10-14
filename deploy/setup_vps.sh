#!/usr/bin/env bash
# ==============================================================================
# Poorvanchal Matrimony - Turnkey VPS Deployment Script
# Supports: Oracle Linux 9 (RHEL) / Ubuntu 22.04 / 24.04 / Debian
# Multi-tenant isolation: Runs on 127.0.0.1:8001, leaving maindev.tech untouched.
# ==============================================================================

set -o errexit
set -o nounset
set -o pipefail

APP_DIR="/var/www/poorvanchalmatrimony"
REPO_URL="https://github.com/aditya081105/matrimony-site.git"
SYSTEMD_FILE="/etc/systemd/system/poorvanchal.service"
LOG_DIR="/var/log/poorvanchal"

echo "==> [1/7] Detecting OS and installing runtime dependencies..."
if command -v dnf >/dev/null 2>&1; then
    # Oracle Linux / RHEL / Alma / Rocky
    sudo dnf install -y python3.12 python3.12-pip python3.12-devel git nginx certbot python3-certbot-nginx curl
    NGINX_GROUP="nginx"
    PYTHON_BIN="python3.12"
    NGINX_CONF_DEST="/etc/nginx/conf.d/poorvanchalmatrimony.social.conf"
elif command -v apt-get >/dev/null 2>&1; then
    # Ubuntu / Debian
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx curl
    NGINX_GROUP="www-data"
    PYTHON_BIN="python3"
    NGINX_CONF_DEST="/etc/nginx/sites-available/poorvanchalmatrimony.social.conf"
else
    echo "Unsupported package manager."
    exit 1
fi

echo "==> [2/7] Setting up application directory..."
sudo mkdir -p "$APP_DIR"
sudo mkdir -p "$LOG_DIR"
sudo chown -R "$USER":"$NGINX_GROUP" "$APP_DIR"
sudo chown -R "$USER":"$NGINX_GROUP" "$LOG_DIR"
sudo chmod 755 "$APP_DIR"

if [ ! -d "$APP_DIR/.git" ]; then
    echo "Cloning repository..."
    git clone "$REPO_URL" "$APP_DIR"
else
    echo "Fetching latest changes..."
    cd "$APP_DIR"
    git fetch origin
    git checkout main
    git pull origin main
fi

cd "$APP_DIR"

echo "==> [3/7] Setting up Python virtual environment with $PYTHON_BIN..."
if [ ! -d "$APP_DIR/venv" ]; then
    "$PYTHON_BIN" -m venv "$APP_DIR/venv"
fi

"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "==> [4/7] Checking environment configuration (.env)..."
if [ ! -f "$APP_DIR/.env" ]; then
    echo "Creating .env from template..."
    cp "$APP_DIR/deploy/.env.example" "$APP_DIR/.env"
fi

echo "==> [5/7] Collecting static assets and applying database migrations..."
if [ -f "$APP_DIR/.env" ]; then
    "$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" collectstatic --noinput || true
    "$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" migrate || true
fi

echo "==> [6/7] Configuring systemd service..."
sudo cp "$APP_DIR/deploy/systemd/poorvanchal.service" "$SYSTEMD_FILE"
sudo sed -i "s|User=ubuntu|User=$USER|g" "$SYSTEMD_FILE"
sudo sed -i "s|Group=www-data|Group=$NGINX_GROUP|g" "$SYSTEMD_FILE"
sudo systemctl daemon-reload
sudo systemctl enable poorvanchal.service
sudo systemctl restart poorvanchal.service

echo "==> [7/7] Configuring Nginx server block..."
if [ -d "/etc/nginx/conf.d" ]; then
    sudo cp "$APP_DIR/deploy/nginx/poorvanchalmatrimony.social.conf" "/etc/nginx/conf.d/poorvanchalmatrimony.social.conf"
fi
if [ -d "/etc/nginx/sites-available" ]; then
    sudo cp "$APP_DIR/deploy/nginx/poorvanchalmatrimony.social.conf" "/etc/nginx/sites-available/poorvanchalmatrimony.social.conf"
    if [ ! -f "/etc/nginx/sites-enabled/poorvanchalmatrimony.social.conf" ]; then
        sudo ln -s "/etc/nginx/sites-available/poorvanchalmatrimony.social.conf" "/etc/nginx/sites-enabled/poorvanchalmatrimony.social.conf"
    fi
fi

# Ensure SELinux permissions if enabled
if command -v semanage >/dev/null 2>&1; then
    sudo semanage fcontext -a -t httpd_sys_content_t "$APP_DIR(/.*)?" 2>/dev/null || true
    sudo restorecon -R "$APP_DIR" 2>/dev/null || true
fi

sudo nginx -t
sudo systemctl reload nginx

echo "=================================================================="
echo "Deployment successful!"
echo "Poorvanchal Matrimony is running on 127.0.0.1:8001 via systemd."
echo "Nginx is routing poorvanchalmatrimony.social to this service."
echo ""
echo "To obtain SSL certificate via Certbot, run:"
echo "sudo certbot --nginx -d poorvanchalmatrimony.social -d www.poorvanchalmatrimony.social"
echo "=================================================================="
