# Backend AGENTS.md

## Overview
This directory contains the FastAPI backend for the Project Management MVP.
It serves API routes for board CRUD, AI chat streaming, and static frontend output.

## Main Files
- `app/main.py`: FastAPI app, CORS config, API routes, static index handler.
- `app/db.py`: SQLite initialization and per-user board persistence.
- `app/ai.py`: OpenAI integration and SSE streaming helper.
- `tests/test_main.py`: CRUD and baseline backend behavior tests.
- `tests/test_ai.py`: AI endpoint tests with mocked OpenAI client.

## API Surface
- `GET /api/ping`
- `GET /api/board/{username}`
- `PUT /api/board/{username}`
- `DELETE /api/board/{username}`
- `GET /api/ai/ping`
- `POST /api/board/{username}/chat` (SSE stream)

## AI Chat Events
`POST /api/board/{username}/chat` requires the caller to send the live board
in the request body (`{"message": ..., "board": {...}}`). The endpoint emits
SSE `data:` payloads:
- `{"type":"token","content":"..."}`
- `{"type":"board_update","board":{...}}`
- `{"type":"error","message":"..."}`
- `{"type":"done"}`

If AI returns `update_board` tool arguments, the backend repairs (restores
omitted but still-referenced cards, restores omitted columns), validates,
persists the updated board, and emits `board_update`.

## Auth
All `/api/board/*` and `/api/ai/*` routes accept an optional `X-API-Key`
header. When `PM_API_KEY` is unset (default for dev/test), no check is done.
When set, requests without a matching header receive 401. `/api/ping` is
always unauthenticated.

## Development
- Run backend tests from repo root:
	- `python -m pytest backend/tests -v`