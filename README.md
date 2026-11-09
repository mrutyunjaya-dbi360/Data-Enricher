# ScrapeOps — Scraping-as-a-Service MVP

Phase 1 multi-tenant wrapper around the domain-finder + matcher + CrewAI scraper pipeline.

## Quick start (Docker)

```bash
cp .env.example .env
# Edit .env: set DJANGO_SECRET_KEY, DATASOURCES_ENCRYPTION_KEY, OPENAI_API_KEY, SERPER_API_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # paste into DATASOURCES_ENCRYPTION_KEY

docker compose up --build
```

- Frontend: http://localhost/
- API: http://localhost/api/
- Create admin:
  ```bash
  docker compose exec web python manage.py createsuperuser
  ```
  (or use the seed command if present)

## Local (no Docker)

```bash
cd backend
export USE_SQLITE=true
export DJANGO_SECRET_KEY=dev
export DATASOURCES_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
# separate terminal: celery -A scrapeops worker -l info -c 1
```

## Architecture

- **accounts** — User (email as username), Tenant, JWT auth
- **datasources** — encrypted Mongo URIs, SSRF guard
- **jobs** — submit / cancel / resume, Celery `run_job`
- **metrics** — Event stream, DocQuality, rollups, Report/Cost/Quality/Users APIs
- **pipeline** — ported combined_pipeline (step1/2/3 + helpers + CrewAI + Crawl4AI)

## Key flows

1. Admin provisions member (POST `/api/admin/users`) → password returned once.
2. Create datasource with public Mongo URI (SSRF-checked, Fernet-encrypted).
3. Submit job → Celery worker runs pipeline cycles → Events emitted → SSE progress.
4. Dashboard surfaces: Report (funnel), Cost, Quality, Users (admin).

See `TODO.md` for deferred items and `DECISIONS.md` for design choices.

## Tests

```bash
cd backend
USE_SQLITE=true python manage.py test
```

## Pipeline notes

Business rules (blacklists, prompts, cleaning, status lifecycle) are preserved from the original combined_pipeline.py. Config is injected via `JobConfig`; globals removed; credit exhaustion raises `CreditExpired` and pauses the job.

## Run without Docker

### Requirements
- Python 3.11+
- Redis (for Celery). Install: `sudo apt install redis-server` or `brew install redis`
- Optional: PostgreSQL (default local mode uses **SQLite**)

### Setup

```bash
cd scrapeops
cp .env.example .env
# Edit .env — at minimum:
#   DJANGO_SECRET_KEY=...
#   DATASOURCES_ENCRYPTION_KEY=...   # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#   OPENAI_API_KEY=...
#   SERPER_API_KEY=...
#   USE_SQLITE=true
#   REDIS_URL=redis://127.0.0.1:6379/0

./run_local.sh
```

### Three processes

```bash
# Terminal 1 — API
cd backend
export USE_SQLITE=true
export $(grep -v '^#' ../.env | xargs)   # optional: load .env
python3 manage.py runserver 0.0.0.0:8000

# Terminal 2 — Celery worker (needs Redis)
cd backend
export USE_SQLITE=true
celery -A scrapeops worker -l info -c 1

# Terminal 3 — Frontend static server
cd frontend
# Point API at Django:
#   edit js/config.js → window.SCRAPEOPS_API = "http://127.0.0.1:8000/api";
python3 -m http.server 8080
```

Open **http://localhost:8080** → login `admin@scrapeops.local` / `admin12345`.

### CORS
With `DEBUG=true`, CORS allows all origins so the frontend on :8080 can call :8000.

### No Redis?
Jobs will queue but not run until Redis + Celery worker are up. For a smoke test of the API only, Redis is not required.
