#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

echo "==> 1. Installing dependencies..."
pip install -r requirements.txt

echo "==> 2. Validating and collecting static files..."
python manage.py collectstatic --noinput

echo "==> 3. Running automated test suite (safety gate)..."
python manage.py test

echo "==> 4. Applying database migrations..."
python manage.py migrate

echo "==> Build and verification successful!"