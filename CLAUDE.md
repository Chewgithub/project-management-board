# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Project Management MVP web app with a Kanban board and AI chat sidebar. The AI can create, edit, and move cards on the board via tool calls.

MVP constraints: single hardcoded user (`user`/`password`), one board per user, runs locally in Docker.

Planning and schema docs live in `docs/` (`PLAN.md`, `DATABASE.md`).

## Environment

`.env` at the project root is loaded by the backend via `python-dotenv`:
- `OPENAI_API_KEY` — required; backend raises at first AI call if missing.
- `OPENAI_MODEL` — optional; defaults to `gpt-4o-mini` (see `backend/app/ai.py`).
- `PM_API_KEY` — optional; when set, all `/api/board/*` and `/api/ai/*` routes require an `X-API-Key` header matching this value. `/api/ping` is always open. The frontend reads `NEXT_PUBLIC_PM_API_KEY` and sends the header on every backend call.

## Commands

### Backend

All backend commands run from the **project root** (`pm/`), since imports use the `backend.*` module path.

```bash
python -m uvicorn backend.app.main:app --reload  # dev server on port 8000

cd backend && uv run pytest                      # run all tests
cd backend && uv run pytest tests/test_main.py   # run a single test file
cd backend && uv run pytest -k "test_name"       # run a single test
```

### Frontend

```bash
cd frontend
npm run dev          # dev server on port 3000
npm run build        # production build
npm run lint         # ESLint
npm run test         # vitest unit tests (run once)
npm run test:unit:watch  # vitest watch mode
npm run test:e2e     # Playwright E2E tests (requires running dev server)
npm run test:all     # unit + E2E
```

### Docker

```bash
./scripts/start.sh   # build and start the container
./scripts/stop.sh    # stop the container
```

The Dockerfile builds the frontend and serves it as static files via FastAPI at `/`.

## Architecture

**Frontend** (Next.js App Router, TypeScript, Tailwind CSS 4):
- `src/app/page.tsx` — root component; manages auth state, board state, and layout
- `src/components/` — KanbanBoard (dnd-kit drag-and-drop), LoginForm, AIChatSidebar
- `src/lib/api.ts` — all backend API calls
- `src/lib/kanban.ts` — board data utilities and type guards

**Backend** (FastAPI, SQLite, OpenAI):
- `app/main.py` — routes and app setup; CORS allows localhost:3000/3001
- `app/db.py` — SQLite operations; DB is auto-created on startup; board stored as JSON blob
- `app/ai.py` — OpenAI streaming with tool calling; streams SSE events (token, board_update, error, done)

**Database** (SQLite, local file):
- `users`: id, username, password_hash, created_at, updated_at
- `boards`: id, user_id, board_key, title, board_json, created_at, updated_at; UNIQUE(user_id, board_key)

**API surface:**
- `GET  /api/ping` — health check (always unauthenticated).
- `GET  /api/board/{username}` — load board.
- `PUT  /api/board/{username}` — save board.
- `DELETE /api/board/{username}` — reset board.
- `POST /api/board/{username}/chat` — AI chat (SSE streaming). Body must include the live `board` so the AI sees the same state the user sees, even if a debounced save hasn't landed yet. Returns 404 for unknown users.
- `GET  /api/ai/ping` — check AI connectivity.

**AI flow:** Frontend sends `{message, board}` → FastAPI validates board → OpenAI with `update_board` tool → backend streams tokens, repairs the AI's tool output (restores omitted-but-still-referenced cards/columns; honors deletions), persists, and emits `board_update`/`error`/`done` SSE events.

**Save semantics:** `page.tsx` debounces board PUTs by ~300ms and serializes them through a promise chain so an older snapshot can never overwrite a newer one. When the backend is unreachable on login, the UI enters fallback mode (local-only) and shows a Retry button; AI chat is hidden until reconnect.

## Coding Standards

- No over-engineering. Keep it simple. No unnecessary defensive programming.
- No emojis, ever.
- Identify root cause before fixing bugs — prove with evidence.
- Use latest idiomatic approaches for the stack.
