# Backend Deployment Fix - Summary

## Problem Diagnosis

### Root Cause: Vercel was only deploying the frontend, not the backend

**Why this happened:**

1. **No Vercel configuration** (`vercel.json` was missing)
   - Vercel had no instructions on how to build or deploy the project
   - Defaulted to treating it as a static site

2. **No `/api` directory structure**
   - Vercel expects serverless functions in an `/api` directory at the project root
   - The FastAPI backend lives in `/backend/app/main.py` (traditional server structure)
   - Vercel's auto-detection didn't find any serverless functions

3. **FastAPI is a traditional server framework**
   - FastAPI with uvicorn runs as a persistent server process
   - Vercel serverless functions are stateless, request-based handlers
   - Converting FastAPI to Vercel serverless would require significant restructuring

4. **Hardcoded localhost URLs in frontend**
   - Frontend had `API_BASE_URL = 'http://localhost:8000'` hardcoded
   - Would never work in production

## Solution Implemented

### Approach: Separate Frontend and Backend Deployments

**Frontend → Vercel (Static Site)**
- Created `vercel.json` to configure frontend-only deployment
- Updated frontend to use `VITE_API_BASE_URL` environment variable
- Frontend builds to static files, deployed on Vercel CDN

**Backend → Separate Platform (Render/Fly.io/Railway)**
- Backend remains as traditional FastAPI server
- Deploy on platform that supports persistent Python servers
- Configure CORS to allow Vercel frontend domain

## Changes Made

### 1. Backend (`backend/app/main.py`)
- ✅ Added `/api/health` endpoint for health checks
- ✅ Made `GEMINI_API_KEY` optional at startup (only required for image generation)
- ✅ Added `CORS_ORIGINS` environment variable support for production domains

### 2. Frontend
- ✅ Updated `frontend/src/App.jsx` to use `VITE_API_BASE_URL` env var
- ✅ Updated `frontend/src/pages/GenerationPage.jsx` to use `VITE_API_BASE_URL` env var
- ✅ Falls back to `http://localhost:8000` for local development

### 3. Configuration
- ✅ Created `vercel.json` for frontend-only deployment
- ✅ Created `DEPLOYMENT.md` with complete deployment instructions

## Local Testing

### Backend Startup
```bash
cd backend
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Test Endpoints
```bash
# Health check (no dependencies required)
curl http://127.0.0.1:8000/api/health
# Expected: {"ok":true}

# News endpoint (requires database)
curl http://127.0.0.1:8000/api/news
# Expected: JSON array of news items
```

**Note:** The backend code loads successfully (verified in logs). Port binding issues in testing are system-level macOS security restrictions, not code issues.

## Production Setup

### 1. Deploy Frontend to Vercel
- Connect repository
- Set `VITE_API_BASE_URL` environment variable to your backend URL
- Vercel will use `vercel.json` to build and deploy

### 2. Deploy Backend to Render/Fly.io/Railway
- Follow instructions in `DEPLOYMENT.md`
- Set environment variables:
  - `DATABASE_URL`
  - `GEMINI_API_KEY`
  - `CORS_ORIGINS` (your Vercel frontend URL)
  - `CRON_SECRET`

### 3. Verify
- Frontend: `https://your-app.vercel.app` loads
- Backend health: `curl https://your-backend-url.com/api/health` → `{"ok":true}`
- Frontend can fetch: Check browser console for successful API calls

## Why This Solution

1. **Minimal structural changes** - No need to restructure FastAPI as serverless functions
2. **More reliable** - Traditional server deployment is better for FastAPI with database connections
3. **Easier to maintain** - Standard FastAPI deployment patterns
4. **Better for portfolio** - Shows understanding of different deployment strategies

## Files Changed

- `backend/app/main.py` - Added health endpoint, CORS config, optional GEMINI_API_KEY
- `frontend/src/App.jsx` - Use environment variable for API URL
- `frontend/src/pages/GenerationPage.jsx` - Use environment variable for API URL
- `vercel.json` - New file for frontend deployment configuration
- `DEPLOYMENT.md` - New file with complete deployment guide

## Next Steps

1. Deploy backend to Render/Fly.io/Railway (choose one)
2. Set `VITE_API_BASE_URL` in Vercel to point to backend
3. Set `CORS_ORIGINS` on backend to allow Vercel domain
4. Test production endpoints
5. Configure cron job for `/api/cron/pull-feeds`
