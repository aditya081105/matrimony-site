#!/usr/bin/env bash
# ==============================================================================
# Poorvanchal Matrimony - Turnkey VPS Deployment Script (Ubuntu / Debian)
# Isolated multi-tenant deployment: runs on internal port 8001 without
# interfering with maindev.tech or other existing services on Nginx.
# ==============================================================================

set -o errexit
set -o nounset
set -o pipefail

APP_DIR="/var/www/poorvanchalmatrimony"
REPO_URL="https://github.com/aditya081105/matrimony-site.git"
SYSTEMD_FILE="/etc/systemd/system/poorvanchal.service"
NGINX_AVAILABLE="/etc/nginx/sites-available/poorvanchalmatrimony.social.conf"
NGINX_ENABLED="/etc/nginx/sites-enabled/poorvanchalmatrimony.social.conf"
LOG_DIR="/var/log/poorvanchal"

echo "==> [1/7] Updating package index and installing runtime dependencies..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip git nginx certbot python3-certbot-nginx curl

echo "==> [2/7] Setting up application directory..."
sudo mkdir -p "$APP_DIR"
sudo mkdir -p "$LOG_DIR"
sudo chown -R "$USER":"$USER" "$APP_DIR"
sudo chown -R "$USER":"$USER" "$LOG_DIR"

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

echo "==> [3/7] Setting up Python virtual environment..."
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi

"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "==> [4/7] Checking environment configuration (.env)..."
if [ ! -f "$APP_DIR/.env" ]; then
    echo "Creating .env from template..."
    cp "$APP_DIR/deploy/.env.example" "$APP_DIR/.env"
    echo "------------------------------------------------------------------"
    echo "NOTICE: Please configure $APP_DIR/.env with your DATABASE_URL,"
    echo "SECRET_KEY, and Gmail credentials before starting the service."
    echo "------------------------------------------------------------------"
fi

echo "==> [5/7] Collecting static assets and applying database migrations..."
if [ -f "$APP_DIR/.env" ]; then
    "$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" collectstatic --noinput || true
    "$APP_DIR/venv/bin/python" "$APP_DIR/manage.py" migrate || true
fi

echo "==> [6/7] Configuring systemd service..."
sudo cp "$APP_DIR/deploy/systemd/poorvanchal.service" "$SYSTEMD_FILE"
# Ensure the user running the service matches the current user
sudo sed -i "s|User=ubuntu|User=$USER|g" "$SYSTEMD_FILE"
sudo systemctl daemon-reload
sudo systemctl enable poorvanchal.service
sudo systemctl restart poorvanchal.service

echo "==> [7/7] Configuring Nginx server block..."
sudo cp "$APP_DIR/deploy/nginx/poorvanchalmatrimony.social.conf" "$NGINX_AVAILABLE"
if [ ! -f "$NGINX_ENABLED" ]; then
    sudo ln -s "$NGINX_AVAILABLE" "$NGINX_ENABLED"
fi

sudo nginx -t
sudo systemctl reload nginx

echo "=================================================================="
echo "Deployment completed successfully!"
echo "Poorvanchal Matrimony is running on 127.0.0.1:8001 via systemd."
echo "Nginx is configured to serve poorvanchalmatrimony.social."
echo ""
echo "To issue SSL certificates, run:"
echo "sudo certbot --nginx -d poorvanchalmatrimony.social -d www.poorvanchalmatrimony.social"
echo "=================================================================="
