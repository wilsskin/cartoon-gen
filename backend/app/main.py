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

import asyncio
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.responses import JSONResponse
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
from db import get_db, SessionLocal
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
PROMPT_MAX_LENGTH = 2000


class ImageRequest(BaseModel):
    """Accepts either prompt (direct) or headlineId (server builds prompt)."""
    prompt: Optional[str] = None
    headlineId: Optional[str] = None
    regenerate: bool = False
    basePrompt: Optional[str] = None  # ignored; backward compat

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

# UUID pattern for validation (standard UUID format)
UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)


def _is_valid_uuid(uuid_string: str) -> bool:
    """Check if a string is a valid UUID format"""
    return bool(UUID_PATTERN.match(uuid_string))


def _get_latest_fetch_date_range(db: Session) -> Optional[Tuple[datetime, datetime]]:
    """
    Get the date range (in UTC) for the most recent Pacific Time date that has at least one item.

    Used so we show the latest batch of headlines (e.g. yesterday before cron runs, today after).
    Returns None if there are no items in the database.
    """
    result = db.execute(
        text("""
            SELECT (MAX(i.fetched_at) AT TIME ZONE :tz)::date AS display_date
            FROM items i
            WHERE i.feed_id != 'cnn_top'
        """),
        {"tz": APP_TIMEZONE},
    )
    row = result.fetchone()
    if not row or row[0] is None:
        return None
    display_date = row[0]
    pt_tz = ZoneInfo(APP_TIMEZONE)
    day_start_pt = datetime.combine(display_date, datetime.min.time(), tzinfo=pt_tz)
    day_end_pt = day_start_pt + timedelta(days=1)
    day_start_utc = day_start_pt.astimezone(timezone.utc)
    day_end_utc = day_end_pt.astimezone(timezone.utc)
    if DEBUG_TIME_WINDOWS:
        print(
            f"LATEST FETCH DATE PT: {display_date} -> UTC window {day_start_utc.isoformat()} to {day_end_utc.isoformat()}"
        )
    return day_start_utc, day_end_utc


@app.get("/api/news")
def get_news(db: Session = Depends(get_db)):
    """
    Returns the most recent batch of RSS items from the database (one calendar day in Pacific Time).

    Uses the latest fetch date that has data: e.g. yesterday's headlines before the daily cron runs,
    today's after it runs. Never mixes days. Returns [] if there are no items.
    """
    try:
        date_range = _get_latest_fetch_date_range(db)
        if date_range is None:
            return []

        day_start_utc, day_end_utc = date_range

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
                WHERE i.fetched_at >= :day_start_utc
                  AND i.fetched_at < :day_end_utc
                  AND i.feed_id != 'cnn_top'
                ORDER BY i.published_at DESC NULLS LAST, i.fetched_at DESC
                LIMIT :limit
            """),
            {
                "limit": MAX_NEWS_ITEMS,
                "day_start_utc": day_start_utc,
                "day_end_utc": day_end_utc,
            }
        )

        rows = result.fetchall()

        news_items = []
        for row in rows:
            item_id = str(row[0])
            title = row[1] or ""
            summary = row[2] or ""
            base_prompt = f"{title}. {summary[:100]}" if summary else title
            caption = title[:80] + "..." if len(title) > 80 else title
            feed_id = row[6] or ""
            feed_name = row[7] or "Unknown Source"
            source_tag = FEED_DISPLAY_TAGS.get(feed_id, feed_name)
            if feed_id == "wsj_us" or (feed_name and "Wall Street Journal" in feed_name):
                source_tag = "WSJ"
                feed_id = "wsj_us"
            news_items.append({
                "id": item_id,
                "feedId": feed_id,
                "headline": title,
                "summary": summary or "",
                "sourceName": feed_name,
                "sourceUrl": row[3] or "",
                "pregeneratedCaption": caption,
                "basePrompt": base_prompt,
                "initialImageUrl": "",
                "category": source_tag,
            })
        return news_items

    except Exception as e:
        error_msg = str(e)
        if "DATABASE_URL" in error_msg or "password" in error_msg.lower():
            error_msg = "Database query error"
        print(f"Error fetching news from database: {error_msg}")
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

    No date filter: the news list is already restricted to the most recent batch by
    the endpoint that serves headlines. Image generation just uses whatever headline
    the user clicked (by ID). For DB items we match UUID and exclude cnn_top; for
    static fallback we use numeric id from news.json when ALLOW_STATIC_NEWS_FALLBACK is True.
    """
    is_uuid = _is_valid_uuid(headline_id)

    if is_uuid:
        try:
            # LEFT JOIN so we still find the item if the feed row is missing (e.g. feed deleted)
            result = db.execute(
                text("""
                    SELECT i.id, i.title, i.summary, i.url, i.published_at, i.fetched_at, i.category, f.name as feed_name
                    FROM items i
                    LEFT JOIN feeds f ON i.feed_id = f.id
                    WHERE i.id::text = :headline_id AND (i.feed_id IS NULL OR i.feed_id != 'cnn_top')
                """),
                {"headline_id": headline_id},
            )
            row = result.fetchone()
            if row:
                return {
                    "headline": row[1] or "",
                    "summary": row[2] or "",
                    "id": str(row[0]),
                }
            print(f"headline lookup: id={headline_id} not found in items (or feed is cnn_top)")
        except Exception as e:
            print(f"Database lookup error for UUID {headline_id}: {type(e).__name__}")

    # Static fallback (only if numeric ID and flag is enabled)
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


