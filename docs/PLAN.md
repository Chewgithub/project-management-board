# High level steps for project

Part 1: Plan

- [x] Review AGENTS.md and business requirements
- [x] Review technical decisions and limitations
- [x] Review starting point and color scheme
- [x] Enrich PLAN.md with detailed substeps for each part
- [x] Add checklists for each part
- [x] Add tests and success criteria for each part
- [x] Create AGENTS.md in frontend describing existing code
- [x] Ensure user checks and approves the plan

**Tests:**
- AGENTS.md in frontend exists and accurately describes the code
- PLAN.md contains detailed substeps, checklists, and success criteria for all parts
- User reviews and approves the plan

**Success Criteria:**
- All planning documentation is clear, actionable, and approved
- All checklists and tests are present for each project phase

Part 2: Scaffolding

- [x] Set up Docker infrastructure
- [x] Scaffold backend/ with FastAPI
- [x] Write start and stop scripts in scripts/
- [x] Serve example static HTML from backend
- [x] Confirm 'hello world' works locally
- [x] Confirm API call works

**Tests:**
- Docker container builds and runs
- Static HTML served at /
- API endpoint returns expected response

**Success Criteria:**
- Local server runs in Docker
- Both static HTML and API call are functional

Part 3: Add in Frontend

- [x] Update backend to serve statically built frontend
- [x] Build frontend demo Kanban board
- [x] Display Kanban board at /
- [x] Add unit and integration tests

**Tests:**
- Frontend builds successfully
- Kanban board displays at /
- All tests pass

**Success Criteria:**
- Kanban board is visible and interactive
- Tests cover main functionality

Part 4: Add in a fake user sign in experience

- [x] Add login page at /
- [x] Require login with dummy credentials ('user', 'password')
- [x] Allow logout
- [x] Add comprehensive tests

**Tests:**
- Login required to access Kanban
- Login and logout work as expected
- Tests cover authentication flow

**Success Criteria:**
- Authentication is enforced
- Tests validate login/logout

Part 5: Database modeling

- [x] Propose database schema for Kanban
- [x] Save schema as JSON
- [x] Document database approach in docs/
- [x] Get user sign off

**Tests:**
- Schema is documented and saved
- User reviews and approves schema

**Success Criteria:**
- Database schema is clear and approved

Part 6: Backend

- [x] Add API routes for Kanban CRUD
- [x] Support per-user Kanban
- [x] Create database if it doesn't exist
- [x] Add backend unit tests

**Tests:**
- API routes work for Kanban CRUD
- Database is created if missing
- Tests cover backend logic

**Success Criteria:**
- Backend API is functional and tested

Part 7: Frontend + Backend

- [x] Integrate frontend with backend API
- [x] Persist Kanban board
- [x] Add thorough tests

**Tests:**
- Frontend updates Kanban via API
- Kanban persists across reloads
- Tests cover integration

**Success Criteria:**
- Persistent Kanban board with API integration

Part 8: AI connectivity

- [x] Enable backend to call AI via OpenAI
- [x] Test AI connectivity with '2+2' example

**Tests:**
- AI call returns correct result

**Success Criteria:**
- Backend can call AI and receive responses

Part 9: AI Kanban updates

- [x] Extend backend to call AI with Kanban JSON and user question
- [x] AI responds with structured outputs (response + optional Kanban update)
- [x] Add thorough tests

**Tests:**
- AI responds with structured output
- Kanban updates as directed by AI
- Tests cover AI integration

**Success Criteria:**
- AI can update Kanban and respond to user

Part 10: AI chat sidebar

- [x] Add sidebar widget to UI for AI chat
- [x] Support full AI chat
- [x] Allow LLM to update Kanban via structured outputs
- [x] UI refreshes automatically if Kanban is updated

**Tests:**
- Sidebar chat works
- Kanban updates via AI
- UI refreshes on Kanban change

**Success Criteria:**
- AI chat sidebar is functional and integrated

Part 11: AI board update reliability

- [x] AI often returns partial board JSON (omitting unchanged cards or columns)
- [x] Repair logic fills in missing cards from the original board before validation
- [x] Repair logic restores missing columns from the original board before validation
- [x] Stronger system prompt instructs AI to always return the complete board
- [x] Tests cover all repair scenarios (partial cards, missing cards field, missing columns)

**Root cause:** The `update_board` tool call returned by the AI frequently omitted unchanged cards from the `cards` dict, causing validation to fail (columns referenced card IDs not present in `cards`). The AI also sometimes returned fewer columns than the original board.

**Fix:** After parsing the AI's tool call arguments, repair the board payload before validation:
1. If `cards` is missing or not a dict, initialise it as an empty dict.
2. Fill in any cards from the original board that the AI omitted (using `setdefault` so the AI's version wins).
3. Append any columns from the original board that the AI omitted entirely.

**Tests:**
- Partial cards dict is repaired and board update succeeds
- Missing `cards` field is repaired and board update succeeds
- Missing columns are repaired and board update succeeds
- Invalid card references (unknown IDs) still fail validation

**Success Criteria:**
- AI can move, create, and edit cards reliably without validation failures from partial responses