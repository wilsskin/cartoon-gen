"""
Database initialization script for RSS ingestion schema.

This script creates the necessary tables, indexes, and extensions for the RSS feed
ingestion system. It is safe to run multiple times (idempotent).

Usage:
    # From the project root directory:
    cd /path/to/cartoon-gen
    python3 -m backend.scripts.init_db
    
    # OR from the backend directory:
    cd backend
    python3 -m scripts.init_db

The script requires DATABASE_URL to be set in the environment or in backend/.env
"""

import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text

# Load environment variables from backend/.env
backend_path = Path(__file__).resolve().parent.parent
env_path = backend_path / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# Import engine from db module
# Add backend directory to path so we can import db
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from db import engine


def init_schema():
    """
    Initialize the database schema for RSS ingestion.
    Creates extensions, tables, and indexes.
    """
    print("Initializing database schema...")
    
    with engine.begin() as conn:
        # 0) Ensure pgcrypto extension exists
        print("  Creating pgcrypto extension...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto;"))
        
        # 1) Table: feeds
        print("  Creating feeds table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS feeds (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                category_default TEXT,
                language TEXT,
                enabled BOOLEAN NOT NULL DEFAULT true,
                etag TEXT,
                last_modified TEXT,
                last_fetched_at TIMESTAMPTZ
            );
        """))
        
        # 2) Table: items
        print("  Creating items table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                summary TEXT,
                url TEXT NOT NULL,
                published_at TIMESTAMPTZ,
                category TEXT,
                fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """))
        
        # 3) Table: runs
        print("  Creating runs table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS runs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                finished_at TIMESTAMPTZ,
                status TEXT NOT NULL,
                total_feeds INT NOT NULL DEFAULT 0,
                feeds_succeeded INT NOT NULL DEFAULT 0,
                feeds_failed INT NOT NULL DEFAULT 0,
                items_inserted INT NOT NULL DEFAULT 0,
                error_summary TEXT
            );
        """))
        
        # 4) Table: feed_run_errors
        print("  Creating feed_run_errors table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS feed_run_errors (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                feed_id TEXT NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                http_status INT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """))
        
        # 5) Deduplication and query indexes
        print("  Creating indexes...")
        
        # Unique index on (feed_id, url) for items - prevents duplicates
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS items_feed_id_url_unique 
            ON items(feed_id, url);
        """))
        
        # Index on items(published_at) for time-based queries
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS items_published_at_idx 
            ON items(published_at);
        """))
        
        # Index on items(feed_id) for feed-specific queries
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS items_feed_id_idx 
            ON items(feed_id);
        """))
        
        # Index on runs(started_at) for run history queries
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS runs_started_at_idx 
            ON runs(started_at);
        """))
        
        # Additional useful indexes
        # Index on feed_run_errors(run_id) for error lookups
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS feed_run_errors_run_id_idx 
            ON feed_run_errors(run_id);
        """))
        
        # Index on feed_run_errors(feed_id) for feed error history
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS feed_run_errors_feed_id_idx 
            ON feed_run_errors(feed_id);
        """))
    
    print("✓ Database schema initialized successfully!")


if __name__ == "__main__":
    try:
        init_schema()
    except Exception as e:
        print(f"✗ Error initializing schema: {e}")
        sys.exit(1)