def _build_prompt_template(headline: str, summary: str) -> str:
    """
    Build a server-side prompt template for image generation.

    The prompt is constructed entirely server-side from hard-coded instructions
    plus the headline/summary text. The client never sends prompt text.

    Args:
        headline: The headline title
        summary: The headline summary/description

    Returns:
        Complete prompt string for image generation
    """
    return (
    f"Create a political cartoon about this headline:\n"
    f'"{headline}"\n\n'
    f"Context: {summary}\n\n"
    
    "TASK & CONSTRAINTS:\n"
    "- Square format (1:1 aspect ratio), solid white background.\n"
    "- Maximum 2-3 visual elements total.\n"
    "- New Yorker editorial cartoon style: confident ink lines, limited color palette "
    "(black/white/gray + 1-2 accent colors max).\n"
    "- Use satire to critique power, systems, or institutions — avoid personal attacks.\n\n"
    
    "STYLE & APPROACH:\n"
    "- The cartoon must work as a visual joke, pun, or ironic juxtaposition — NOT a literal illustration of the headline.\n"
    "- If depicting a real person: exaggerate distinctive features (hair, expression, posture) for instant recognition.\n"
    "- Use a single strong visual metaphor that creates an 'aha' moment.\n"
    "- Do NOT create infographics, diagrams, or explanatory illustrations.\n\n"
    
    "TEXT RULES:\n"
    "- Use text ONLY for: speech bubbles, signs held by characters, or essential 1-2 word labels.\n"
    "- Never use text to explain the joke or add multiple labels.\n"
    "- When in doubt, use less text."
)


# --- Rate Limiting ---
# Maximum number of image generation requests per IP within the time window
RATE_LIMIT_MAX_REQUESTS = 10
RATE_LIMIT_WINDOW_MINUTES = 5

# --- Per-process throttle (avoid rapid-fire during dev) ---
# At most 1 image generation request per second per process (in-memory).
_last_image_request_time: float = 0
IMAGE_THROTTLE_MIN_INTERVAL = 1.0


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


