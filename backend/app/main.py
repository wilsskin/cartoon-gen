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
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

# Try to import zoneinfo (Python 3.9+), fallback to pytz if needed
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for older Python or systems without zoneinfo
    try:
        import pytz  # type: ignore[reportMissingModuleSource]
        ZoneInfo = pytz.timezone
    except ImportError:
        raise ImportError("zoneinfo or pytz is required for timezone support")

# Load environment variables from backend/.env
# This ensures DATABASE_URL and GEMINI_API_KEY are available
# This is the single source of truth for env loading - dotenv is loaded exactly once here
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# GEMINI_API_KEY is required for image generation but not for basic API endpoints
# The /api/generate-image endpoint will check for it and return an error if missing
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("WARNING: GEMINI_API_KEY is not configured. Image generation will not work.")

# Check if static news fallback is allowed (default: false for production safety)
ALLOW_STATIC_NEWS_FALLBACK = os.environ.get("ALLOW_STATIC_NEWS_FALLBACK", "false").lower() in ("true", "1", "yes")

# Check if debug time windows logging is enabled (default: false to avoid log spam)
DEBUG_TIME_WINDOWS = os.environ.get("DEBUG_TIME_WINDOWS", "false").lower() in ("true", "1", "yes")

# Check if debug mode is enabled (allows debug endpoints)
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() in ("true", "1", "yes")

# Application timezone - all "today" calculations use Pacific Time
APP_TIMEZONE = "America/Los_Angeles"

# Safe debug log - only indicates if keys are set, never prints the values
print(f"ENV LOADED: DATABASE_URL set? {bool(os.environ.get('DATABASE_URL'))}, GEMINI_API_KEY set? {bool(os.environ.get('GEMINI_API_KEY'))}, ALLOW_STATIC_NEWS_FALLBACK={ALLOW_STATIC_NEWS_FALLBACK}")

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
# Also allow production Vercel domains (configured via CORS_ORIGINS env var)
origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
]

# Add production origins from environment variable (comma-separated)
cors_origins_env = os.environ.get("CORS_ORIGINS", "")
if cors_origins_env:
    origins.extend([origin.strip() for origin in cors_origins_env.split(",") if origin.strip()])

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
    headlineId: str
    style: Optional[str] = None
    regenerate: bool = False
    # basePrompt is ignored if provided - kept for backward compatibility during migration
    basePrompt: Optional[str] = None

# --- API Endpoints ---
# Maximum number of news items to return from database
MAX_NEWS_ITEMS = 30

# Only categories we allow clients to see.
ALLOWED_CATEGORIES = {"World", "Politics", "Business", "Technology", "Culture"}

# Style allowlist for image generation
ALLOWED_STYLES = ["Default", "Funnier", "Drier", "More sarcastic", "More wholesome"]

# UUID pattern for validation (standard UUID format)
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)


def _is_valid_uuid(uuid_string: str) -> bool:
    """Check if a string is a valid UUID format"""
    return bool(UUID_PATTERN.match(uuid_string))


def _get_today_date_range() -> Tuple[datetime, datetime]:
    """
    Get today's date range for filtering in Pacific Time, converted to UTC for database queries.
    
    Computes "today" in America/Los_Angeles (Pacific Time) at 00:00:00,
    then converts to UTC for database comparison.
    
    Returns:
        Tuple of (today_start_utc, tomorrow_start_utc) as timezone-aware datetime objects in UTC.
        These can be passed directly to SQL queries for TIMESTAMPTZ comparisons.
    """
    # Get Pacific Time timezone
    pt_tz = ZoneInfo(APP_TIMEZONE)
    
    # Get today's date in Pacific Time
    now_pt = datetime.now(pt_tz)
    today_pt = now_pt.date()
    
    # Create today_start at 00:00:00 in Pacific Time
    today_start_pt = datetime.combine(today_pt, datetime.min.time(), tzinfo=pt_tz)
    
    # Create tomorrow_start at 00:00:00 in Pacific Time
    tomorrow_start_pt = today_start_pt + timedelta(days=1)
    
    # Convert to UTC for database queries (TIMESTAMPTZ comparisons)
    today_start_utc = today_start_pt.astimezone(timezone.utc)
    tomorrow_start_utc = tomorrow_start_pt.astimezone(timezone.utc)
    
    # Debug logging (only if flag is enabled)
    if DEBUG_TIME_WINDOWS:
        print(
            f"TODAY WINDOW PT: {today_start_pt.isoformat()} -> {tomorrow_start_pt.isoformat()}, "
            f"UTC: {today_start_utc.isoformat()} -> {tomorrow_start_utc.isoformat()}"
        )
    
    return today_start_utc, tomorrow_start_utc


