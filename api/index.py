"""
Vercel serverless function entry point for FastAPI backend.
This file is required for Vercel to detect and deploy Python serverless functions.

Export only `app` (ASGI). Do NOT set handler=app - Vercel checks handler first
and expects a BaseHTTPRequestHandler class, causing TypeError: issubclass() arg 1 must be a class.
"""
import sys
from pathlib import Path

# Add backend directory to Python path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Import the FastAPI app from backend - Vercel uses `app` for ASGI/WSGI
from app.main import app
