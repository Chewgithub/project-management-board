#!/bin/sh
set -e

# Start FastAPI backend
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