@app.get("/api/news")
def get_news(db: Session = Depends(get_db)):
    """
    Returns live RSS items from the database for today only (Pacific Time), or falls back to static news.json.
    
    Only returns items fetched today in Pacific Time (fetched_at >= today 00:00 PT AND fetched_at < tomorrow 00:00 PT).
    The database comparison uses UTC boundaries converted from Pacific Time.
    
    Maintains the existing frontend response contract:
    - Array of objects with: id (UUID string for DB items, numeric for static), headline, summary, sourceName, sourceUrl, 
      pregeneratedCaption, basePrompt, initialImageUrl, category
    """
    try:
        today_start_utc, tomorrow_start_utc = _get_today_date_range()
        
        # Query database for items fetched today only (using UTC boundaries)
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
                WHERE i.fetched_at >= :today_start_utc 
                  AND i.fetched_at < :tomorrow_start_utc
                ORDER BY i.published_at DESC NULLS LAST, i.fetched_at DESC
                LIMIT :limit
            """),
            {
                "limit": MAX_NEWS_ITEMS,
                "today_start_utc": today_start_utc,
                "tomorrow_start_utc": tomorrow_start_utc,
            }
        )
        
        rows = result.fetchall()
        
        if rows and len(rows) > 0:
            # Map database rows to frontend contract
            news_items = []
            for idx, row in enumerate(rows):
                # Use UUID directly as stable unique identifier (convert to string)
                item_id = str(row[0])  # row[0] is the UUID
                
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
        
        # Fallback to static news.json only if flag is enabled
        if ALLOW_STATIC_NEWS_FALLBACK:
            return _load_static_news()
        else:
            # Return empty list if no items found and fallback is disabled
            return []
    
    except Exception as e:
        # Log error without exposing secrets
        error_msg = str(e)
        if "DATABASE_URL" in error_msg or "password" in error_msg.lower():
            error_msg = "Database query error"
        print(f"Error fetching news from database: {error_msg}")
        
        # Fallback to static news.json on error only if flag is enabled
        if ALLOW_STATIC_NEWS_FALLBACK:
            return _load_static_news()
        else:
            # Return empty list on error if fallback is disabled
            return []


def _load_static_news():
    """
    Load and return static news.json as fallback.
    Only called if ALLOW_STATIC_NEWS_FALLBACK is True.
    """
    if not ALLOW_STATIC_NEWS_FALLBACK:
        raise HTTPException(status_code=404, detail="Static news fallback is disabled")
    
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


def _lookup_headline_by_id(headline_id: str, db: Session) -> dict:
    """
    Look up a headline by its ID from the database or static fallback.
    
    For database items, the ID is the UUID (stable unique identifier).
    For static items, the ID is the numeric id field from news.json.
    
    Database lookup only matches items fetched today in Pacific Time (fetched_at >= today 00:00 PT AND fetched_at < tomorrow 00:00 PT).
    The database comparison uses UTC boundaries converted from Pacific Time.
    Static fallback is only used if ALLOW_STATIC_NEWS_FALLBACK is True.
    
    Args:
        headline_id: The headline ID as a string (UUID for DB items, numeric string for static items)
        db: Database session
        
    Returns:
        Dictionary with headline data: {headline, summary, id}
        
    Raises:
        HTTPException(404): If headline not found
    """
    # Determine if headline_id is a UUID or numeric
    is_uuid = _is_valid_uuid(headline_id)
    
    # First, try to find in database by UUID (only if it's a valid UUID format)
    if is_uuid:
        try:
            today_start_utc, tomorrow_start_utc = _get_today_date_range()
            
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
                    WHERE i.id::text = :headline_id
                      AND i.fetched_at >= :today_start_utc 
                      AND i.fetched_at < :tomorrow_start_utc
                """),
                {
                    "headline_id": headline_id,
                    "today_start_utc": today_start_utc,
                    "tomorrow_start_utc": tomorrow_start_utc,
                }
            )
            
            row = result.fetchone()
            if row:
                return {
                    "headline": row[1] or "",
                    "summary": row[2] or "",
                    "id": str(row[0]),  # UUID as string
                }
        except Exception as e:
            # Log specific error but don't expose details
            print(f"Database lookup error for UUID {headline_id}: {type(e).__name__}")
            # Continue to 404 below
    
    # Fallback to static news.json (only if numeric ID and flag is enabled)
    if not is_uuid and ALLOW_STATIC_NEWS_FALLBACK:
        try:
            headline_id_int = int(headline_id)
            data_file_path = BASE_DIR.parent / "data" / "news.json"
            with open(data_file_path, "r") as f:
                static_data = json.load(f)
            
            for item in static_data:
                if item.get("id") == headline_id_int:
                    return {
                        "headline": item.get("headline", ""),
                        "summary": item.get("summary", ""),
                        "id": item.get("id"),
                    }
        except (ValueError, FileNotFoundError):
            pass
    
    # Not found in either source
    raise HTTPException(status_code=404, detail=f"Headline with id {headline_id} not found")


