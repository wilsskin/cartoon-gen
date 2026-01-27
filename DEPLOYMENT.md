# Deployment Guide

## Problem Diagnosis

**Why Vercel wasn't deploying the backend:**
1. **No `vercel.json` configuration** - Vercel had no instructions on how to build/deploy
2. **No `/api` directory structure** - Vercel expects serverless functions in `/api` at the project root, but the FastAPI backend lives in `/backend/app/main.py`
3. **FastAPI is a traditional server framework** - Not structured as Vercel serverless functions
4. **Hardcoded localhost URLs** - Frontend was hardcoded to `http://localhost:8000`

**Solution:** Deploy frontend on Vercel (static site) and backend separately on a platform that supports traditional Python servers (Render, Fly.io, Railway, etc.).

## Architecture

- **Frontend**: Vercel (static React/Vite build)
- **Backend**: Separate deployment on Render/Fly.io/Railway (FastAPI server)

## Local Development

### Backend Setup

```bash
# Navigate to backend directory
cd backend

# Install dependencies (if not already installed)
pip3 install -r requirements.txt

# Set up environment variables
# Create backend/.env file with:
# DATABASE_URL=your_postgres_connection_string
# GEMINI_API_KEY=your_gemini_api_key (optional for basic endpoints)
# CORS_ORIGINS=https://your-vercel-app.vercel.app (for production)

# Start the backend server
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or use the startup script
./start_backend.sh
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server (frontend only)
npm run dev

# Or start both frontend and backend together
npm run dev:full
```

### Testing Local Backend

Once the backend is running, test the endpoints:

```bash
# Health check (no database required)
curl http://127.0.0.1:8000/api/health
# Expected: {"ok":true}

# News endpoint (requires database)
curl http://127.0.0.1:8000/api/news
# Expected: JSON array of news items

# Database connection test
curl http://127.0.0.1:8000/api/debug/db
# Expected: {"ok":true} or {"ok":false,"error":"..."}
```

## Production Deployment

### Frontend (Vercel)

1. **Connect your repository to Vercel**
2. **Set environment variable in Vercel dashboard:**
   - `VITE_API_BASE_URL` = `https://your-backend-url.com`
   - Example: `https://cartoon-gen-backend.onrender.com`

3. **Vercel will automatically:**
   - Use `vercel.json` to configure the build
   - Build from `frontend/` directory
   - Deploy static files from `frontend/dist`

### Backend (Render/Fly.io/Railway)

Choose one platform:

#### Option A: Render (Recommended - Easiest)

1. **Create a new Web Service** on Render
2. **Connect your GitHub repository**
3. **Configure:**
   - **Build Command**: `cd backend && pip install -r requirements.txt`
   - **Start Command**: `cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Environment**: Python 3
   - **Root Directory**: `backend` (or leave blank and adjust paths)

4. **Set Environment Variables:**
   - `DATABASE_URL` - Your Neon Postgres connection string
   - `GEMINI_API_KEY` - Your Gemini API key
   - `CORS_ORIGINS` - Your Vercel frontend URL (e.g., `https://your-app.vercel.app`)
   - `CRON_SECRET` - Secret for cron endpoint authentication
   - `ALLOW_STATIC_NEWS_FALLBACK` - Set to `false` for production

5. **Deploy**

#### Option B: Fly.io

1. **Install Fly CLI**: `curl -L https://fly.io/install.sh | sh`
2. **Create `fly.toml` in backend directory:**
   ```toml
   app = "your-app-name"
   primary_region = "iad"

   [build]
     builder = "paketobuildpacks/builder:base"

   [http_service]
     internal_port = 8000
     force_https = true
     auto_stop_machines = true
     auto_start_machines = true
     min_machines_running = 0

   [[services]]
     protocol = "tcp"
     internal_port = 8000
   ```

3. **Deploy**: `cd backend && fly deploy`
4. **Set secrets**: `fly secrets set DATABASE_URL=... GEMINI_API_KEY=... CORS_ORIGINS=...`

#### Option C: Railway

1. **Create new project** on Railway
2. **Add GitHub repository**
3. **Set root directory** to `backend`
4. **Railway auto-detects Python** and runs `pip install -r requirements.txt`
5. **Set start command**: `python3 -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. **Add environment variables** in Railway dashboard

### Cron Jobs

For `/api/cron/pull-feeds` endpoint:

- **Render**: Use Render Cron Jobs (add in dashboard)
- **Fly.io**: Use `fly cron schedule` or external cron service
- **Railway**: Use Railway Cron Jobs or external service

**Cron Configuration:**
- **URL**: `https://your-backend-url.com/api/cron/pull-feeds`
- **Method**: POST
- **Headers**: `X-Cron-Secret: your_cron_secret_value`
- **Schedule**: Daily (e.g., `0 6 * * *` for 6 AM UTC)

## Environment Variables Summary

### Backend (.env or platform environment variables)
- `DATABASE_URL` - Postgres connection string (required)
- `GEMINI_API_KEY` - Gemini API key (required for image generation)
- `CORS_ORIGINS` - Comma-separated list of allowed origins (e.g., `https://your-app.vercel.app`)
- `CRON_SECRET` - Secret for cron endpoint authentication
- `ALLOW_STATIC_NEWS_FALLBACK` - Set to `false` in production
- `DEBUG_MODE` - Set to `false` in production

### Frontend (Vercel environment variables)
- `VITE_API_BASE_URL` - Backend API URL (e.g., `https://your-backend.onrender.com`)

## Verification Checklist

After deployment, verify:

- [ ] Frontend loads at Vercel URL
- [ ] Backend health check: `curl https://your-backend-url.com/api/health` returns `{"ok":true}`
- [ ] Frontend can fetch news: Check browser console for successful API calls
- [ ] CORS is configured: Frontend can make requests to backend
- [ ] Database connection works: Backend `/api/debug/db` returns `{"ok":true}`
- [ ] Cron endpoint is secured: Test with wrong secret returns 403

## Troubleshooting

### Backend returns 404 on Vercel
- **Cause**: Vercel is only deploying frontend, not backend
- **Solution**: Deploy backend separately (see above)

### CORS errors in browser
- **Cause**: Backend CORS_ORIGINS not configured
- **Solution**: Set `CORS_ORIGINS` environment variable on backend to your Vercel frontend URL

### Frontend can't connect to backend
- **Cause**: `VITE_API_BASE_URL` not set or incorrect
- **Solution**: Set `VITE_API_BASE_URL` in Vercel environment variables to your backend URL

### Database connection fails
- **Cause**: `DATABASE_URL` not set or incorrect
- **Solution**: Verify `DATABASE_URL` is set correctly on backend platform