@app.get("/api/debug/news-ids")
def debug_news_ids(db: Session = Depends(get_db)):
    """
    Debug: list item IDs in the DB (no date filter). Use to verify which IDs exist
    when headline lookup returns 404. Compare these to the id you're sending.
    """
    try:
        result = db.execute(
            text("""
                SELECT i.id::text
                FROM items i
                WHERE i.feed_id != 'cnn_top'
                ORDER BY i.fetched_at DESC NULLS LAST
                LIMIT 50
            """)
        )
        ids = [row[0] for row in result.fetchall()]
        return {"count": len(ids), "ids": ids}
    except Exception as e:
        return {"count": 0, "ids": [], "error": str(e)}


@app.get("/api/debug/headline/{headline_id}")
def debug_headline_lookup(headline_id: str, db: Session = Depends(get_db)):
    """
    Debug: run the same lookup as generate-image for one ID. Shows whether the row
    exists, its feed_id, and whether the full lookup (with JOIN) finds it.
    """
    out = {"headline_id": headline_id, "in_items": None, "lookup_found": None, "lookup_row": None}
    try:
        # 1) Does the row exist in items at all?
        row = db.execute(
            text("SELECT id::text, feed_id, title FROM items WHERE id::text = :hid"),
            {"hid": headline_id},
        ).fetchone()
        if row:
            out["in_items"] = True
            out["feed_id"] = row[1]
            out["title_preview"] = (row[2] or "")[:60]
        else:
            out["in_items"] = False
            return out
        # 2) Exact same query as _lookup_headline_by_id (LEFT JOIN)
        lookup = db.execute(
            text("""
                SELECT i.id::text, i.title, i.summary
                FROM items i
                LEFT JOIN feeds f ON i.feed_id = f.id
                WHERE i.id::text = :headline_id AND (i.feed_id IS NULL OR i.feed_id != 'cnn_top')
            """),
            {"headline_id": headline_id},
        ).fetchone()
        if lookup:
            out["lookup_found"] = True
            out["lookup_row"] = {"id": lookup[0], "title_preview": (lookup[1] or "")[:60]}
        else:
            out["lookup_found"] = False
        return out
    except Exception as e:
        out["error"] = str(e)
        return out


def _apply_throttle() -> None:
    """In-memory throttle: at most 1 request per IMAGE_THROTTLE_MIN_INTERVAL seconds."""
    global _last_image_request_time
    now = time.monotonic()
    elapsed = now - _last_image_request_time
    if elapsed < IMAGE_THROTTLE_MIN_INTERVAL:
        wait = IMAGE_THROTTLE_MIN_INTERVAL - elapsed
        time.sleep(wait)
    _last_image_request_time = time.monotonic()


