"""
Database module for Neon Postgres connectivity using SQLAlchemy 2.

This module provides:
- A global SQLAlchemy engine configured for serverless environments
- A session factory for creating database sessions
- A get_db dependency for FastAPI endpoints
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

# Get DATABASE_URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Convert postgresql:// to postgresql+psycopg:// for psycopg3 compatibility
# Neon provides postgresql:// URLs, but SQLAlchemy 2.0 with psycopg3 needs postgresql+psycopg://
if DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Create engine with serverless-safe configuration
# - pool_pre_ping: Test connections before using them (important for serverless)
# - pool_size: Small pool size (2) for serverless environments
# - max_overflow: Small overflow (2) to limit connections
# - pool_timeout: Reasonable timeout for connection acquisition
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=2,
    pool_timeout=10,
    echo=False,  # Set to True for SQL query logging in development
)

# Create session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session and ensures it's closed.
    
    Usage in FastAPI endpoint:
        @app.get("/api/example")
        def example(db: Session = Depends(get_db)):
            # Use db session here
            pass
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
