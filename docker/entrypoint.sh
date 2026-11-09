#!/bin/bash
set -e
cd /app
python manage.py migrate --noinput
python manage.py collectstatic --noinput 2>/dev/null || true
exec "$@"
