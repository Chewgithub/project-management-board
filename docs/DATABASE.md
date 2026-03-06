# Database Approach (Part 5)

## Goal
Store each user's Kanban board persistently in SQLite, while keeping the schema simple for MVP and ready for future expansion.

## MVP Principles
- SQLite file is local and auto-created if missing.
- One board per user in MVP.
- Store board state as JSON in a single column for simplicity.
- Keep schema multi-user ready.

## Proposed Tables
- `users`
  - `id` (PK)
  - `username` (unique)
  - `password_hash`
  - `created_at`, `updated_at`

- `boards`
  - `id` (PK)
  - `user_id` (FK to `users.id`)
  - `board_key` (default `default`)
  - `title`
  - `board_json` (serialized Kanban payload)
  - `created_at`, `updated_at`

## Key Constraint
- `UNIQUE(user_id, board_key)`
  - For MVP, `board_key` stays `default`, which enforces one board per user.
  - Future: support multiple boards by using different keys.

## Why JSON for Board Data
- Matches current frontend shape directly.
- Fast to implement and iterate.
- Avoids over-modeling cards/columns too early.
- Easy to extend for AI-assisted updates in later parts.

## Canonical JSON Shape
The canonical payload shape is documented in:
- `docs/database-schema.json` under `kanbanBoardJsonShape`.

## Initial Seed Strategy (MVP)
- On first login for a user:
  - Create user row if missing.
  - Create default board row if missing.
  - Use existing frontend initial board JSON as first `board_json`.

## Future Migration Path
If needed later, normalize `board_json` into dedicated `columns` and `cards` tables while keeping backward compatibility via migration scripts.