@app.post("/api/generate-image")
async def generate_image(request: ImageRequest, raw_request: Request, db: Session = Depends(get_db)):
    """
    Generates an image using Gemini native image model.

    Accepts either:
    - prompt: string (non-empty, max 2000 chars) — used directly (wrapped in template)
    - headlineId — prompt built server-side from headline

    Rate limited per IP and per-process throttled (1 req/sec).
    Returns { ok, imageBase64?, mimeType?, model?, requestId? } or { ok: false, error: { ... } }.
    """
    # --- Rate limit check ---
    client_ip = _get_client_ip(raw_request)
    rate_check = _check_rate_limit(client_ip, "generate-image", db)
    if not rate_check["allowed"]:
        retry_after = rate_check["retry_after_seconds"]
        return JSONResponse(
            status_code=429,
            content={
                "ok": False,
                "error": {
                    "code": "RATE_LIMIT",
                    "message": (
                        f"Rate limit exceeded. You can generate up to {RATE_LIMIT_MAX_REQUESTS} cartoons "
                        f"every {RATE_LIMIT_WINDOW_MINUTES} minutes. "
                        f"Please wait {retry_after} seconds and try again."
                    ),
                    "status": 429,
                    "details": None,
                    "model": services.GEMINI_IMAGE_MODEL,
                    "requestId": None,
                },
            },
            headers={"Retry-After": str(retry_after)},
        )

    # Fail fast if API key missing (never log or return the key)
    if not os.environ.get("GEMINI_API_KEY"):
        return {
            "ok": False,
            "error": {
                "code": "MISSING_API_KEY",
                "message": "GEMINI_API_KEY is not configured. Set it in Vercel Project Settings → Environment Variables or in backend/.env for local dev.",
                "status": 500,
                "details": None,
                "model": services.GEMINI_IMAGE_MODEL,
                "requestId": None,
            },
        }

    # Resolve final prompt: either from request.prompt or from headlineId
    if request.prompt is not None and request.prompt.strip():
        prompt_text = request.prompt.strip()
        if len(prompt_text) > PROMPT_MAX_LENGTH:
            return {
                "ok": False,
                "error": {
                    "code": "PROMPT_TOO_LONG",
                    "message": f"Prompt must be at most {PROMPT_MAX_LENGTH} characters.",
                    "status": 400,
                    "details": None,
                    "model": services.GEMINI_IMAGE_MODEL,
                    "requestId": None,
                },
            }
        final_prompt = _build_prompt_template(headline=prompt_text, summary="")
        log_context = "prompt"
    else:
        if not request.headlineId or not request.headlineId.strip():
            return {
                "ok": False,
                "error": {
                    "code": "MISSING_INPUT",
                    "message": "Provide either 'prompt' or 'headlineId'.",
                    "status": 400,
                    "details": None,
                    "model": services.GEMINI_IMAGE_MODEL,
                    "requestId": None,
                },
            }
        headline_id = request.headlineId.strip()
        # Use a fresh DB session for lookup so rate-limit session state doesn't affect the query
        lookup_db = SessionLocal()
        try:
            headline_data = _lookup_headline_by_id(headline_id, lookup_db)
        except HTTPException as e:
            return {
                "ok": False,
                "error": {
                    "code": "HEADLINE_NOT_FOUND",
                    "message": e.detail if isinstance(e.detail, str) else "Headline not found.",
                    "status": e.status_code,
                    "details": None,
                    "model": services.GEMINI_IMAGE_MODEL,
                    "requestId": None,
                },
            }
        finally:
            lookup_db.close()
        final_prompt = _build_prompt_template(
            headline=headline_data["headline"],
            summary=headline_data["summary"],
        )
        log_context = f"headlineId={request.headlineId}"

    # Per-process throttle (blocking wait)
    _apply_throttle()

    start = time.perf_counter()
    result = services.generate_satire_image(final_prompt)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    request_id = result.get("request_id") if result.get("ok") else result.get("error", {}).get("request_id")

    # Log model, timing, status, requestId — never the API key
    print(f"generate-image model={services.GEMINI_IMAGE_MODEL} status={'ok' if result.get('ok') else 'error'} elapsed_ms={elapsed_ms} requestId={request_id} context={log_context}")

    if result.get("ok"):
        return {
            "ok": True,
            "imageBase64": result["image_base64"],
            "mimeType": result["mime_type"],
            "model": result["model"],
            "requestId": result.get("request_id"),
        }
    err = result.get("error", {})
    return {
        "ok": False,
        "error": {
            "code": err.get("code", "UNKNOWN"),
            "message": err.get("message", "Image generation failed."),
            "status": err.get("status"),
            "details": err.get("details"),
            "model": err.get("model", services.GEMINI_IMAGE_MODEL),
            "requestId": err.get("request_id"),
        },
    }

@app.get("/")
def read_root():
    return {"status": "Backend is running"}


@app.get("/api/health")
def health_check():
    """
    Health check: ok, whether Gemini API key is set (not the value), and image model name.
    """
    return {
        "ok": True,
        "hasApiKey": bool(os.environ.get("GEMINI_API_KEY")),
        "model": services.GEMINI_IMAGE_MODEL,
    }


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

    Only works when DEBUG_MODE=true. Returns 404 otherwise.

    Returns summary of ingestion run.
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
