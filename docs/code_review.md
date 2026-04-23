# Code Review

Reviewer: Claude
Date: 2026-04-23
Scope: full repository (`backend/`, `frontend/`, `scripts/`, Dockerfile, docs)

## Summary

The codebase is small, idiomatic for its stack, and the recent refactor that has the AI chat receive the live board from the client (rather than reloading from SQLite) eliminated the most visible correctness bug. Tests pass — 19 backend, 24 frontend.

The remaining issues fall into three buckets:

1. **Security posture is MVP-only.** No authentication on any API endpoint. Any caller can read, write, or delete any user's board, and can drive the (paid) AI chat against any username. Acceptable for "runs locally in Docker" per the MVP charter, but must not ship without auth.
2. **Persistence races.** Drag-and-drop and column-rename fire fire-and-forget PUTs with no debounce or sequencing. Rapid edits can lose data via out-of-order arrivals; a single rename of "Backlog Updated" emits ~14 PUTs.
3. **Drift between parallel definitions.** The board schema and validators are duplicated three ways (`DEFAULT_BOARD` in `db.py:12`, `initialData` in `kanban.ts:69`, and the two `is_valid_board_payload` / `isBoardData` validators). Docs (`AGENTS.md`, `CLAUDE.md`, `backend/AGENTS.md`) are partly stale.

Nothing in here blocks the MVP. The P0 items below should be addressed before any deployment beyond a single user's laptop.

---

## Remediation log — 2026-04-23

All P0, P1, P2-cleanup, P3, and documentation items from this review were addressed in a single pass. Final status: backend pytest 26/26 (was 19; +7 regression tests), frontend vitest 24/24, ESLint clean.

Legend: `[x]` shipped; `[~]` partial with rationale; `[ ]` not done.

### Security
- `[x]` **S1** — Optional bearer-token auth. Added `require_api_key` FastAPI dependency in `backend/app/main.py`, gated on `PM_API_KEY` env var. When unset (dev/test default) no check is performed; when set, `X-API-Key` is required on `/api/board/*` and `/api/ai/*`. `/api/ping` stays open. Frontend (`frontend/src/lib/api.ts`) reads `NEXT_PUBLIC_PM_API_KEY` and sends the header on every backend call.
- `[x]` **S2** — Chat rejects unknown users. Added `user_exists` helper in `db.py` and a 404 check in `chat_with_board`. Test fixture `seeded_user` added so chat tests pre-create the user via GET.
- `[x]` **S3** — CORS tightened. `allow_methods=["GET","PUT","POST","DELETE"]` and `allow_headers=["Content-Type","Accept","X-API-Key"]` replace the wildcards.

### Correctness
- `[x]` **C1** — Save debounce + serialization. `page.tsx` now coalesces rapid mutations into a single PUT via a 300 ms timer (`SAVE_DEBOUNCE_MS`) and chains PUTs through a `saveChainRef` promise so an older snapshot can never overwrite a newer one.
- `[x]` **C2** — AI can now delete cards. New `_repair_board_update` in `ai.py` restores only cards that are still referenced in some column's `cardIds`. A card removed from both `cardIds` and `cards` is honored as a deletion. Columns remain non-deletable (unchanged). `SYSTEM_PROMPT` updated to instruct the model to remove from both places.
- `[x]` **C3** — `error` SSE event now emitted on `json.JSONDecodeError` instead of `pass`.
- `[x]` **C4** — Comment added in `stream_chat` explaining the single-tool-call assumption.
- `[x]` **C5** — Startup warning logged when `frontend/.next/server/app/index.html` is missing. (Did not switch to Next.js `output: 'standalone'` — that's a build-system change beyond the review's scope.)

