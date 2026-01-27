# CartoonGen Architecture and Deployment

## Purpose

CartoonGen is a web app that:
- pulls news headlines daily
- displays them in a clean frontend
- generates satirical cartoon images from headlines using AI
- keeps the system simple, fast, and secure

The system intentionally avoids unnecessary services, wrappers, or complexity.

---

## High-Level Architecture

- Frontend: React + Vite
- Backend: FastAPI
- Database: Neon Postgres
- Hosting: Vercel
- Scheduling: Vercel Cron

Everything runs in a single Vercel project.

---

## Repository Structure

- /frontend  
  React frontend built with Vite

- /backend/app/main.py  
  FastAPI application containing all backend logic

- /api/index.py  
  Vercel serverless entry point that exposes the FastAPI app

- /api/requirements.txt  
  Python dependencies for Vercel serverless functions

- vercel.json  
  Deployment configuration, routing, and cron schedule

---

## How Routing Works

- All frontend routes are rewritten to `/index.html`
- All `/api/*` routes are excluded from rewrites
- `/api/*` requests are handled by FastAPI via Vercel serverless

This separation is enforced in `vercel.json`.

**Frontend API calls:**
- In production (Vercel), frontend calls relative `/api/*` routes on the same domain (no `VITE_API_BASE_URL` needed).
- In local dev, frontend uses `http://localhost:8000`.

---

## Backend on Vercel

Vercel requires backend code to live under `/api` to run as Python serverless functions.

`/api/index.py` imports the FastAPI app from `backend/app/main.py`.
No backend logic is duplicated or restructured.

---

## Database

- Uses Neon Postgres
- Connection is provided via `DATABASE_URL`
- Backend reads and writes directly to Neon
- No ORM magic or background workers

---

## Cron Job

- Runs once per day at 16:00 UTC
- Corresponds to ~8:00 AM Pacific
- Implemented using Vercel Cron

Cron calls: `POST /api/cron/pull-feeds`

Authentication:
- Primarily uses `Authorization: Bearer <CRON_SECRET>` (Vercel Cron format)
- Also accepts `X-Cron-Secret` header for backward compatibility
- Endpoint validates the secret before running

---

## Environment Variables (Vercel)

Required:
- DATABASE_URL
- CRON_SECRET

Optional:
- GEMINI_API_KEY (only required for image generation)

---

## Verification

After deployment, these endpoints should work:

- `/api/health`  
  Returns `{ "ok": true }`

- `/api/news`  
  Returns a JSON array of headlines

If these return HTML or 404, routing is misconfigured.

---

## Design Principles

- Prefer removing broken logic over adding layers
- Avoid proxy services or duplicate deployments
- Keep infrastructure minimal
- One backend, one frontend, one database
- Fix issues at the source, not with overrides
