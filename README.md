# Cartoon Gen

Generate political cartoons from today's top headlines.

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

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for complete deployment instructions.

**Quick Summary:**
- Frontend deploys to Vercel (static site)
- Backend deploys separately to Render/Fly.io/Railway (FastAPI server)
- Set `VITE_API_BASE_URL` in Vercel to point to backend
- Set `CORS_ORIGINS` on backend to allow Vercel domain

## Project Structure

- `/backend` - FastAPI backend with database, RSS ingestion, image generation
- `/frontend` - React/Vite frontend
