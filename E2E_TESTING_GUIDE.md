# JobXplore — End-to-End Testing Guide

##### Start everything
> In the /Docker directory...
docker && docker compose up -d

##### Open the web app
open http://localhost:3000

##### Monitor pipeline/worker logs
docker compose logs worker -f

##### Stop when done
docker compose stop

##### Full restart
docker compose up -d --build web

---

docker compose build --no-cache api worker
docker compose up -d api worker

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Automated Unit Tests (no Docker needed)](#2-automated-unit-tests-no-docker-needed)
3. [Start the Docker Stack](#3-start-the-docker-stack)
4. [Run Database Migrations](#4-run-database-migrations)
5. [Verify the API](#5-verify-the-api)
6. [Verify the Web App](#6-verify-the-web-app)
7. [Load the Chrome Extension](#7-load-the-chrome-extension)
8. [End-to-End Workflow](#8-end-to-end-workflow)
9. [Automated Integration Tests (inside Docker)](#9-automated-integration-tests-inside-docker)
10. [Tear Down](#10-tear-down)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prerequisites

### Required software

| Tool | Minimum version | Check |
|---|---|---|
| Docker + Docker Compose | 24.x / v2.x | `docker compose version` |
| Node.js | 20.x | `node --version` |
| npm | 10.x | `npm --version` |
| Google Chrome / Chromium | any recent | `google-chrome --version` |
| Python (for CLI pipeline only) | 3.12 | `python3 --version` |

### Environment files

Both env files should already exist with your Supabase credentials:

```
apps/api/.env          ← DATABASE_URL, SUPABASE_*, ENCRYPTION_KEY, REDIS_URL, etc.
apps/web/.env.local    ← NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL
```

If either file is missing, copy from the examples and fill in credentials:

```bash
cp apps/api/.env.example apps/api/.env        # if it exists
cp apps/web/.env.local.example apps/web/.env.local
```

---

## 2. Automated Unit Tests (no Docker needed)

These tests run entirely locally and do **not** require the Docker stack or a live database.

### 2a. API unit tests (Python)

The API tests use SQLite in-memory, so no PostgreSQL is needed.

```bash
# From project root — install deps into a local venv if not already done
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run just unit tests (pure functions, no DB fixtures)
pytest tests/unit/ -v

# Expected output:
# tests/unit/test_alignment_scorer.py::TestScoreToGrade::test_perfect_score_is_a_plus  PASSED
# tests/unit/test_alignment_scorer.py::TestScoreToGrade::test_zero_score_is_d          PASSED
# tests/unit/test_alignment_scorer.py::TestTextMatcher::test_direct_match               PASSED
# ... (25+ tests)
# tests/unit/test_period_start.py::TestPeriodStart::test_today_is_midnight             PASSED
# ... all PASSED

cd ../..
```

### 2b. API integration tests (SQLite in-memory)

```bash
cd apps/api
source .venv/bin/activate

# Run all tests (unit + integration, all using SQLite in-memory)
pytest -v

# Expected: 60+ tests, all PASSED
# The only skip to expect is GET /timeline if the DATE cast triggers a SQLite quirk
cd ../..
```

### 2c. Chrome extension tests (vitest)

```bash
cd apps/extension
npm install
npm test

# Expected output:
# ✓ src/__tests__/job-board-detector.test.ts (18 tests)
# ✓ src/__tests__/base-filler.test.ts (12 tests)
# Test Files  2 passed
# Tests       30 passed
```

### 2d. Web app tests (vitest)

```bash
cd apps/web
npm install
npm test

# Expected output:
# ✓ src/__tests__/api-client.test.ts (18 tests)
# Test Files  1 passed
# Tests       18 passed
```

### 2e. Run everything with one script

```bash
# From project root:
./scripts/run_tests.sh all
```

---

## 3. Start the Docker Stack

### 3a. Start all six services

```bash
cd docker
docker compose up -d
```

Services started:

| Service | Port | Purpose |
|---|---|---|
| `db` | 5432 | PostgreSQL (local dev DB) |
| `redis` | 6379 | Celery broker + result backend |
| `browserless` | 3001 | Chrome for server-side scraping |
| `api` | 8000 | FastAPI backend |
| `worker` | — | Celery pipeline worker |
| `web` | 3000 | Next.js frontend |

### 3b. Confirm all services are healthy

```bash
docker compose ps
# All should show "running" or "healthy". Give it ~30s for db and redis.

docker compose logs api --tail=20
# Should end with: INFO:     Application startup complete.

docker compose logs worker --tail=20
# Should end with: celery@... ready.
```

### 3c. Verify Docker connectivity

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","service":"JobXplore API"}

curl http://localhost:3000
# Expected: HTML response (Next.js page)
```

---

## 4. Run Database Migrations

The Supabase-hosted PostgreSQL already has tables if you ran migrations previously.
If this is a fresh setup, run all four Alembic migrations.

### 4a. Run migrations against Supabase

```bash
cd apps/api
source .venv/bin/activate   # or use the Docker container (see note below)

# Point alembic at the Supabase DATABASE_URL from your .env
export DATABASE_URL_SYNC=$(grep DATABASE_URL_SYNC .env | cut -d= -f2-)
alembic -x db_url="$DATABASE_URL_SYNC" upgrade head
```

> **Alternative — run inside Docker** (avoids local venv setup):
> ```bash
> docker compose exec api alembic upgrade head
> ```

### 4b. Verify tables exist

```bash
docker compose exec api python3 -c "
from src.models import User, Job, ApplicationLog, Notification
print('Models import OK — tables exist')
"
```

Or check directly in Supabase Dashboard → Table Editor: you should see `users`, `jobs`, `resumes`, `search_configs`, `pipeline_runs`, `alignment_scores`, `input_indexes`, `application_logs`, `notifications`, `optimized_resumes`.

---

## 5. Verify the API

All API smoke tests use `curl`. Replace `<TOKEN>` below with a real Supabase JWT (obtain from step 6).

### 5a. Public endpoints (no auth)

```bash
# Health check
curl -s http://localhost:8000/health | python3 -m json.tool
# → {"status": "ok", "service": "JobXplore API"}

# OpenAPI docs (opens in browser)
open http://localhost:8000/docs
```

### 5b. Authenticated endpoints

After signing in via the web app (step 6), copy your JWT from the browser devtools:

1. Open `http://localhost:3000`
2. Sign in → open DevTools → Application → Local Storage → `sb-*-auth-token`
3. Copy the `access_token` value

```bash
TOKEN="<paste your JWT here>"

# Get your profile
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/users/profile | python3 -m json.tool

# Get notification count
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/notifications/count
# → {"unread": 0}

# Get application stats
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/application-logs/stats?period=all"
# → {"total": 0, "submitted": 0, ...}
```

---

## 6. Verify the Web App

### 6a. Open the app

Navigate to `http://localhost:3000`

### 6b. Sign up / Sign in

1. Click **Sign Up** — use any email + password
2. Check your email for the Supabase confirmation link and confirm
3. Sign in — you should land on `/dashboard`

### 6c. Smoke test each dashboard page

| Page | URL | What to verify |
|---|---|---|
| Dashboard | `/dashboard` | Loads with stat cards (0 counts) |
| Jobs | `/dashboard/jobs` | Empty state — "No jobs yet" |
| Searches | `/dashboard/searches` | Empty state — "No search configs" |
| Resumes | `/dashboard/resumes` | Empty state — "Upload your resume" |
| Analytics | `/dashboard/analytics` | Period buttons, all charts render (empty) |
| Settings | `/dashboard/settings` | Profile form loads |
| Alignment | `/dashboard/alignment` | Setup wizard or alignment table |
| Pipelines | `/dashboard/pipelines` | Empty run history |

### 6d. Update your profile

1. Go to **Settings**
2. Fill in: Full Name, Phone, Location, Work Authorization
3. Click **Save** → success toast appears
4. Refresh the page → values persist

### 6e. Upload a resume

1. Go to **Resumes**
2. Upload a PDF resume
3. Verify it appears in the list with name and upload date
4. Check the API: `GET /api/v1/resumes/` returns the entry

---

## 7. Load the Chrome Extension

### 7a. Build the extension

```bash
cd apps/extension
npm install
npm run build
# Output goes to: apps/extension/dist/
```

### 7b. Load in Chrome

1. Open `chrome://extensions`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `apps/extension/dist/` folder
5. The JobXplore icon appears in the toolbar

### 7c. Configure the extension

1. Click the JobXplore extension icon → popup opens
2. Enter:
   - **API URL**: `http://localhost:8000`
   - **Your JWT token** (from step 5b) — or sign in via the popup if it has an auth flow
3. Click **Save**

### 7d. Verify extension connectivity

1. Click the extension icon
2. The popup should show your name or email (confirming auth works)
3. Check Chrome's extension background service worker for errors:
   - `chrome://extensions` → JobXplore → **Service Worker** → Inspect
   - Console should be free of errors

---

## 8. End-to-End Workflow

This section walks through the full pipeline: search → enrich → insights → alignment → autofill → analytics.

### 8a. Create a Search Configuration

1. Web app → **Searches** → **New Search**
2. Fill in:
   - Job title: `Marketing Analytics Manager`
   - Salary: `175000`
   - Job type: `Full-time`
   - Work mode: `Remote`
3. Click **Save**

### 8b. Run the Pipeline

1. Web app → **Pipelines** → **Run Pipeline**
2. Select your search config → click **Start**
3. Watch the pipeline status update: `queued → running → complete`
4. Pipeline stages complete in order:
   - Stage 1: Job search (LinkedIn scraping via Browserless)
   - Stage 2: Job detail extraction (apply URLs + descriptions)
   - Stage 3: Merge + deduplicate
   - Stage 5: JD insights (keyword extraction)
   - Stage 5.5: Alignment scoring
   - Stage 6: Resume optimization

> **Note on LinkedIn scraping**: Stage 1 requires valid LinkedIn cookies. If the pipeline fails at Stage 1 with an auth error, you need to re-upload cookies. See [§11 Troubleshooting](#11-troubleshooting).

### 8c. Review Jobs

1. Web app → **Jobs**
2. You should see scraped job listings with:
   - Title, company, location, salary range
   - Alignment score + grade (A+, A, B+, etc.)
3. Filter by company, sort by alignment score

### 8d. Check Insights

1. Web app → **Insights**
2. Verify keyword/skill frequency data populated from JD analysis

### 8e. Review Alignment Scores

1. Web app → **Alignment**
2. Top-matched jobs appear with their grade breakdown
3. If the input index is empty, go to **Alignment → Setup** and generate it first

### 8f. Test the Autofill Extension

1. Find a job with an **Apply URL** on a supported ATS (Greenhouse, Workday, Lever, SmartRecruiters, or LinkedIn Easy Apply)
2. Click the apply URL — the ATS form opens in Chrome
3. Click the JobXplore extension icon → **Fill This Form**
4. Watch the extension fill:
   - Personal info (name, email, phone)
   - Resume upload
   - Custom questions (where supported)
5. **Review every field before submitting** — do not auto-submit; always manually confirm
6. Submit the application

### 8g. Log the Application

After submitting, the extension should automatically log the result. Verify:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/application-logs/ | python3 -m json.tool
# → array with one entry, status: "submitted"
```

### 8h. Verify Notification

1. Web app → check the bell icon in the header
2. A notification should appear: "X high-alignment jobs found" (if pipeline found jobs with score ≥ 0.75)
3. Click the notification → mark as read → bell badge clears

### 8i. Check Analytics

1. Web app → **Analytics**
2. Select period: **This Week**
3. Verify:
   - Total count = 1 (the application just logged)
   - Line chart shows today's bar
   - Pie chart shows one "submitted" slice
   - Recent logs table shows the application

---

## 9. Automated Integration Tests (inside Docker)

To run the full Python test suite inside the Docker environment (with all dependencies installed):

```bash
# From project root:
docker build \
  -f docker/Dockerfile.api.test \
  -t jobxplore-api-test \
  .

docker run --rm \
  -e DATABASE_URL="sqlite+aiosqlite:///:memory:" \
  -e SUPABASE_JWT_SECRET="test-secret" \
  -e ENCRYPTION_KEY="dGVzdC1rZXktMzItYnl0ZXMtbG9uZy1wYWQ=" \
  jobxplore-api-test

# Expected: 60+ tests, all passed
```

Or use the convenience script:

```bash
./scripts/run_tests.sh api
```

---

## 10. Tear Down

```bash
# Stop all services (keep volumes — preserves DB data)
cd docker
docker compose stop

# Stop AND remove volumes (wipes the local PostgreSQL data)
docker compose down -v
```

---

## 11. Troubleshooting

### Pipeline fails at Stage 1 — LinkedIn auth error

LinkedIn cookies have expired. Re-upload them:

```bash
# CLI method (opens a browser for you to log in manually):
source venv/bin/activate
export PYTHONPATH="$(pwd)/src"
python3 src/job_extraction/manual_login.py
# Follow the prompts — saves cookies to config/linkedin_cookies.txt

# Then upload via the web app:
# Settings → LinkedIn Cookies → Upload File
```

### API container won't start — database connection refused

The `api` service connects to the Supabase cloud DB, not the local `db` container.
Verify the `DATABASE_URL` in `apps/api/.env` points to `db.roxualsilqmgjfmccdqk.supabase.co`
(not `localhost` or `db:5432`).

```bash
docker compose logs api | grep "DATABASE_URL\|connect\|error" -i
```

### Web app shows "Failed to fetch" errors

The web app calls `http://localhost:8000` which requires the `api` container to be running
**and** CORS to be configured for `http://localhost:3000`.

Check `apps/api/.env`:
```
CORS_ORIGINS=["http://localhost:3000"]
```

Then restart the API:
```bash
docker compose restart api
```

### Extension popup is blank / shows error

1. Check the extension's service worker console (`chrome://extensions` → JobXplore → Inspect service worker)
2. Common cause: the stored API URL points to the wrong host. Clear extension storage:
   ```javascript
   // In the service worker console:
   chrome.storage.local.clear(() => console.log('cleared'))
   ```
3. Re-enter the API URL and token in the popup

### Alembic migration fails — table already exists

The Supabase DB already has some tables from a previous run. Run only the pending migrations:

```bash
docker compose exec api alembic current   # show current revision
docker compose exec api alembic history   # show all revisions
docker compose exec api alembic upgrade head  # apply only what's missing
```

### `pytest` fails with "No module named 'src'"

The `pythonpath = .` in `pytest.ini` requires pytest to be run from the `apps/api/` directory:

```bash
cd apps/api
pytest
# NOT: pytest apps/api/  (from root — this won't find src)
```

### Vitest fails with "cannot find module '@shared/...'"

The path aliases in `vitest.config.ts` resolve relative to the package root. Run vitest from the package directory:

```bash
cd apps/extension
npm test
# NOT: npx vitest apps/extension/  (from root)
```
