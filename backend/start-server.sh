#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Ensuring first admin exists (bootstrap)..."
python manage.py ensure_admin || echo "ensure_admin skipped/failed; continuing."

echo "Starting server..."
exec gunicorn backend.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${WEB_CONCURRENCY:-3}
