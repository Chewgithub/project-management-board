# Code Review

Reviewer: Claude  
Date: 2026-04-24  
Scope: full repository — `backend/`, `frontend/`, `scripts/`, Dockerfile

---

## Summary

The codebase is clean and well-scoped for an MVP. The previous review round addressed all P0/P1 items: optional bearer-token auth, save debounce and serialization, AI card deletion, board-repair logic, fallback/retry UX, and test coverage for each of those paths. What remains is a set of low-priority issues — none are blockers.

Overall: **ship-ready for single-user local use.** The items below matter if the scope grows beyond one user or the app becomes accessible beyond localhost.

---

## What is working well

- **Backend architecture** is minimal and correct. FastAPI routes are thin; business logic lives in `db.py` and `ai.py`.
- **Save pipeline** (`page.tsx`) — debounce + promise-chain serialization is a clean solution to the out-of-order PUT problem.
- **AI board repair** (`ai.py:_repair_board_update`) correctly distinguishes intentional deletions (card absent from all `cardIds`) from accidental omissions (still referenced), with tests locking in both behaviors.
- **Test coverage** is good for the backend: 26 pytest tests covering CRUD, auth, streaming, repair, error paths, and the client-board regression. Frontend vitest has 24 tests.
- **CORS** is correctly scoped to localhost origins with explicit methods/headers.

---

## Remaining issues

### P1 — Minor correctness

**C1. `get_client()` called twice per chat request**

`main.py:177–179` calls `get_client()` to fail-fast with a 503 before opening the stream. Then `ai.py:stream_chat:135` calls it again. The second call is safe (the singleton is cached), but it's confusing — a future change that modifies `get_client()` to do real work on every call would create a hidden double-cost.

**Recommendation:** pass the client into `stream_chat` rather than calling `get_client()` inside it, or remove the pre-check in `main.py` and rely on `stream_chat` to emit the error SSE.

---

**C2. `init_db()` called redundantly on every DB operation**

`db.py` lines 193, 202, 220, 229 each call `init_db()` at the top of every public function. `init_db()` is also called in the FastAPI `lifespan` at startup (`main.py:52`). The per-call calls are harmless but add a file-existence check on every request.

**Recommendation:** remove the `init_db()` calls from the four public DB functions and rely solely on the lifespan call. If a function is called outside FastAPI (e.g., in a standalone script), the caller is responsible for `init_db()`.

---

### P2 — Code health

**Q1. Schema duplication**

The board schema still lives in two parallel places with no contract test:

- `backend/app/db.py:12` — `DEFAULT_BOARD` Python dict + `is_valid_board_payload` validator
- `frontend/src/lib/kanban.ts:69` — `initialData` TypeScript object + `isBoardData` validator

A field added to one side won't be caught until manual testing. The `test_chat_uses_client_submitted_board_not_db` test provides indirect coverage, but not a direct schema contract test.

**Recommendation (if scope grows):** generate TypeScript types from the FastAPI OpenAPI schema via `openapi-typescript`. For now, a minimal safeguard would be a script that round-trips `DEFAULT_BOARD` through `isBoardData` at build time.

---

**Q2. `useMemo` no-op in `KanbanBoard`**

`KanbanBoard.tsx:32`:

```typescript
const cardsById = useMemo(() => board.cards, [board.cards]);
```

This memoizes an identity function. `board.cards` is already a plain object reference; the `useMemo` adds overhead with no benefit. `cardsById` is used only once (line 96) and could just be `board.cards` inline.

---

**Q3. Message list uses array index as key**

`AIChatSidebar.tsx:160`:

```tsx
{messages.map((msg, i) => (
  <div key={i} ...>
```

Index keys suppress React's reconciliation warnings but can cause incorrect DOM reuse if messages are ever deleted or reordered. Since messages only append here, it's practically safe — but a stable key (e.g., a monotonic counter or timestamp) is better practice.

---

**Q4. `chatEndpoint` constructed inline in `api.ts`**

`api.ts:83` builds the chat URL inline instead of using the `boardEndpoint` helper. Both use `encodeURIComponent` consistently, but the duplication means a future hostname change (e.g., adding a `/v1` prefix) needs to be made in two places.

```typescript
// Current
`${apiBaseUrl}/api/board/${encodeURIComponent(username)}/chat`

// Better: extend the helper
const chatEndpoint = (username: string) => `${boardEndpoint(username)}/chat`;
```

---

### P3 — UX nits

**U1. No "saving" indicator**

The sync message is cleared to `null` on a successful save (`page.tsx:40`). Users have no feedback that their edits are being persisted — they only learn something went wrong if a save fails. A brief "Saved" flash or a subtle spinner on the save-chain path would close this gap.

---

**U2. Hardcoded login credentials remain client-visible**

`LoginForm.tsx:5–6` hardcodes `USER = "user"` and `PASS = "password"` in the React bundle, readable by anyone with devtools. Acceptable per the MVP charter (the server-side `PM_API_KEY` is the real gate), but must be removed before any multi-user or public deployment.

---

### Testing gaps

| Gap | Priority |
|-----|----------|
| Playwright E2E for AI chat (SSE wiring regression) | Low — backend pytest covers per-event behavior |
| Real async streaming test (not `iter(chunks)`) | Low — backpressure not in MVP SLOs |
| Build-time contract test: `DEFAULT_BOARD` passes `isBoardData` | Medium — catches cross-language schema drift |
| Test for `delete_board_for_user` when user doesn't exist | Low — returns `False` by inspection, trivial to add |

---

## Quick wins

| Fix | File:line | Effort |
|-----|-----------|--------|
| Remove `useMemo` no-op | `KanbanBoard.tsx:32` | 1 line |
| Extract `chatEndpoint` helper | `api.ts:83` | 2 lines |
| Remove redundant `init_db()` calls | `db.py:193,202,220,229` | 4 lines |
| Add stable key to message list | `AIChatSidebar.tsx:160` | 2 lines |

---

## Prioritized action list

1. **Q2, Q3, Q4** — three-minute quick wins with no risk.
2. **C1** — remove the client pre-check in `main.py` or pass the client into `stream_chat` to eliminate the double call.
3. **C2** — remove per-function `init_db()` calls; rely on lifespan.
4. **U1** — add a "saving" indicator for better user feedback.
5. **Q1** — build-time schema contract test to catch cross-language drift.
6. **U2** — remove hardcoded credentials when real auth lands.
