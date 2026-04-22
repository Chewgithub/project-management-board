#!/bin/sh
set -e

# Stop FastAPI backend (kill uvicorn)
pkill -f uvicorn || true
