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
from fastapi import FastAPI, HTTPException, Depends, Header, Request
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

# Feed ID -> display tag shown next to each headline (RSS source)
FEED_DISPLAY_TAGS = {
    "fox_us": "FOX",
    "nbc_top": "NBC",
    "nyt_home": "NYT",
    "npr_news": "NPR",
    "wsj_us": "WSJ",
}

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
    - Array of objects with: id, feedId (for logo mapping), headline, summary, sourceName, sourceUrl, 
      pregeneratedCaption, basePrompt, initialImageUrl, category (feed display tag: CNN Top, Fox US, etc.)
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
                    f.id as feed_id,
                    f.name as feed_name
                FROM items i
                JOIN feeds f ON i.feed_id = f.id
                WHERE i.fetched_at >= :today_start_utc 
                  AND i.fetched_at < :tomorrow_start_utc
                  AND i.feed_id != 'cnn_top'
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
                
                feed_id = row[6] or ""
                feed_name = row[7] or "Unknown Source"
                source_tag = FEED_DISPLAY_TAGS.get(feed_id, feed_name)
                # Always show "WSJ" and correct feedId for Wall Street Journal
                if feed_id == "wsj_us" or (feed_name and "Wall Street Journal" in feed_name):
                    source_tag = "WSJ"
                    feed_id = "wsj_us"

                news_item = {
                    "id": item_id,
                    "feedId": feed_id,
                    "headline": title,
                    "summary": summary or "",
                    "sourceName": feed_name,
                    "sourceUrl": row[3] or "",  # url
                    "pregeneratedCaption": caption,
                    "basePrompt": base_prompt,
                    "initialImageUrl": "",  # RSS items don't have pre-generated images (empty string for frontend compatibility)
                    "category": source_tag,  # feed display tag (CNN Top, Fox US, etc.)
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
        # Static fallback: use sourceName as display tag; no feedId (frontend uses default logo)
        for item in data:
            item["category"] = item.get("sourceName", "Unknown Source")
            item["feedId"] = None
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
                      AND i.feed_id != 'cnn_top'
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
            data_file_path = (Path(__file__).resolve().parent.parent / "data" / "news.json").resolve()
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
    
    The prompt is constructed entirely server-side from hard-coded instructions
    plus the headline/summary text. The client never sends prompt text.
    
    Args:
        headline: The headline title
        summary: The headline summary/description
        style: The style name (must be from ALLOWED_STYLES)
        
    Returns:
        Complete prompt string for image generation
    """
    base_template = (
        "TASK: Create a political cartoon illustration inspired by the following headline and summary. "
        "The cartoon should use humor, exaggeration, and symbolism to deliver a satirical take on the situation described.\n\n"
        f"HEADLINE: {headline}\n"
        f"SUMMARY: {summary}\n\n"
        "STYLE AND TONE:\n"
        "- Classic newspaper political cartoon style with bold ink outlines, a limited color palette "
        "(mainly black, white, gray, and 2-3 accent colors), and a hand-drawn editorial aesthetic.\n"
        "- Witty, clever, and slightly exaggerated — never cruel, offensive, or mean-spirited.\n"
        "- Maintain a consistent character design and drawing style, as if all cartoons come from the same cartoonist.\n"
        "- Include visible, legible labels or captions only if they enhance the satire "
        "(e.g. labeling symbols like 'Congress,' 'AI regulation,' or 'Public Opinion').\n\n"
        "CONTENT REQUIREMENTS:\n"
        "- Use visual metaphor (e.g. sinking ships, broken machines, tightropes, puppet strings) to represent abstract issues.\n"
        "- Focus on irony and contrast — show the difference between what's said and what's happening.\n"
        "- Represent political figures or institutions as symbolic caricatures only — never photorealistic. "
        "Keep depictions focused on ideas, policies, and institutions rather than personal attacks.\n"
        "- The scene should be self-contained and understandable on its own, but more meaningful with the headline.\n"
        "- Rely on visual storytelling — avoid text-heavy dialogue.\n\n"
        "SAFETY AND SENSITIVITY:\n"
        "- Never depict graphic violence, hate speech, or discriminatory content.\n"
        "- Always punch up — target power, hypocrisy, or absurdity, never vulnerable individuals or groups.\n"
        "- Avoid content that could be construed as personally attacking or defaming any real individual.\n"
        "- Keep the output suitable for a general audience and appropriate for a professional publication.\n"
        "- When depicting sensitive topics, use abstract symbolism rather than literal representation.\n\n"
        "OUTPUT FORMAT:\n"
        "- A single detailed cartoon illustration in 16:9 aspect ratio.\n"
        "- Center composition with a clear focal point.\n"
        "- Include enough detail and context to make the commentary clear.\n\n"
        "GOAL: Create a timeless, funny, and thought-provoking political cartoon that visually communicates "
        "the essence of the headline through satire, metaphor, and exaggeration — in the spirit of "
        "publications like The New Yorker, The Economist, or Politico."
    )

    # Style-specific modifiers appended to the base prompt
    style_modifiers = {
        "Default": "",  # Base template already defines the default style
        "Funnier": (
            "\n\nSTYLE MODIFIER: Push the humor further — use more exaggeration, absurd visual analogies, "
            "and comedic elements. Think brighter accent colors and a more playful, animated feel."
        ),
        "Drier": (
            "\n\nSTYLE MODIFIER: Use a more understated, dry wit approach — muted tones, subtle irony, "
            "and deadpan visual humor. Less is more."
        ),
        "More sarcastic": (
            "\n\nSTYLE MODIFIER: Lean into sharp irony and pointed visual metaphors. "
            "The sarcasm should be biting but still clever — never mean-spirited."
        ),
        "More wholesome": (
            "\n\nSTYLE MODIFIER: Take a lighter, more optimistic angle while keeping the satirical edge. "
            "Warmer tones, gentler humor, and a more hopeful perspective."
        ),
    }

    modifier = style_modifiers.get(style, "")

    return f"{base_template}{modifier}"


# --- Rate Limiting ---
# Maximum number of image generation requests per IP within the time window
RATE_LIMIT_MAX_REQUESTS = 10
RATE_LIMIT_WINDOW_MINUTES = 5


def _get_client_ip(request: Request) -> str:
    """
    Extract the client IP address from the request.
    
    On Vercel (behind a proxy), the real IP is in X-Forwarded-For.
    Falls back to request.client.host for local development.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
        # The first one is the original client IP
        return forwarded_for.split(",")[0].strip()
    
    # Fallback for local dev (no proxy)
    if request.client:
        return request.client.host
    
    return "unknown"


def _check_rate_limit(ip_address: str, endpoint: str, db: Session) -> dict:
    """
    Check if an IP has exceeded the rate limit for an endpoint.
    
    Counts requests within the last RATE_LIMIT_WINDOW_MINUTES minutes.
    If under the limit, records the new request and allows it.
    If over the limit, returns info about when the window resets.
    
    Args:
        ip_address: The client's IP address
        endpoint: The endpoint being rate-limited (e.g. "generate-image")
        db: Database session
        
    Returns:
        dict with keys:
            - allowed (bool): Whether the request is allowed
            - current_count (int): Number of requests in the current window
            - retry_after_seconds (int|None): Seconds until the oldest request expires (if blocked)
    """
    try:
        # Count requests in the current time window
        result = db.execute(
            text("""
                SELECT COUNT(*), MIN(requested_at) as oldest
                FROM rate_limits
                WHERE ip_address = :ip
                  AND endpoint = :endpoint
                  AND requested_at > now() - INTERVAL :window
            """),
            {
                "ip": ip_address,
                "endpoint": endpoint,
                "window": f"{RATE_LIMIT_WINDOW_MINUTES} minutes",
            }
        )
        row = result.fetchone()
        current_count = row[0] if row else 0
        oldest_request = row[1] if row else None
        
        if current_count >= RATE_LIMIT_MAX_REQUESTS:
            # Calculate how long until the oldest request falls outside the window
            retry_after = RATE_LIMIT_WINDOW_MINUTES * 60  # default to full window
            if oldest_request:
                from datetime import timezone as tz
                now_utc = datetime.now(tz.utc)
                # Ensure oldest_request is timezone-aware
                if oldest_request.tzinfo is None:
                    oldest_request = oldest_request.replace(tzinfo=tz.utc)
                window_end = oldest_request + timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)
                retry_after = max(1, int((window_end - now_utc).total_seconds()))
            
            return {
                "allowed": False,
                "current_count": current_count,
                "retry_after_seconds": retry_after,
            }
        
        # Under the limit — record this request
        db.execute(
            text("""
                INSERT INTO rate_limits (ip_address, endpoint, requested_at)
                VALUES (:ip, :endpoint, now())
            """),
            {"ip": ip_address, "endpoint": endpoint}
        )
        db.commit()
        
        return {
            "allowed": True,
            "current_count": current_count + 1,
            "retry_after_seconds": None,
        }
    
    except Exception as e:
        # If rate limiting fails (e.g. table doesn't exist yet), allow the request
        # rather than blocking all image generation
        print(f"Rate limit check failed (allowing request): {type(e).__name__}")
        return {
            "allowed": True,
            "current_count": 0,
            "retry_after_seconds": None,
        }


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
async def generate_image(request: ImageRequest, raw_request: Request, db: Session = Depends(get_db)):
    """
    Generates an image based on a headline ID and optional style.
    
    The prompt is constructed server-side from the headline data.
    The client must NOT send any prompt text - only headlineId and style.
    
    Rate limited to RATE_LIMIT_MAX_REQUESTS per RATE_LIMIT_WINDOW_MINUTES per IP.
    """
    # --- Rate limit check ---
    client_ip = _get_client_ip(raw_request)
    rate_check = _check_rate_limit(client_ip, "generate-image", db)
    
    if not rate_check["allowed"]:
        retry_after = rate_check["retry_after_seconds"]
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded. You can generate up to {RATE_LIMIT_MAX_REQUESTS} cartoons "
                f"every {RATE_LIMIT_WINDOW_MINUTES} minutes. "
                f"Please wait {retry_after} seconds and try again."
            ),
            headers={"Retry-After": str(retry_after)},
        )

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


