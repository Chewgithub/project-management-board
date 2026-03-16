# Scripts AGENTS.md

## Overview
This directory contains helper scripts for local backend runtime and Docker workflows.

## Scripts
- `start.sh`: Start FastAPI (`uvicorn backend.app.main:app`).
- `stop.sh`: Stop local `uvicorn` process.
- `run-backend-docker.sh`: Build and run backend container on port `8000`.
- `stop-backend-docker.sh`: Stop and remove backend container.
- `seed-user-board.sh`: Seed the `user` board using `seed-user-board.json`.

## Expected Usage
From repo root:
- `./scripts/run-backend-docker.sh`
- `./scripts/seed-user-board.sh`
- `./scripts/stop-backend-docker.sh`

For local non-Docker runs, `start.sh` and `stop.sh` are used by top-level scripts.