# Frontend AGENTS.md

## Overview
This directory contains the Next.js frontend for the Project Management MVP.
It includes login, backend-backed Kanban persistence, and a streaming AI chat
sidebar that can update the board.

## Main Files
- `src/app/page.tsx`: Login flow, board loading/saving, sync status, AI sidebar wiring.
- `src/components/KanbanBoard.tsx`: Board UI interactions (drag, rename, add/delete cards).
- `src/components/AIChatSidebar.tsx`: Streaming chat UI and board update handling.
- `src/lib/api.ts`: HTTP helpers for board CRUD and chat streaming.
- `src/lib/kanban.ts`: Frontend board types and local board utilities.

## Runtime Behavior
- Login accepts only `user` / `password`.
- After login, board is loaded from `GET /api/board/{username}`.
- Board edits save via `PUT /api/board/{username}`.
- AI chat posts to `POST /api/board/{username}/chat` and consumes SSE events:
  - `token`: append assistant text
  - `board_update`: replace board state in UI
  - `done`: end of stream

## Testing
- Unit/integration tests live in `src/**/*.test.ts(x)`.
- Core coverage includes login flow, board interactions, API helpers, and AI chat sidebar.
- Commands:
  - `npm run test`
  - `npm run test:unit`
  - `npm run test:e2e`

## Notes
- In frontend-only mode (backend unavailable), the app falls back to local board data.
- Styling follows project color variables from `src/app/globals.css`.