def _verify_cron_secret(
    authorization: Optional[str] = None,
    x_cron_secret: Optional[str] = None
) -> None:
    """
    Verify CRON_SECRET from Authorization header or X-Cron-Secret header.
    
    Raises HTTPException if authentication fails.
    """
    import hmac
    
    # Get CRON_SECRET from environment
    cron_secret = os.environ.get("CRON_SECRET")
    
    if not cron_secret:
        raise HTTPException(status_code=500, detail={"error": "CRON_SECRET not configured"})
    
    # Extract secret from Authorization header if present (Bearer <secret>)
    provided_secret = None
    if authorization and authorization.startswith("Bearer "):
        provided_secret = authorization[7:].strip()
    elif x_cron_secret:
        provided_secret = x_cron_secret
    
    if not provided_secret:
        raise HTTPException(status_code=403, detail={"error": "Missing authentication header"})
    
    # Verify secret (constant-time comparison to prevent timing attacks)
    if not hmac.compare_digest(provided_secret, cron_secret):
        raise HTTPException(status_code=403, detail={"error": "Invalid CRON_SECRET"})


def _run_cron_pull_feeds() -> dict:
    """
    Execute RSS feed ingestion and return summary.
    Shared logic for both GET and POST handlers.
    """
    from datetime import timezone as tz
    
    start_time = datetime.now(tz.utc)
    print(f"CRON: Starting pull-feeds at {start_time.isoformat()}")
    
    try:
        summary = run_rss_ingest()
        
        end_time = datetime.now(tz.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        print(f"CRON: Completed pull-feeds in {duration_ms}ms - "
              f"status={summary.get('status')}, "
              f"items_inserted={summary.get('items_inserted')}, "
              f"feeds_succeeded={summary.get('feeds_succeeded')}, "
              f"feeds_failed={summary.get('feeds_failed')}")
        
        # Add timing info to response
        summary["duration_ms"] = duration_ms
        summary["completed_at"] = end_time.isoformat()
        
        return summary
    except Exception as e:
        # Sanitize error messages
        error_msg = str(e)
        if "DATABASE_URL" in error_msg or "password" in error_msg.lower() or "CRON_SECRET" in error_msg:
            error_msg = "Ingestion error"
        
        print(f"CRON: Failed pull-feeds with error: {error_msg}")
        raise HTTPException(status_code=500, detail={"error": error_msg})


@app.get("/api/cron/pull-feeds")
def cron_pull_feeds_get(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret")
):
    """
    GET handler for Vercel Cron - pulls RSS feeds into database.
    
    Vercel Cron sends GET requests by default. This endpoint handles the cron
    invocation with proper authentication via CRON_SECRET.
    
    Authentication accepts either:
    - Authorization: Bearer <CRON_SECRET> (Vercel Cron format)
    - X-Cron-Secret: <CRON_SECRET> (backward compatibility)
    
    Returns summary of ingestion run.
    """
    _verify_cron_secret(authorization, x_cron_secret)
    return _run_cron_pull_feeds()


@app.post("/api/cron/pull-feeds")
def cron_pull_feeds_post(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret")
):
    """
    POST handler for manual cron trigger - pulls RSS feeds into database.
    
    Kept for backward compatibility with manual curl/API calls that use POST.
    
    Authentication accepts either:
    - Authorization: Bearer <CRON_SECRET> (Vercel Cron format)
    - X-Cron-Secret: <CRON_SECRET> (backward compatibility)
    
    Returns summary of ingestion run.
    """
    _verify_cron_secret(authorization, x_cron_secret)
    return _run_cron_pull_feeds()
