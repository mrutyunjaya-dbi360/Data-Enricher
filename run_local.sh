#!/usr/bin/env bash
# ScrapeOps — local run (no Docker)
set -e
cd "$(dirname "$0")/backend"

export USE_SQLITE="${USE_SQLITE:-true}"
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-dev-local-secret-change-me}"
export DEBUG=true
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"

if [ -z "$DATASOURCES_ENCRYPTION_KEY" ]; then
  export DATASOURCES_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  echo "Generated DATASOURCES_ENCRYPTION_KEY (set permanently in .env for stable decrypt):"
  echo "  $DATASOURCES_ENCRYPTION_KEY"
fi

# Optional: load .env from project root
if [ -f ../.env ]; then
  set -a
  # shellcheck disable=SC1091
  source ../.env
  set +a
  export USE_SQLITE="${USE_SQLITE:-true}"
fi

echo "==> Installing Python deps (user)..."
pip3 install --user -q -r requirements.txt 2>/dev/null || pip3 install --user -r requirements.txt

echo "==> Migrating..."
python3 manage.py migrate --noinput

echo "==> Seeding default tenant + admin (admin@scrapeops.local / admin12345)..."
python3 manage.py seed_tenant --email admin@scrapeops.local --password admin12345 || true

echo ""
echo "Start in two terminals:"
echo "  1) API:   cd backend && USE_SQLITE=true python3 manage.py runserver 0.0.0.0:8000"
echo "  2) Worker: cd backend && USE_SQLITE=true celery -A scrapeops worker -l info -c 1"
echo ""
echo "Frontend: serve the frontend/ folder on port 80 or open index.html via any static server,"
echo "  e.g.  cd frontend && python3 -m http.server 8080"
echo "  then open http://localhost:8080  (API must be proxied or set API to http://localhost:8000/api)"
echo ""
echo "Login: admin@scrapeops.local / admin12345"
