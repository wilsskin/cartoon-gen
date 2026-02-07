# CartoonGen Architecture and Deployment

**Production URL:** https://cartoon-gen1.vercel.app/

## Purpose

CartoonGen is a web app that:
- pulls news headlines daily from RSS feeds
- displays them in a clean frontend
- generates satirical cartoon images from headlines using AI (Google Gemini)
- keeps the system simple, secure, and minimal

---

## High-Level Architecture

- **Frontend:** React + Vite
- **Backend:** FastAPI
- **Database:** Neon Postgres
- **Hosting:** Vercel (single project)
- **Scheduling:** Vercel Cron

Everything runs in a single Vercel project—no separate backend deployment.

---

## Repository Structure

| Path | Purpose |
|------|---------|
| `/frontend` | React frontend built with Vite |
| `/backend/app/main.py` | FastAPI application with all backend logic |
| `/backend/services/` | RSS ingestion, category classification, image generation |
| `/backend/data/` | feeds.json (RSS config), news.json (static fallback) |
| `/api/index.py` | Vercel serverless entry point—imports FastAPI app |
| `/api/requirements.txt` | Python dependencies for Vercel serverless |
| `vercel.json` | Build config, routing, cron schedule |

---

## How Routing Works

- **Frontend routes** (e.g. `/`, `/generate`) → rewritten to `/index.html` (SPA)
- **API routes** (`/api/*`) → handled by FastAPI via Vercel serverless
- Rewrite `/api/:path*` → `/api` so all API requests hit the FastAPI handler

**Frontend API calls:**
- **Production (Vercel):** Relative URLs (`/api/news`, `/api/generate-image`) on the same domain—no `VITE_API_BASE_URL` needed
- **Local dev:** `http://localhost:8000` (backend runs separately)

---

## Vercel Deployment

### Build Configuration

- **Root directory:** Project root (default)
- **Build command:** `npm run build --prefix frontend`
- **Output directory:** `frontend/dist`
- **Install command:** `npm ci --prefix frontend`
- **Framework preset:** Vite

The `api/` folder is automatically detected; Vercel deploys Python serverless functions from it.

### API Serverless Wiring

- `api/index.py` adds `backend` to `sys.path` and imports `app` from `backend.app.main`
- **Export only `app`** (ASGI)—do not set `handler = app`; Vercel expects `handler` to be a `BaseHTTPRequestHandler` class, which causes `TypeError: issubclass() arg 1 must be a class`

---

## Environment Variables (Vercel)

Configure in **Project Settings → Environment Variables** for Production (and Preview if needed).

### Required

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Neon Postgres connection string (e.g. `postgresql://user:pass@host/db?sslmode=require`) |
| `CRON_SECRET` | Secret for authenticating Vercel Cron calls to `/api/cron/pull-feeds` |

### Optional

| Variable | Purpose | Default |
|----------|---------|---------|
| `GEMINI_API_KEY` | Google Gemini API key for image generation | Not set—image generation returns 500 if missing |
| `ALLOW_STATIC_NEWS_FALLBACK` | Use `news.json` when DB has no today's items | `false` |
| `CORS_ORIGINS` | Comma-separated allowed origins (rarely needed when frontend/API share domain) | — |
| `DEBUG_MODE` | Enable `POST /api/debug/pull-feeds` for manual ingest | `false` |
| `DEBUG_TIME_WINDOWS` | Log time window calculations | `false` |
| `DEBUG_RSS_DUMP` | On parse failure or 0 entries (with 200), save raw feed XML to a temp file and log path | `false` |

### Where to set environment variables

- **Vercel:** Project Settings → Environment Variables. Add each variable for Production (and Preview if needed). Redeploy after changing.
- **Local:** Create `backend/.env` with the same variable names (e.g. `GEMINI_API_KEY=...`). The backend loads `.env` via python-dotenv at startup.

### Image generation (Gemini) and free-tier