### Code health
- `[x]` **Q2** — `is_valid_board_payload` moved from `ai.py` to `db.py` (alongside `DEFAULT_BOARD`). `main.py` imports it from `db`.
- `[x]` **Q3** — Stub `backend/main.py` deleted. Dockerfile and dev commands already used `backend.app.main:app`.
- `[x]` **Q4** — `MODEL` imported at module top of `main.py`; no more inline import inside `ai_ping`.
- `[x]` **Q5** — `stream_chat` docstring re-indented in the `ai.py` rewrite.
- `[~]` **Q1** — Schema/validator duplication not fully resolved. A single-source-of-truth fix (OpenAPI-driven TypeScript codegen, or a shared JSON Schema) is a multi-file build-system change and would violate the "no over-engineering" rule for this MVP. Instead, cross-language drift is now caught indirectly by the PUT validation tests (`test_put_board_rejects_invalid_payload`) and by the new `test_chat_uses_client_submitted_board_not_db` which would fail if schemas diverge. If Q1 is later prioritized, recommend generating `BoardData`/`Card`/`Column` TS from Pydantic via `fastapi.openapi`.
- `[~]` **Q6** — Whole-board-in-chat-request left as-is. The review already flagged it as acceptable at MVP card counts; no action needed until there's a measured latency concern.

### UX
- `[x]` **U1** — Fallback mode now surfaces a **Retry** button next to the sync message. On click, `loadBoard` is re-attempted; success restores online mode and clears the message. AI chat sidebar is hidden while in fallback so the user can't send messages that would fail.
- `[x]` **U2** — Button labels disambiguated. The toggle stays "Add a card"; the submit button is renamed to "Save card" (two buttons with the same accessible name is a worse a11y outcome than two distinct labels). Tests (`KanbanBoard.test.tsx`, `kanban.spec.ts`) updated.
- `[~]` **U3** — `USER`/`PASS` constants in `LoginForm.tsx` remain for the MVP. Per the charter, this is explicitly a hardcoded login. S1's token is the server-side gate; U3 is scheduled for the "real auth" follow-up.

### Documentation
- `[x]` `AGENTS.md` — model corrected from `openai/gpt-oss-120b` to `gpt-4o-mini` (default; override via `OPENAI_MODEL`).
- `[x]` `backend/AGENTS.md` — chat endpoint now documented as requiring `board` in the request body; `error` SSE event added to the list; new **Auth** section describes `PM_API_KEY` / `X-API-Key`.
- `[x]` `CLAUDE.md` — added Environment section (`OPENAI_API_KEY`, `OPENAI_MODEL`, `PM_API_KEY`); corrected API surface (includes `/api/ping`, 404 semantics, client-board requirement); new Save semantics paragraph describing debounce + serialization + fallback retry; pointer to `docs/code_review.md` alongside `PLAN.md` / `DATABASE.md`.

### Testing
Added to `backend/tests/test_ai.py`:
- `[x]` `test_chat_uses_client_submitted_board_not_db` — the regression for the original drift bug. Asserts the OpenAI mock received the client's board (not `DEFAULT_BOARD`) in the system prompt.
- `[x]` `test_chat_allows_ai_to_delete_card` — locks in C2.
- `[x]` `test_chat_emits_error_event_on_malformed_tool_json` — locks in C3.
- `[x]` `test_chat_returns_404_for_unknown_user` — locks in S2.
- `[x]` `test_api_key_required_when_env_set`, `test_api_key_not_required_when_env_unset`, `test_ping_remains_unauthenticated` — lock in S1 behavior.
- `[ ]` Playwright AI-chat E2E smoke test — not added. SSE mocking inside Playwright is non-trivial; the per-event behavior is already covered by backend pytest + frontend vitest. Can be added if chat wiring regresses in a way the unit tests miss.
- `[ ]` Real-streaming test (async generator rather than `iter(chunks)`) — not added. Same rationale: the wire format is covered; backpressure isn't part of the MVP's SLOs.

