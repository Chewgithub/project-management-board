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
`POST /api/board/{username}/chat` emits SSE `data:` payloads:
- `{"type":"token","content":"..."}`
- `{"type":"board_update","board":{...}}`
- `{"type":"done"}`

If AI returns `update_board` tool arguments, the backend persists the updated
board for the user before emitting `board_update`.

## Development
- Run backend tests from repo root:
	- `python -m pytest backend/tests -v`