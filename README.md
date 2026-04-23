# Project Management MVP

A single-user Kanban board application with an AI chat assistant that can create, edit, move, and delete cards through tool calls. Built as a local-first MVP: a FastAPI backend serves the Next.js frontend as static files and persists state in SQLite.

## Features

- Single-board Kanban with five columns (Backlog, Discovery, In Progress, Review, Done).
- Drag-and-drop card movement, inline column rename, and per-card add/delete.
- AI chat sidebar powered by OpenAI; the model returns a full updated board via an `update_board` tool call, which the backend validates, repairs, and persists.
- Server-sent events stream tokens and board updates to the UI in real time.
- Optional shared-secret API key for the backend; frontend sends `X-API-Key` when configured.

## Architecture

- **Frontend**: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, dnd-kit.
- **Backend**: FastAPI, SQLite, OpenAI Python SDK, uvicorn.
- **Packaging**: multi-stage Dockerfile that builds the frontend and serves the static output from FastAPI on port 8000.

The frontend sends the live board with every chat request so the AI sees exactly what the user sees, even when a debounced save has not yet reached the database. Board PUTs are debounced (300 ms) and serialized through a promise chain to prevent out-of-order writes.

## Prerequisites

- Python 3.12+
- Node.js 20+
- An OpenAI API key
- Docker (only for the container workflow)

## Environment

Create `.env` at the repository root:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini      # optional; defaults to gpt-4o-mini
PM_API_KEY=                   # optional; when set, /api/board/* and /api/ai/* require X-API-Key
```

Frontend environment (optional, create `frontend/.env.local`):

```
NEXT_PUBLIC_PM_API_KEY=       # must match PM_API_KEY when backend auth is enabled
NEXT_PUBLIC_API_BASE_URL=     # override the default (http://localhost:8000 in dev)
```

## Quick start

### Docker (single container on port 8000)

```bash
./scripts/run-backend-docker.sh     # builds the image and starts the container
./scripts/stop-backend-docker.sh    # stops and removes the container
```

The container reads `.env` for `OPENAI_API_KEY` and mounts a Docker volume (`pm-backend-data`) so the SQLite database persists across restarts. Open http://localhost:8000 after startup.

### Local development (frontend and backend as separate processes)

Backend, from the repository root:

```bash
python -m uvicorn backend.app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on http://localhost:3000 and calls the backend on http://localhost:8000. CORS is preconfigured for both ports.

### Seed a starter board (optional)

```bash
./scripts/seed-user-board.sh
```

Uses `scripts/seed-user-board.json` to populate the default user's board via the API. Requires the backend to be running.

## Default credentials

Login accepts `user` / `password`. This is an MVP constraint; the database schema supports multiple users for a future iteration.

## API

All routes are served under `/api`. Routes marked *auth* require `X-API-Key` when `PM_API_KEY` is set.

| Method | Path | Purpose | Auth |
| --- | --- | --- | --- |
| GET | `/api/ping` | Liveness check | no |
| GET | `/api/board/{username}` | Load the user's board (creates default if missing) | yes |
| PUT | `/api/board/{username}` | Replace the user's board | yes |
| DELETE | `/api/board/{username}` | Remove the user's board | yes |
| POST | `/api/board/{username}/chat` | AI chat; body: `{"message": string, "board": BoardData}`; SSE stream | yes |
| GET | `/api/ai/ping` | AI connectivity smoke test | yes |

Chat endpoint SSE event types: `token`, `board_update`, `error`, `done`.

## Testing

Backend, from the repository root:

```bash
cd backend
uv run pytest                       # full suite
uv run pytest tests/test_ai.py      # single file
uv run pytest -k "test_name"        # single test
```

Frontend:

```bash
cd frontend
npm run test          # vitest unit/integration (single run)
npm run test:unit:watch
npm run test:e2e      # Playwright E2E (requires dev server)
npm run test:all      # unit + E2E
npm run lint
```

## Project layout

```
backend/
  app/
    main.py       FastAPI routes, CORS, auth dependency, static hosting
    ai.py         OpenAI streaming, tool call handling, board repair
    db.py         SQLite schema, DEFAULT_BOARD, validator, CRUD helpers
  tests/          pytest suites (TestClient)
frontend/
  src/
    app/          Next.js App Router pages
    components/   KanbanBoard, LoginForm, AIChatSidebar, ...
    lib/          api client, kanban types/utilities
  tests/          Playwright specs
scripts/          start/stop helpers, seed script
docs/             PLAN.md, DATABASE.md, code_review.md
Dockerfile        two-stage build; frontend then backend
```

## Documentation

- `CLAUDE.md` — guidance for Claude Code when operating in this repo.
- `docs/PLAN.md` — project plan.
- `docs/DATABASE.md` — database schema notes.
- `docs/code_review.md` — latest code review and remediation log.
