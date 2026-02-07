# CartoonGen

Generate political cartoons from today's top headlines using AI.

## What It Does

CartoonGen pulls the latest headlines from major news outlets (WSJ, NYT, NBC, Fox, NPR), displays them in a clean interface, and lets you generate satirical cartoon illustrations for any headline. Click a headline to see an AI-generated political cartoon based on that story.

## How It Works

1. **Headlines** — A daily cron job fetches the top 3 stories from each RSS feed and stores them in a Neon Postgres database.
2. **Browse** — The landing page shows today's headlines, categorized by topic (World, Politics, Business, Technology, Culture).
3. **Generate** — Click any headline to go to the generation page. The app automatically generates a satirical cartoon for that story using Google's Gemini API.
4. **Download** — Save your cartoon as a PNG.

## Quick Start

### Local Development

**Backend:**
```bash
cd backend
pip3 install -r requirements.txt
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Or run both together:
```bash
cd frontend
npm run dev:full
```

## Project Structure

- `/frontend` — React + Vite frontend
- `/backend` — FastAPI backend (database, RSS ingestion, image generation)
- `/api` — Vercel serverless entry point for the backend

## Deployment & Configuration

For deployment details, environment variables, Vercel setup, and integration specifics, see **[ARCHITECTURE.md](./ARCHITECTURE.md)**.