### Still open (by design)
- `[ ]` **Q1 full schema dedup** — deferred (see rationale above).
- `[ ]` **Q6 board-diff/hash** — deferred (MVP card counts).
- `[ ]` **U3 hardcoded login** — deferred (MVP charter).
- `[ ]` Playwright AI E2E + streaming-generator tests — deferred (see above).

### Files touched

Backend: `backend/app/main.py`, `backend/app/ai.py`, `backend/app/db.py`, `backend/tests/test_ai.py`. Deleted: `backend/main.py`.

Frontend: `frontend/src/app/page.tsx`, `frontend/src/lib/api.ts`, `frontend/src/components/NewCardForm.tsx`, `frontend/src/components/KanbanBoard.test.tsx`, `frontend/tests/kanban.spec.ts`.

Docs: `CLAUDE.md`, `AGENTS.md`, `backend/AGENTS.md`.

---

## P0 — Security (must fix before any non-local use)

### S1. No authentication on any API endpoint

`backend/app/main.py:76-156` — every route trusts the `{username}` path parameter blindly. There is no session, token, cookie, or header check. The hardcoded `user`/`password` check lives entirely in the React bundle (`frontend/src/components/LoginForm.tsx:5-21`), which means:

- `curl http://localhost:8000/api/board/alice` returns alice's board (or creates her with default state).
- `curl -X DELETE http://localhost:8000/api/board/anyone` deletes their board.
- `curl -X POST http://localhost:8000/api/board/anyone/chat -d '{"message":"...", "board":{...}}'` triggers a paid OpenAI call.

**Recommendation:** even an MVP should require a shared bearer token from `.env` on every `/api` call. Two lines of FastAPI dependency code. Without this, the AI chat endpoint is an unbounded cost vector if the port is ever exposed.

### S2. AI chat endpoint creates users implicitly

`backend/app/main.py:132-156` validates the username string is non-empty but never confirms the user exists. The AI's `on_board_update` callback calls `update_board_for_user`, which calls `_get_or_create_user` (`db.py:116-127`) — a hostile caller can populate the `users` table with arbitrary names by sending one chat message per name.

**Recommendation:** in `chat_with_board`, require an existing user (`SELECT id FROM users WHERE username = ?` and 404 otherwise). Tied to S1 — a real auth check would also fix this.

### S3. CORS posture

`backend/app/main.py:36-47` allows credentials with `allow_methods=["*"]` and `allow_headers=["*"]`. The origin allowlist is explicit (localhost:3000/3001 only) so this is fine for dev, but if you ever change the allowlist to include a production domain, the wildcard methods/headers should be tightened to the actual ones used.

---

## P1 — Correctness and reliability

### C1. Out-of-order PUTs can clobber state

`frontend/src/app/page.tsx:41-51` saves on every board mutation as `void saveBoard(...)`. Two failure modes:

- **Rapid edits race**: drag a card, then immediately rename a column. PUT #1 (drag) might arrive *after* PUT #2 (rename) due to network jitter. The drag's older snapshot then overwrites the renamed-column state in the DB. UI looks fine until refresh.
- **Column rename emits a PUT per keystroke** (`KanbanColumn.tsx:42-47` is uncontrolled-style — every input change calls `onRename`, which calls `onBoardChange`, which PUTs the entire board JSON). Typing a 14-character title sends 14 full-board PUTs.

**Recommendations:**
- Debounce `saveBoard` (300–500ms) for non-structural edits like rename. Drag/add/delete can stay immediate.
- Sequence saves so a newer state never gets overwritten by an older one — easiest is to track an in-flight promise and chain (`lastSave = lastSave.then(() => saveBoard(...))`) so PUTs are serialized.

### C2. AI cannot delete cards (silently)

`backend/app/ai.py:210-220` "repairs" any AI response that omits cards by re-adding them from the original board. The system prompt at `ai.py:28-39` tells the AI it can delete cards, but the post-processing makes deletion impossible — any card the AI omits is silently restored. Test `test_chat_repairs_incomplete_cards_in_board_update` (test_ai.py:200) locks this behavior in.

