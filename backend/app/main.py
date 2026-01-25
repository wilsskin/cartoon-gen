"""
FastAPI Backend for Cartoon Generator

SMOKE TEST INSTRUCTIONS:
=======================

1. Local Development:
   - Ensure backend/.env contains DATABASE_URL pointing to your Neon Postgres instance
   - Start the backend: cd frontend && npm run dev:backend
   - Or manually: cd backend && python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

2. Test Database Connection:
   curl http://localhost:8000/api/debug/db
   
   Expected response: {"ok": true}
   
   If connection fails: {"ok": false, "error": "..."}

3. Production (Vercel):
   - Ensure DATABASE_URL is set in Vercel environment variables
   - Visit: https://your-app.vercel.app/api/debug/db
   - Should return: {"ok": true}
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

# Load environment variables from backend/.env
# This ensures DATABASE_URL is available for database connections
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# Safe debug log - only indicates if DATABASE_URL is set, never prints the value
print(f"ENV LOADED: DATABASE_URL set? {bool(os.environ.get('DATABASE_URL'))}")

# Import our image generation service
from . import services

# Import database module
# db.py is in the parent directory (backend/), so we add it to the path
import sys
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))
from db import get_db
from services.rss_ingest import run_rss_ingest
from services.classify_category import classify_category

# Define the base directory of the backend
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

# --- Middleware ---
# Allow frontend running on localhost:5173 to make requests
origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static File Serving ---
# This serves your pre-generated images from the /static/images directory
static_files_path = BASE_DIR.parent / "static"
app.mount("/static", StaticFiles(directory=static_files_path), name="static")

# --- Pydantic Models for Request Body Validation ---
class ImageRequest(BaseModel):
    basePrompt: str
    style: str

# --- API Endpoints ---
# Maximum number of news items to return from database
MAX_NEWS_ITEMS = 30

# Only categories we allow clients to see.
ALLOWED_CATEGORIES = {"World", "Politics", "Business", "Technology", "Culture"}

@app.get("/api/news")
def get_news(db: Session = Depends(get_db)):
    """
    Returns live RSS items from the database, or falls back to static news.json.
    
    Maintains the existing frontend response contract:
    - Array of objects with: id, headline, summary, sourceName, sourceUrl, 
      pregeneratedCaption, basePrompt, initialImageUrl, category
    """
    try:
        # Query database for latest RSS items
        result = db.execute(
            text("""
                SELECT 
                    i.id,
                    i.title,
                    i.summary,
                    i.url,
                    i.published_at,
                    i.fetched_at,
                    i.category,
                    f.name as feed_name
                FROM items i
                JOIN feeds f ON i.feed_id = f.id
                ORDER BY i.published_at DESC NULLS LAST, i.fetched_at DESC
                LIMIT :limit
            """),
            {"limit": MAX_NEWS_ITEMS}
        )
        
        rows = result.fetchall()
        
        if rows and len(rows) > 0:
            # Map database rows to frontend contract
            news_items = []
            for idx, row in enumerate(rows):
                # Use numeric ID for frontend compatibility (hash of UUID, ensure positive)
                item_id = abs(hash(str(row[0]))) % (10**9)
                
                # Use published_at if available, otherwise fetched_at
                date = row[4] if row[4] else row[5]
                
                # Generate basePrompt from title and summary
                title = row[1] or ""
                summary = row[2] or ""
                base_prompt = f"{title}. {summary[:100]}" if summary else title
                
                # Generate pregeneratedCaption from title (simplified)
                caption = title[:80] + "..." if len(title) > 80 else title
                
                raw_category = (row[6] or "").strip()
                # Ensure category is always one of the 5 buckets, even if older DB rows
                # still contain RSS tags or "general".
                if raw_category in ALLOWED_CATEGORIES:
                    category = raw_category
                else:
                    category = classify_category(title, f"{summary} {raw_category}".strip())

                news_item = {
                    "id": item_id,
                    "headline": title,
                    "summary": summary or "",
                    "sourceName": row[7] or "Unknown Source",  # feed_name
                    "sourceUrl": row[3] or "",  # url
                    "pregeneratedCaption": caption,
                    "basePrompt": base_prompt,
                    "initialImageUrl": "",  # RSS items don't have pre-generated images (empty string for frontend compatibility)
                    "category": category,  # one of 5 buckets
                }
                news_items.append(news_item)
            
            return news_items
        
        # Fallback to static news.json if no items found
        return _load_static_news()
    
    except Exception as e:
        # Log error without exposing secrets
        error_msg = str(e)
        if "DATABASE_URL" in error_msg or "password" in error_msg.lower():
            error_msg = "Database query error"
        print(f"Error fetching news from database: {error_msg}")
        
        # Fallback to static news.json on error
        return _load_static_news()


def _load_static_news():
    """Load and return static news.json as fallback"""
    data_file_path = BASE_DIR.parent / "data" / "news.json"
    try:
        with open(data_file_path, "r") as f:
            data = json.load(f)
        # Ensure fallback items have a 5-bucket category too (Culture is last resort)
        for item in data:
            headline = item.get("headline", "")
            summary = item.get("summary", "")
            item["category"] = classify_category(headline, summary)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="News data file not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.get("/api/debug/news-source")
def debug_news_source(db: Session = Depends(get_db)):
    """
    Debug endpoint to check which data source is being used.
    Returns { "source": "db" } or { "source": "fallback" }
    """
    try:
        result = db.execute(
            text("""
                SELECT COUNT(*) 
                FROM items
                LIMIT 1
            """)
        )
        count = result.scalar()
        
        if count and count > 0:
            return {"source": "db"}
        else:
            return {"source": "fallback"}
    except Exception:
        return {"source": "fallback"}

@app.post("/api/generate-image")
async def generate_image(request: ImageRequest):
    """
    Receives a base prompt and a style, constructs a final prompt,
    and calls the image generation service.
    """
    # Fail loudly (but safely) if the server is not configured for image generation.
    # Never log or return the key value.
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")

    style_modifiers = {
        "Funnier": "in a highly exaggerated, funny, satirical cartoon style, vibrant colors",
        "More Absurd": "in a surreal, abstract, and absurd art style, dreamlike, bizarre",
        "Labubu": "in the whimsical Labubu toy art style — all human figures reimagined as Labubu-like characters with big heads, small bodies, and sharp teeth; expressive pastel colors, vinyl toy aesthetic, cute but mischievous mood, maintaining the original political scene composition; cinematic lighting, soft textures, collectible figure look",
    }

    modifier = style_modifiers.get(request.style, "")
    final_prompt = f"{request.basePrompt}, {modifier}"

    print(f"Generating image with prompt: {final_prompt}")

    # Call the image generation service
    try:
        image_url = services.generate_satire_image(final_prompt)
    except RuntimeError as e:
        # Surface expected configuration errors clearly.
        msg = str(e)
        if "GEMINI_API_KEY" in msg:
            raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")
        raise HTTPException(status_code=500, detail="Image generation is not configured")

    if image_url:
        # The URL is now a Base64 data URL
        return {"imageUrl": image_url}
    else:
        raise HTTPException(status_code=500, detail="Failed to generate image.")

@app.get("/")
def read_root():
    return {"status": "Backend is running"}


@app.get("/api/debug/db")
def debug_db(db: Session = Depends(get_db)):
    """
    Healthcheck endpoint to verify database connectivity.
    
    Tests the connection by executing SELECT 1.
    Returns {"ok": true} on success, or {"ok": false, "error": "..."} on failure.
    """
    try:
        # Execute a simple query to test the connection
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        return {"ok": True}
    except Exception as e:
        # Return error without exposing sensitive details
        error_msg = str(e)
        # Sanitize error message to avoid leaking connection details
        # Remove any potential secrets from error messages
        sanitized_error = error_msg
        if "DATABASE_URL" in error_msg or "password" in error_msg.lower() or "@" in error_msg:
            sanitized_error = "Database connection error"
        return {"ok": False, "error": sanitized_error}


@app.post("/api/debug/ingest")
def debug_ingest():
    """
    Manual trigger endpoint for RSS ingestion (local testing only).
    
    This endpoint has no authentication and should be removed or secured
    before production deployment.
    
    Returns summary of ingestion run.
    """
    try:
        summary = run_rss_ingest()
        return summary
    except Exception as e:
        # Sanitize error messages
        error_msg = str(e)
        if "DATABASE_URL" in error_msg or "password" in error_msg.lower():
            error_msg = "Ingestion error"
        raise HTTPException(status_code=500, detail={"error": error_msg})


@app.post("/api/cron/pull-feeds")
def cron_pull_feeds(x_cron_secret: str = Header(..., alias="X-Cron-Secret")):
    """
    Production cron endpoint for RSS feed ingestion.
    
    Requires X-Cron-Secret header matching CRON_SECRET environment variable.
    Returns summary of ingestion run.
    """
    # Get CRON_SECRET from environment
    cron_secret = os.environ.get("CRON_SECRET")
    
    if not cron_secret:
        raise HTTPException(status_code=500, detail={"error": "CRON_SECRET not configured"})
    
    # Verify secret (constant-time comparison to prevent timing attacks)
    import hmac
    if not hmac.compare_digest(x_cron_secret, cron_secret):
        raise HTTPException(status_code=403, detail={"error": "Invalid CRON_SECRET"})
    
    try:
        summary = run_rss_ingest()
        return summary
    except Exception as e:
        # Sanitize error messages
        error_msg = str(e)
        if "DATABASE_URL" in error_msg or "password" in error_msg.lower() or "CRON_SECRET" in error_msg:
            error_msg = "Ingestion error"
        raise HTTPException(status_code=500, detail={"error": error_msg})