def _build_prompt_template(headline: str, summary: str, style: str) -> str:
    """
    Build a server-side prompt template for image generation.
    
    Args:
        headline: The headline title
        summary: The headline summary/description
        style: The style name (must be from ALLOWED_STYLES)
        
    Returns:
        Complete prompt string for image generation
    """
    # Base template for political cartoon
    base_template = (
        "You are a political cartoonist creating a single-panel satirical cartoon. "
        "Create an illustration based on this news story:\n\n"
        f"Headline: {headline}\n"
        f"Summary: {summary}\n\n"
        "The cartoon should be satirical, thought-provoking, and visually engaging. "
        "Use symbolic imagery and avoid creating exact likenesses of real people. "
        "Focus on the political or social themes of the story."
    )
    
    # Add style-specific instructions
    style_instructions = {
        "Default": "Use a classic editorial cartoon style with clear symbolism and bold lines.",
        "Funnier": "Make it highly exaggerated, funny, and satirical with vibrant colors and comedic elements.",
        "Drier": "Use a more understated, dry wit approach with muted colors and subtle humor.",
        "More sarcastic": "Emphasize irony and sarcasm with sharp visual metaphors and pointed commentary.",
        "More wholesome": "Take a lighter, more positive approach while still maintaining the satirical edge.",
    }
    
    style_instruction = style_instructions.get(style, style_instructions["Default"])
    
    return f"{base_template}\n\nStyle: {style_instruction}"


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
async def generate_image(request: ImageRequest, db: Session = Depends(get_db)):
    """
    Generates an image based on a headline ID and optional style.
    
    The prompt is constructed server-side from the headline data.
    The client must NOT send any prompt text - only headlineId and style.
    """
    # Fail loudly (but safely) if the server is not configured for image generation.
    # Never log or return the key value.
    if not os.environ.get("GEMINI_API_KEY"):
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")

    # Validate style against allowlist
    style = request.style if request.style else "Default"
    if style not in ALLOWED_STYLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid style '{style}'. Allowed styles: {', '.join(ALLOWED_STYLES)}"
        )

    # Look up headline by ID (from DB or static fallback)
    headline_data = _lookup_headline_by_id(request.headlineId, db)
    
    # Build prompt server-side from headline data
    final_prompt = _build_prompt_template(
        headline=headline_data["headline"],
        summary=headline_data["summary"],
        style=style
    )

    print(f"Generating image for headlineId {request.headlineId} with style '{style}'")

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
        return {"imageUrl": image_url, "cacheHit": False}
    else:
        raise HTTPException(status_code=500, detail="Failed to generate image.")

@app.get("/")
def read_root():
    return {"status": "Backend is running"}


@app.get("/api/health")
def health_check():
    """
    Simple health check endpoint that doesn't require database connection.
    Returns {"ok": true} if the server is running.
    """
    return {"ok": True}


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


@app.post("/api/debug/pull-feeds")
def debug_pull_feeds():
    """
    Manual trigger endpoint for RSS feed ingestion (debug mode only).
    
    Only works when DEBUG_MODE=true. Returns 404 if DEBUG_MODE is not enabled.
    This endpoint does NOT require the cron secret - it's for local debugging only.
    
    Returns summary of ingestion run with diagnostic information.
    """
    if not DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Debug endpoint not available")
    
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