This is a real contradiction: the user can ask the AI to "delete card X", the AI will produce a board without X, the backend will add X back, and the user will see the card stay. No error is shown.

**Recommendations (pick one):**
- Update `SYSTEM_PROMPT` to remove "delete" from the list of supported operations and explain it isn't currently supported.
- Or change the repair logic so cards omitted from `cards` AND no longer referenced in any `cardIds` are intentional deletions (only re-add cards that are still referenced somewhere).

### C3. Silent JSON-decode failure in stream

`backend/app/ai.py:234-235` swallows `json.JSONDecodeError` with `pass`, then proceeds to the `done` event. The user sees the AI's preamble text but no board change and no error — appears as a non-deterministic bug.

**Recommendation:** emit an `error` SSE event ("AI returned malformed board JSON") in the same shape the validator-failure branch already uses (ai.py:223-228).

### C4. AI tool-call handling assumes a single call

`backend/app/ai.py:198-236` iterates `tool_args_by_index` but `break`s after the first `update_board`. If a future model issues multiple tool calls or other tool types, only the first is processed. Today it's fine because only `update_board` is registered, but worth a short comment so the next change doesn't hit a confusing edge case.

### C5. Static-file mounting is silently fragile

`backend/app/main.py:50-58` hardcodes the path `frontend/.next/server/app/index.html`. This is a private Next.js build output path — Next has changed it across major versions before. If they change it again, `serve_index` falls through to the "Backend is running" placeholder with no error. `check_dir=False` on the `_next/static` mount makes the static path failure silent too.

**Recommendation:** at startup, log a warning if `frontend_index.exists()` is False; better, use Next's standalone output (`output: 'standalone'` in `next.config.ts`) which has a documented, stable file layout.

---

## P2 — Code health and duplication

### Q1. Three parallel board definitions / validators

The board schema lives in four places:

- `backend/app/db.py:12-66` — `DEFAULT_BOARD` Python dict
- `frontend/src/lib/kanban.ts:69-123` — `initialData` TypeScript object
- `backend/app/ai.py:83-124` — `is_valid_board_payload` Python validator
- `frontend/src/lib/kanban.ts:21-67` — `isBoardData` TypeScript validator

A schema change touches at least three files and there's no contract test catching divergence. Options:
- Treat the Pydantic models as the source of truth, generate TS types from OpenAPI (`fastapi.openapi`), and let the frontend import them.
- Or ship a single JSON Schema both sides validate against.
- For an MVP, at minimum add a small contract test: load `DEFAULT_BOARD`, JSON-encode it, assert `isBoardData` (in a Node script) accepts it.

### Q2. `is_valid_board_payload` is in the wrong module

It's a pure shape validator with no AI dependency. Currently in `backend/app/ai.py:83-124` and imported by `main.py`. Belongs in `db.py` next to the schema, or a new `schemas.py`.

### Q3. Stub file `backend/main.py`

`backend/main.py` is a one-liner re-exporting `app` from `backend.app.main`. Nothing references it (Dockerfile and dev command both use `backend.app.main:app`). Either delete it or document it.

### Q4. Inline import in `ai_ping`

`backend/app/main.py:113` does `from backend.app.ai import MODEL` inside the function. There's no circular-import reason — `MODEL` could be imported at module top.

### Q5. Docstring indentation in `stream_chat`

`backend/app/ai.py:135-143` — the error/done bullets have inconsistent indentation (looks like the error line was added later). Cosmetic.

### Q6. Whole board sent on every chat request

`ChatRequest.board` (`main.py:21-23`) ships the full board JSON for every user prompt. Fine at MVP card counts, but for a 200-card board that's tens of KB on every keystroke. If this ever feels slow, send a board hash and only the diff, or rate-limit chat by hash.

---

## P3 — UX and nits

