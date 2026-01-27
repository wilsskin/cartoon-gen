"""
Vercel serverless function entry point for FastAPI backend.
This file is required for Vercel to detect and deploy Python serverless functions.
"""
import sys
from pathlib import Path

# Add backend directory to Python path
backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Import the FastAPI app from backend
from app.main import app

# Vercel expects the handler to be named 'handler' or 'app'
# FastAPI app works directly as a Vercel handler
handler = app
