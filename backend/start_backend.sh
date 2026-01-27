#!/bin/bash
# Backend startup script for CartoonGen

cd "$(dirname "$0")"
echo "Starting backend server on http://localhost:8000"
echo "Press Ctrl+C to stop"
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
