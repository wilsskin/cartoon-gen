"""
RSS ingestion service for fetching and storing RSS feed items.

This service reads feed configuration from backend/data/feeds.json,
fetches RSS feeds, and stores items in the database.

Optimized for Vercel Hobby plan (10 second timeout) using parallel feed fetching.
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from uuid import uuid4

import feedparser
import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

# Add backend directory to path for imports
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from db import engine

# Parallel fetching configuration for Vercel Hobby plan (10s timeout)
MAX_WORKERS = 6  # Fetch all feeds concurrently
FETCH_TIMEOUT = 5  # Aggressive timeout per feed (seconds)
FETCH_RETRIES = 3  # Retries with backoff for 429/5xx/timeouts

# Browser-like headers to avoid bot blocking (e.g. WSJ/CDN throttling)
DEFAULT_RSS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
}

# When True, save raw XML to a temp file when a feed returns 200 but parse fails or 0 entries
DEBUG_RSS_DUMP = os.environ.get("DEBUG_RSS_DUMP", "false").lower() in ("true", "1", "yes")


def _log_feed_result(
    feed_name: str,
    url: str,
    status: Optional[int],
    bytes_count: int,
    parsed_count: int,
    kept_count: int,
    error_type: Optional[str] = None,
) -> None:
    """Structured log for each feed: feed_name, url, status, bytes, parsed_count, kept_count, error_type."""
    print(
        f"INGEST: feed_name={feed_name!r} url={url[:80]!r} status={status} bytes={bytes_count} "
        f"parsed_count={parsed_count} kept_count={kept_count} error_type={error_type!r}"
    )


def _dump_feed_xml(feed_id: str, content: bytes) -> Optional[str]:
    """If DEBUG_RSS_DUMP, save raw XML to a temp file and return path; else return None."""
    if not DEBUG_RSS_DUMP or not content:
        return None
    try:
        import tempfile
        fd, path = tempfile.mkstemp(prefix=f"rss_{feed_id}_", suffix=".xml")
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        return path
    except Exception as e:
        print(f"INGEST: DEBUG_RSS_DUMP write failed: {e}")
        return None


# Data retention configuration
ITEMS_RETENTION_DAYS = 7    # Keep news items for 7 days
RUNS_RETENTION_DAYS = 30    # Keep run logs for 30 days
ERRORS_RETENTION_DAYS = 30  # Keep error logs for 30 days


def load_feeds_config() -> Dict[str, Any]:
    """Load feeds configuration from backend/data/feeds.json.
    Uses Path(__file__).resolve() for serverless-safe absolute path resolution."""
    feeds_file = Path(__file__).resolve().parent.parent / "data" / "feeds.json"
    with open(feeds_file, "r") as f:
        return json.load(f)


def parse_published_date(entry: Any) -> Optional[datetime]:
    """Parse RSS published date from feedparser entry to datetime"""
    try:
        # feedparser provides published_parsed as time.struct_time
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            return datetime(*entry.published_parsed[:6])
        # Fallback to published string if available
        if hasattr(entry, 'published') and entry.published:
            # feedparser may have already parsed it
            if hasattr(entry.published, 'parsed'):
                return entry.published.parsed
    except Exception:
        pass
    return None


def upsert_feed(db: Session, feed_data: Dict) -> None:
    """Upsert feed row in feeds table"""
    db.execute(
        text("""
            INSERT INTO feeds (id, name, url, category_default, language, enabled)
            VALUES (:id, :name, :url, :category_default, :language, :enabled)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                url = EXCLUDED.url,
                category_default = EXCLUDED.category_default,
                language = EXCLUDED.language,
                enabled = EXCLUDED.enabled
        """),
        {
            "id": feed_data["id"],
            "name": feed_data["name"],
            "url": feed_data["url"],
            "category_default": feed_data.get("category"),
            "language": feed_data.get("language"),
            "enabled": feed_data.get("enabled", True),
        }
    )


def update_feed_metadata(db: Session, feed_id: str, etag: Optional[str], 
                         last_modified: Optional[str]) -> None:
    """Update feed metadata after successful fetch"""
    db.execute(
        text("""
            UPDATE feeds
            SET etag = :etag,
                last_modified = :last_modified,
                last_fetched_at = now()
            WHERE id = :feed_id
        """),
        {
            "feed_id": feed_id,
            "etag": etag,
            "last_modified": last_modified,
        }
    )


def get_feed_metadata(db: Session, feed_id: str) -> Dict[str, Optional[str]]:
    """Get existing feed metadata (etag, last_modified)"""
    result = db.execute(
        text("SELECT etag, last_modified FROM feeds WHERE id = :feed_id"),
        {"feed_id": feed_id}
    ).fetchone()
    
    if result:
        return {"etag": result[0], "last_modified": result[1]}
    return {"etag": None, "last_modified": None}


def insert_items(db: Session, feed_id: str, entries: List[Dict], max_items: int) -> int:
    """
    Insert RSS items into database.
    Returns count of items inserted or updated.
    
    Both new inserts and conflict updates set fetched_at = now(), so re-fetched
    items appear as "today" in /api/news. Duplicate headlines from different feeds
    are kept (different phrasing on same story).
    """
    inserted = 0
    updated = 0
    
    for entry in entries[:max_items]:
        # Extract entry data
        title = getattr(entry, 'title', '') or ''
        link = getattr(entry, 'link', '') or ''
        summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '') or None
        published = parse_published_date(entry)
        # Category no longer used; display tag is derived from feed_id in API
        if not title or not link:
            continue
        
        try:
            # Upsert: insert new rows, or update existing rows.
            # Update fetched_at on conflict so re-fetched items show as "today" in /api/news
            # Category column left NULL; display tag is derived from feed_id in API
            result = db.execute(
                text("""
                    INSERT INTO items (feed_id, title, summary, url, published_at, category)
                    VALUES (:feed_id, :title, :summary, :url, :published_at, NULL)
                    ON CONFLICT (feed_id, url) DO UPDATE SET
                        title = COALESCE(EXCLUDED.title, items.title),
                        summary = COALESCE(EXCLUDED.summary, items.summary),
                        published_at = COALESCE(EXCLUDED.published_at, items.published_at),
                        fetched_at = now()
                    RETURNING id, fetched_at
                """),
                {
                    "feed_id": feed_id,
                    "title": title,
                    "summary": summary,
                    "url": link,
                    "published_at": published,
                }
            )
            row = result.fetchone()
            if row:
                # Check if this was a new insert (fetched_at is recent) or an update (old fetched_at)
                fetched_at = row[1]
                if fetched_at:
                    # If fetched_at is within last minute, it's likely a new insert
                    from datetime import timedelta, timezone
                    now_utc = datetime.now(timezone.utc)
                    if fetched_at > now_utc - timedelta(minutes=1):
                        inserted += 1
                    else:
                        updated += 1
                else:
                    inserted += 1
        except Exception as e:
            # Log but continue
            print(f"Error inserting item for feed {feed_id}: {e}")
            continue
    
    if updated > 0:
        print(f"INGEST: Feed {feed_id}: {inserted} new items, {updated} existing items refreshed")
    else:
        print(f"INGEST: Feed {feed_id}: {inserted} items inserted")
    
    return inserted


def fetch_rss_feed(url: str, timeout: int, etag: Optional[str] = None,
                  last_modified: Optional[str] = None) -> requests.Response:
    """
    Fetch RSS feed with browser-like headers and optional retries.

    Uses User-Agent, Accept, Accept-Language to reduce bot blocking (e.g. WSJ).
    Retries with exponential backoff on 429, 5xx, and timeouts.
    """
    headers = dict(DEFAULT_RSS_HEADERS)
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    last_exception = None
    last_response = None
    for attempt in range(FETCH_RETRIES):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            last_response = response
            # Retry on rate limit or server errors
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < FETCH_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise requests.exceptions.HTTPError(
                    f"HTTP {response.status_code} after {FETCH_RETRIES} attempts",
                    response=response,
                )
            return response
        except requests.exceptions.Timeout as e:
            last_exception = e
            if attempt < FETCH_RETRIES - 1:
                time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            last_exception = e
            raise
    if last_exception:
        raise last_exception
    if last_response is not None:
        raise requests.exceptions.HTTPError(
            f"HTTP {last_response.status_code} after {FETCH_RETRIES} attempts",
            response=last_response,
        )
    raise RuntimeError("fetch_rss_feed: no response or exception")


def cleanup_old_data() -> Dict[str, int]:
    """
    Delete old data to prevent database bloat.
    
    Retention periods:
    - items: 7 days (news headlines)
    - runs: 30 days (cron execution logs)
    - feed_run_errors: 30 days (error logs)
    
    Returns dict with counts of deleted rows per table.
    """
    deleted = {"items": 0, "runs": 0, "feed_run_errors": 0, "rate_limits": 0}
    
    with engine.begin() as conn:
        # Delete old items (news headlines older than 7 days)
        result = conn.execute(
            text("""
                DELETE FROM items
                WHERE fetched_at < now() - INTERVAL :days
                RETURNING id
            """),
            {"days": f"{ITEMS_RETENTION_DAYS} days"}
        )
        deleted["items"] = result.rowcount
        
        # Delete old feed_run_errors first (foreign key to runs)
        result = conn.execute(
            text("""
                DELETE FROM feed_run_errors
                WHERE created_at < now() - INTERVAL :days
                RETURNING id
            """),
            {"days": f"{ERRORS_RETENTION_DAYS} days"}
        )
        deleted["feed_run_errors"] = result.rowcount
        
        # Delete old runs (cron execution logs older than 30 days)
        result = conn.execute(
            text("""
                DELETE FROM runs
                WHERE started_at < now() - INTERVAL :days
                RETURNING id
            """),
            {"days": f"{RUNS_RETENTION_DAYS} days"}
        )
        deleted["runs"] = result.rowcount
        
        # Delete old rate limit entries (older than 1 hour — only 5 min needed, but
        # keep 1 hour for debugging visibility)
        try:
            result = conn.execute(
                text("""
                    DELETE FROM rate_limits
                    WHERE requested_at < now() - INTERVAL '1 hour'
                    RETURNING id
                """)
            )
            deleted["rate_limits"] = result.rowcount
        except Exception:
            # Table may not exist yet — don't fail cleanup
            pass
    
    total = sum(deleted.values())
    if total > 0:
        print(f"CLEANUP: Deleted {deleted['items']} items, {deleted['runs']} runs, "
              f"{deleted['feed_run_errors']} errors, {deleted['rate_limits']} rate_limit entries "
              f"(retention: items={ITEMS_RETENTION_DAYS}d, runs/errors={RUNS_RETENTION_DAYS}d)")
    else:
        print("CLEANUP: No old data to delete")
    
    return deleted


def fetch_feed_parallel(feed_data: Dict, metadata: Dict[str, Optional[str]], 
                        timeout: int) -> Tuple[str, Optional[requests.Response], Optional[str]]:
    """
    Fetch a single RSS feed (designed for parallel execution).
    
    Returns tuple of (feed_id, response, error_message).
    Response is None if error occurred.
    """
    feed_id = feed_data["id"]
    feed_url = feed_data["url"]
    
    try:
        response = fetch_rss_feed(
            feed_url,
            timeout,
            etag=metadata.get("etag"),
            last_modified=metadata.get("last_modified")
        )
        return (feed_id, response, None)
    except requests.exceptions.Timeout:
        return (feed_id, None, "Request timeout")
    except requests.exceptions.RequestException as e:
        return (feed_id, None, str(e))


def process_feed(db: Session, feed_data: Dict, defaults: Dict, run_id: str) -> Dict[str, Any]:
    """
    Process a single feed: fetch, parse, and store items.
    Returns dict with inserted count and error info if any.
    """
    feed_id = feed_data["id"]
    feed_url = feed_data["url"]
    timeout = defaults.get("timeoutSeconds", 10)
    max_items = defaults.get("maxItemsPerFeed", 3)
    
    result = {
        "feed_id": feed_id,
        "inserted": 0,
        "error": None,
        "error_type": None,
        "http_status": None,
    }
    
    try:
        # Upsert feed row
        upsert_feed(db, feed_data)
        
        # Get existing metadata for conditional request
        metadata = get_feed_metadata(db, feed_id)
        
        # Fetch RSS feed
        response = fetch_rss_feed(
            feed_url,
            timeout,
            etag=metadata["etag"],
            last_modified=metadata["last_modified"]
        )
        
        result["http_status"] = response.status_code
        
        # Handle HTTP 304 Not Modified
        if response.status_code == 304:
            # Update last_fetched_at but skip parsing
            update_feed_metadata(db, feed_id, metadata["etag"], metadata["last_modified"])
            db.commit()
            return result
        
        # Handle HTTP 200 OK
        if response.status_code == 200:
            # Parse RSS
            feed = feedparser.parse(response.content)
            
            # Check for parse errors
            if feed.bozo and feed.bozo_exception:
                raise Exception(f"RSS parse error: {feed.bozo_exception}")
            
            # Extract etag and last-modified from response headers
            etag = response.headers.get('ETag')
            last_modified = response.headers.get('Last-Modified')
            
            # Insert items
            inserted = insert_items(db, feed_id, feed.entries, max_items)
            result["inserted"] = inserted
            
            # Get current timestamp for logging
            from datetime import timezone
            current_timestamp = datetime.now(timezone.utc)
            print(f"INGEST: Feed {feed_id} processed: {inserted} items, fetched_at will be ~{current_timestamp.isoformat()}")
            
            # Update feed metadata
            update_feed_metadata(db, feed_id, etag, last_modified)
            db.commit()
            return result
        
        # Handle other HTTP status codes
        raise Exception(f"HTTP {response.status_code}: {response.reason}")
    
    except requests.exceptions.Timeout:
        result["error"] = "Request timeout"
        result["error_type"] = "timeout"
    except requests.exceptions.RequestException as e:
        result["error"] = str(e)
        result["error_type"] = "http_error"
    except Exception as e:
        result["error"] = str(e)
        result["error_type"] = "parse_error"
    
    return result


def run_rss_ingest() -> Dict[str, Any]:
    """
    Main RSS ingestion function with parallel feed fetching.
    
    Optimized for Vercel Hobby plan (10 second timeout):
    - Phase 1: Prepare feeds and collect metadata (fast, sequential)
    - Phase 2: Fetch all RSS feeds in parallel (slow network I/O, parallelized)
    - Phase 3: Process results and insert items (fast, sequential)
    
    Returns summary dict with run_id, status, items_inserted, feeds_failed.
    """
    from datetime import timezone as tz
    start_time = datetime.now(tz.utc)
    
    config = load_feeds_config()
    defaults = config.get("defaults", {})
    feeds = config.get("feeds", [])
    
    # Use aggressive timeout for Hobby plan, but allow config override
    timeout = min(defaults.get("timeoutSeconds", FETCH_TIMEOUT), FETCH_TIMEOUT)
    max_items = defaults.get("maxItemsPerFeed", 3)
    
    # Filter enabled feeds
    enabled_feeds = [f for f in feeds if f.get("enabled", defaults.get("enabled", True))]
    total_feeds = len(enabled_feeds)
    config_feed_ids = {f["id"] for f in feeds}

    # Remove feeds (and their items) no longer in config (e.g. CNN removed)
    with engine.begin() as conn:
        existing = conn.execute(text("SELECT id FROM feeds")).fetchall()
        for (feed_id,) in existing:
            if feed_id not in config_feed_ids:
                conn.execute(text("DELETE FROM items WHERE feed_id = :id"), {"id": feed_id})
                conn.execute(text("DELETE FROM feeds WHERE id = :id"), {"id": feed_id})
                print(f"INGEST: Removed feed {feed_id} (no longer in config)")

    # Start run record
    run_id = str(uuid4())
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO runs (id, started_at, status, total_feeds)
                VALUES (:id, now(), 'running', :total_feeds)
            """),
            {"id": run_id, "total_feeds": total_feeds}
        )
    
    print(f"INGEST: Starting parallel ingestion run {run_id}: {total_feeds} feeds, timeout={timeout}s")
    
    # ========== PHASE 1: Prepare feeds and collect metadata ==========
    feed_metadata = {}
    with Session(engine) as db:
        for feed_data in enabled_feeds:
            upsert_feed(db, feed_data)
            feed_metadata[feed_data["id"]] = get_feed_metadata(db, feed_data["id"])
        db.commit()
    
    phase1_time = datetime.now(tz.utc)
    print(f"INGEST: Phase 1 (prepare) completed in {int((phase1_time - start_time).total_seconds() * 1000)}ms")
    
    # ========== PHASE 2: Fetch all feeds in parallel ==========
    fetch_results = {}  # feed_id -> (response, error)
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all fetch tasks
        future_to_feed = {
            executor.submit(
                fetch_feed_parallel,
                feed_data,
                feed_metadata.get(feed_data["id"], {}),
                timeout
            ): feed_data["id"]
            for feed_data in enabled_feeds
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_feed):
            feed_id, response, error = future.result()
            fetch_results[feed_id] = (response, error)
    
    phase2_time = datetime.now(tz.utc)
    print(f"INGEST: Phase 2 (parallel fetch) completed in {int((phase2_time - phase1_time).total_seconds() * 1000)}ms")
    
    # ========== PHASE 3: Process results and insert items ==========
    feeds_succeeded = 0
    feeds_failed = 0
    items_inserted = 0
    
    with Session(engine) as db:
        for feed_data in enabled_feeds:
            feed_id = feed_data["id"]
            response, error = fetch_results.get(feed_id, (None, "No fetch result"))
            metadata = feed_metadata.get(feed_id, {})
            
            result = {
                "feed_id": feed_id,
                "inserted": 0,
                "error": error,
                "error_type": "http_error" if error else None,
                "http_status": response.status_code if response else None,
            }
            
            feed_name = feed_data.get("name", feed_id)
            feed_url = feed_data.get("url", "")

            if error:
                # Fetch failed
                feeds_failed += 1
                _log_feed_result(
                    feed_name, feed_url, status=None, bytes_count=0,
                    parsed_count=0, kept_count=0, error_type="http_error",
                )
                print(f"INGEST: Feed {feed_id} failed: {error}")
                db.execute(
                    text("""
                        INSERT INTO feed_run_errors 
                        (run_id, feed_id, error_type, error_message, http_status)
                        VALUES (:run_id, :feed_id, :error_type, :error_message, :http_status)
                    """),
                    {
                        "run_id": run_id,
                        "feed_id": feed_id,
                        "error_type": "http_error",
                        "error_message": error,
                        "http_status": None,
                    }
                )
            elif response.status_code == 304:
                # Not modified - update last_fetched_at only
                feeds_succeeded += 1
                update_feed_metadata(db, feed_id, metadata.get("etag"), metadata.get("last_modified"))
                _log_feed_result(
                    feed_name, feed_url, status=304, bytes_count=0,
                    parsed_count=0, kept_count=0, error_type=None,
                )
                print(f"INGEST: Feed {feed_id} not modified (304), skipped")
            elif response.status_code == 200:
                # Success - parse and insert
                body_len = len(response.content) if response.content else 0
                try:
                    feed = feedparser.parse(response.content)
                    parsed_count = len(feed.entries) if feed.entries else 0

                    if feed.bozo and feed.bozo_exception:
                        raise Exception(f"RSS parse error: {feed.bozo_exception}")

                    # Extract headers
                    etag = response.headers.get('ETag')
                    last_modified = response.headers.get('Last-Modified')

                    # Insert items
                    inserted = insert_items(db, feed_id, feed.entries, max_items)
                    result["inserted"] = inserted
                    items_inserted += inserted
                    feeds_succeeded += 1

                    # Debug dump if we got 200 but 0 entries (helps diagnose parser/env issues)
                    if parsed_count == 0 and response.content:
                        dump_path = _dump_feed_xml(feed_id, response.content)
                        if dump_path:
                            print(f"INGEST: DEBUG_RSS_DUMP saved 0-entry feed XML to {dump_path}")

                    _log_feed_result(
                        feed_name, feed_url, status=200, bytes_count=body_len,
                        parsed_count=parsed_count, kept_count=inserted, error_type=None,
                    )
                    update_feed_metadata(db, feed_id, etag, last_modified)
                    print(f"INGEST: Feed {feed_id} processed: {inserted} items")

                except Exception as e:
                    feeds_failed += 1
                    error_msg = str(e)
                    dump_path = _dump_feed_xml(feed_id, response.content if response else b"")
                    if dump_path:
                        print(f"INGEST: DEBUG_RSS_DUMP saved parse-failure XML to {dump_path}")
                    _log_feed_result(
                        feed_name, feed_url, status=200, bytes_count=body_len,
                        parsed_count=0, kept_count=0, error_type="parse_error",
                    )
                    print(f"INGEST: Feed {feed_id} parse error: {error_msg}")
                    db.execute(
                        text("""
                            INSERT INTO feed_run_errors 
                            (run_id, feed_id, error_type, error_message, http_status)
                            VALUES (:run_id, :feed_id, :error_type, :error_message, :http_status)
                        """),
                        {
                            "run_id": run_id,
                            "feed_id": feed_id,
                            "error_type": "parse_error",
                            "error_message": error_msg,
                            "http_status": 200,
                        }
                    )
            else:
                # Unexpected HTTP status
                feeds_failed += 1
                body_len = len(response.content) if response.content else 0
                _log_feed_result(
                    feed_name, feed_url, status=response.status_code, bytes_count=body_len,
                    parsed_count=0, kept_count=0, error_type="http_error",
                )
                error_msg = f"HTTP {response.status_code}: {response.reason}"
                print(f"INGEST: Feed {feed_id} failed: {error_msg}")
                db.execute(
                    text("""
                        INSERT INTO feed_run_errors 
                        (run_id, feed_id, error_type, error_message, http_status)
                        VALUES (:run_id, :feed_id, :error_type, :error_message, :http_status)
                    """),
                    {
                        "run_id": run_id,
                        "feed_id": feed_id,
                        "error_type": "http_error",
                        "error_message": error_msg,
                        "http_status": response.status_code,
                    }
                )
        
        db.commit()
    
    end_time = datetime.now(tz.utc)
    total_ms = int((end_time - start_time).total_seconds() * 1000)
    
    print(f"INGEST: Run {run_id} completed in {total_ms}ms: "
          f"{feeds_succeeded} succeeded, {feeds_failed} failed, {items_inserted} items inserted")
    
    # Determine final status
    status = "success" if feeds_failed == 0 else "partial"
    
    # Finish run record
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE runs
                SET finished_at = now(),
                    status = :status,
                    feeds_succeeded = :feeds_succeeded,
                    feeds_failed = :feeds_failed,
                    items_inserted = :items_inserted
                WHERE id = :run_id
            """),
            {
                "run_id": run_id,
                "status": status,
                "feeds_succeeded": feeds_succeeded,
                "feeds_failed": feeds_failed,
                "items_inserted": items_inserted,
            }
        )
    
    # ========== PHASE 4: Cleanup old data ==========
    try:
        cleanup_result = cleanup_old_data()
        items_deleted = cleanup_result.get("items", 0)
    except Exception as e:
        # Don't fail the whole run if cleanup fails
        print(f"CLEANUP: Warning - cleanup failed: {e}")
        items_deleted = 0
    
    cleanup_time = datetime.now(tz.utc)
    total_ms = int((cleanup_time - start_time).total_seconds() * 1000)
    print(f"INGEST: Total run completed in {total_ms}ms (including cleanup)")
    
    return {
        "run_id": run_id,
        "status": status,
        "items_inserted": items_inserted,
        "items_deleted": items_deleted,
        "feeds_failed": feeds_failed,
        "feeds_succeeded": feeds_succeeded,
        "total_feeds": total_feeds,
        "duration_ms": total_ms,
    }
