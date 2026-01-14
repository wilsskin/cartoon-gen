"""
RSS ingestion service for fetching and storing RSS feed items.

This service reads feed configuration from backend/data/feeds.json,
fetches RSS feeds, and stores items in the database.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import uuid4

from dotenv import load_dotenv
import feedparser
import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

# Add backend directory to path for imports
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Load environment variables from backend/.env
env_path = backend_path / ".env"
load_dotenv(dotenv_path=env_path, override=False)

from db import engine


def load_feeds_config() -> Dict[str, Any]:
    """Load feeds configuration from backend/data/feeds.json"""
    feeds_file = backend_path / "data" / "feeds.json"
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


def extract_category(entry: Dict, feed_category_default: Optional[str]) -> Optional[str]:
    """
    Extract category from RSS entry.
    Prefers entry tags/category, falls back to feed category_default.
    """
    # Check for tags/categories in entry
    if hasattr(entry, 'tags') and entry.tags:
        # Get first tag value
        tag = entry.tags[0]
        if hasattr(tag, 'term'):
            return tag.term
        elif isinstance(tag, dict) and 'term' in tag:
            return tag['term']
    
    # Check for category field
    if hasattr(entry, 'category'):
        if isinstance(entry.category, str):
            return entry.category
        elif isinstance(entry.category, list) and entry.category:
            return entry.category[0]
    
    # Fall back to feed default
    return feed_category_default


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


def insert_items(db: Session, feed_id: str, entries: List[Dict], 
                category_default: Optional[str], max_items: int) -> int:
    """
    Insert RSS items into database.
    Returns count of items inserted (excluding duplicates).
    """
    inserted = 0
    
    for entry in entries[:max_items]:
        # Extract entry data
        title = getattr(entry, 'title', '') or ''
        link = getattr(entry, 'link', '') or ''
        summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '') or None
        published = parse_published_date(entry)
        category = extract_category(entry, category_default)
        
        if not title or not link:
            continue
        
        try:
            # Insert with ON CONFLICT DO NOTHING (unique constraint on feed_id, url)
            result = db.execute(
                text("""
                    INSERT INTO items (feed_id, title, summary, url, published_at, category)
                    VALUES (:feed_id, :title, :summary, :url, :published_at, :category)
                    ON CONFLICT (feed_id, url) DO NOTHING
                    RETURNING id
                """),
                {
                    "feed_id": feed_id,
                    "title": title,
                    "summary": summary,
                    "url": link,
                    "published_at": published,
                    "category": category,
                }
            )
            if result.fetchone():
                inserted += 1
        except Exception as e:
            # Log but continue
            print(f"Error inserting item for feed {feed_id}: {e}")
            continue
    
    return inserted


def fetch_rss_feed(url: str, timeout: int, etag: Optional[str] = None, 
                  last_modified: Optional[str] = None) -> requests.Response:
    """Fetch RSS feed with conditional headers"""
    headers = {}
    if etag:
        headers['If-None-Match'] = etag
    if last_modified:
        headers['If-Modified-Since'] = last_modified
    
    response = requests.get(url, headers=headers, timeout=timeout)
    return response


def process_feed(db: Session, feed_data: Dict, defaults: Dict, run_id: str) -> Dict[str, Any]:
    """
    Process a single feed: fetch, parse, and store items.
    Returns dict with inserted count and error info if any.
    """
    feed_id = feed_data["id"]
    feed_url = feed_data["url"]
    category_default = feed_data.get("category")
    timeout = defaults.get("timeoutSeconds", 10)
    max_items = defaults.get("maxItemsPerFeed", 5)
    
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
            inserted = insert_items(db, feed_id, feed.entries, category_default, max_items)
            result["inserted"] = inserted
            
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
    Main RSS ingestion function.
    Returns summary dict with run_id, status, items_inserted, feeds_failed.
    """
    config = load_feeds_config()
    defaults = config.get("defaults", {})
    feeds = config.get("feeds", [])
    
    # Filter enabled feeds
    enabled_feeds = [f for f in feeds if f.get("enabled", defaults.get("enabled", True))]
    total_feeds = len(enabled_feeds)
    
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
    
    feeds_succeeded = 0
    feeds_failed = 0
    items_inserted = 0
    
    # Process each feed
    with Session(engine) as db:
        for feed_data in enabled_feeds:
            result = process_feed(db, feed_data, defaults, run_id)
            
            if result["error"]:
                # Record error
                feeds_failed += 1
                db.execute(
                    text("""
                        INSERT INTO feed_run_errors 
                        (run_id, feed_id, error_type, error_message, http_status)
                        VALUES (:run_id, :feed_id, :error_type, :error_message, :http_status)
                    """),
                    {
                        "run_id": run_id,
                        "feed_id": result["feed_id"],
                        "error_type": result["error_type"],
                        "error_message": result["error"],
                        "http_status": result["http_status"],
                    }
                )
            else:
                feeds_succeeded += 1
                items_inserted += result["inserted"]
            
            db.commit()
    
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
    
    return {
        "run_id": run_id,
        "status": status,
        "items_inserted": items_inserted,
        "feeds_failed": feeds_failed,
        "feeds_succeeded": feeds_succeeded,
        "total_feeds": total_feeds,
    }