Image generation uses **Gemini 2.5 Flash Image** (`gemini-2.5-flash-image`) via the Google AI Studio / Gemini API. Set `GEMINI_API_KEY` to a key from [Google AI Studio](https://aistudio.google.com/apikey).

**Common free-tier errors:**

- **429 (rate limit)** — Too many requests per minute; the backend retries with backoff. If you see this in the UI, wait a minute and try again.
- **Quota exceeded** — Daily or per-minute quota for the model is used up. Check usage in Google AI Studio; quotas reset on their schedule.
- **Model access** — Ensure the key has access to the image model (e.g. enable the Gemini API and the image generation model for your project).

---

### Integration Checklist

- [ ] `DATABASE_URL` set (Neon connection string)
- [ ] `CRON_SECRET` set (for daily RSS ingestion)
- [ ] `GEMINI_API_KEY` set when ready for image generation
- [ ] Neon database schema initialized (`python3 -m backend.scripts.init_db` or equivalent)

---

## Cron Job

- **Path:** `GET /api/cron/pull-feeds` (Vercel Cron) or `POST /api/cron/pull-feeds` (manual trigger)
- **Schedule:** `0 16 * * *` (16:00 UTC daily ≈ 8:00 AM Pacific)
- **Auth:** `Authorization: Bearer <CRON_SECRET>` or `X-Cron-Secret: <CRON_SECRET>`

**Important:** Vercel Cron sends GET requests by default. The endpoint supports both GET and POST for compatibility.

The cron fetches RSS feeds from `backend/data/feeds.json`, upserts items into the database, and updates `fetched_at` so `/api/news` returns today's headlines.

### Data Retention (Auto-Cleanup)

The cron job automatically cleans up old data to prevent database bloat:

| Table | Retention | Purpose |
|-------|-----------|---------|
| `items` | 7 days | News headlines (only "today" shown in UI) |
| `runs` | 30 days | Cron execution logs for debugging |
| `feed_run_errors` | 30 days | Error logs for debugging |
| `rate_limits` | 1 hour | Per-IP rate limit tracking for image generation |

Cleanup runs at the end of each cron execution and is non-blocking (failures don't affect ingestion).

---

## Rate Limiting

Image generation (`POST /api/generate-image`) is rate-limited per IP address:

| Setting | Value |
|---------|-------|
| Max requests | 10 per window |
| Window | 5 minutes |
| Storage | `rate_limits` table in Postgres |
| Response when exceeded | `429 Too Many Requests` with `Retry-After` header |

**How it works:**
- Each image generation request records the client IP and timestamp in the `rate_limits` table
- Before each generation, the backend counts requests from that IP in the last 5 minutes
- If the count exceeds 10, the request is rejected with a 429 and a human-readable message
- The `Retry-After` header tells the client how many seconds to wait
- The frontend detects 429 responses and displays a dedicated "Slow down!" message
- Old rate limit entries are cleaned up hourly by the cron job

**Client IP detection:** Uses `X-Forwarded-For` header (set by Vercel's proxy) with fallback to `request.client.host` for local development.

**Recommended:** Also set per-minute and per-day quota limits on the Gemini API key in Google Cloud Console as a global cost safety net.

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Health check—returns `{"ok": true, "hasApiKey": boolean, "model": string}` (never exposes the key) |
| GET | `/api/news` | Today's headlines (filtered by `fetched_at` in Pacific Time) |
| POST | `/api/generate-image` | Generate cartoon (body: `prompt` and/or `headlineId` + `style`)—rate limited; returns `{ok, imageBase64?, mimeType?, model?, requestId?}` or `{ok: false, error: {...}}` |
| GET | `/api/cron/pull-feeds` | RSS ingestion (Vercel Cron—requires `CRON_SECRET`) |
| POST | `/api/cron/pull-feeds` | RSS ingestion (manual trigger—requires `CRON_SECRET`) |
| GET | `/api/debug/db` | Database connectivity check |
| POST | `/api/debug/ingest` | Manual RSS ingest (no auth—use with caution) |

---

## Verification After Deployment

1. **Health:** `https://<your-app>.vercel.app/api/health` → `{"ok": true}`
2. **Database:** `https://<your-app>.vercel.app/api/debug/db` → `{"ok": true}`
3. **News:** `https://<your-app>.vercel.app/api/news` → JSON array of headlines (or `[]` if cron hasn't run)
4. **Frontend:** `https://<your-app>.vercel.app/` → Landing page with headlines

If `/api/*` returns HTML or 404, routing is misconfigured (check `vercel.json` rewrites).

---

## Things to Remember

- **Root directory:** Must be repo root so `backend/` and `api/` are included in the deployment
- **No `typing` in requirements:** Do not add `typing` to `api/requirements.txt`—it conflicts with FastAPI on Vercel
- **Path resolution:** Use `Path(__file__).resolve()` for file paths (e.g. `feeds.json`, `news.json`) so they work in serverless
- **Image generation:** Requires `GEMINI_API_KEY`; without it, `/api/generate-image` returns 500
- **Cron:** Ensure Vercel Cron is enabled for the project and `CRON_SECRET` matches what Vercel sends
- **Vite cache:** If frontend changes don't appear after editing, delete `frontend/node_modules/.vite/` and restart the dev server. Vite caches transformed modules and may serve stale code, especially after renaming or deleting asset files. HMR can silently fail when an import references a file that no longer exists

---

## Design Principles

- Prefer removing broken logic over adding layers
- Avoid proxy services or duplicate deployments
- Keep infrastructure minimal
- One backend, one frontend, one database
- Fix issues at the source, not with overrides

---

## Frontend Notes

- **Filter:** Single-select by news source, reorders headlines (selected source first)
- **Pagination:** Shows 5 headlines at a time, More/Less buttons add/remove 5
- **Animations:** Headlines cascade in on load and filter change (see `DESIGN_SYSTEM.md`)