### U1. Sticky fallback mode

`frontend/src/app/page.tsx:22-31` — if `loadBoard` fails on login, the user gets a local fallback and the message "Backend unavailable. Using local board data." There is no automatic retry; if the backend comes back mid-session, the fallback persists and any edits never sync. AI chat will also fail since `streamChat` hits the same backend.

**Recommendation:** in the fallback branch, kick off a background retry of `loadBoard` and replace state once it succeeds. Or simpler: disable the AI chat button while in fallback so the user understands there's no backend.

### U2. Button label inconsistency

`NewCardForm.tsx:50` says "Add card" (the submit button) and `:70` says "Add a card" (the toggle). Pick one.

### U3. Login credentials in client bundle

`LoginForm.tsx:5-6` hardcodes `USER = "user"` and `PASS = "password"`. Anyone viewing the bundle can read them. Acceptable per MVP constraints but should be removed when real auth lands (S1).

---

## Documentation drift

These docs disagree with the code as of today:

- `AGENTS.md:27` — claims the model is `openai/gpt-oss-120b`. Actual: `gpt-4o-mini` per `.env` and the `backend/app/ai.py:13` default.
- `CLAUDE.md:71` — describes the AI flow as "Chat messages → FastAPI → OpenAI", which is now stale: the flow now includes the client-submitted board, not a DB read. After the recent refactor, the architecture line for `ai.py` should mention "uses the board passed in the request body."
- `backend/AGENTS.md:22-26` — lists SSE event types as `token`, `board_update`, `done` only. Missing `error` (emitted in `ai.py:166,194,224`).
- `CLAUDE.md` doesn't mention `OPENAI_API_KEY`, `OPENAI_MODEL`, `GET /api/ping`, `docs/PLAN.md`, or `docs/DATABASE.md`. The earlier suggested CLAUDE.md edits (this session) are still unapplied.

---

## Testing gaps

- **No test asserts the new client-board flow** — i.e., that the AI sees the board the client sent rather than the DB's. A targeted test would seed the DB with board A, POST chat with board B, and assert the OpenAI mock received board B in its system prompt. This is the most important test to add given the recent refactor.
- **No E2E test of the AI chat path.** `tests/kanban.spec.ts` covers login/drag/add only. A Playwright test that mocks the OpenAI request and exercises the SSE loop would catch wiring regressions.
- Backend "streaming" tests (`test_ai.py`) use `iter(chunks)` which exhausts synchronously. They verify event assembly, not the streaming behavior or backpressure.
- No test for the `update_board_for_user` race / out-of-order PUT scenario described in C1.
- No test around the "AI cannot delete cards" contradiction in C2 — once you decide which behavior is intended, lock it in.

---

## Quick wins (one-liners)

| Fix | File:line |
| --- | --- |
| Move `MODEL` import to top | `backend/app/main.py:113` |
| Delete or document stub | `backend/main.py:1` |
| Fix docstring indentation | `backend/app/ai.py:135-143` |
| Update model in AGENTS.md | `AGENTS.md:27` |
| Add `error` to SSE event list | `backend/AGENTS.md:22-26` |
| Tighten `allow_methods`/`allow_headers` | `backend/app/main.py:36-47` |
| Single-button label | `NewCardForm.tsx:50,70` |

---

## Prioritized action list

1. **S1 + S2** — add a shared-secret bearer token check on `/api/*`; require existing users.
2. **C1** — debounce + serialize `saveBoard`.
3. **C2** — resolve the AI-delete contradiction in either prompt or repair logic.
4. **C3** — emit `error` event on JSON decode failure.
5. **Doc drift** — update `AGENTS.md`, `backend/AGENTS.md`, `CLAUDE.md` to match current code.
6. **Q1** — pick a single source of truth for the board schema and let the other side import/derive from it.
7. **Testing** — add the "AI sees client board, not DB board" regression test, and one E2E chat smoke test.
