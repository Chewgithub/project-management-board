from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError
from pydantic import BaseModel

from backend.app.ai import get_client, is_valid_board_payload, stream_chat
from backend.app.db import delete_board_for_user, get_board_for_user, init_db, update_board_for_user


class BoardPayload(BaseModel):
    columns: list[dict[str, Any]]
    cards: dict[str, dict[str, Any]]


class ChatRequest(BaseModel):
    message: str



@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

# Allow local frontend dev servers to call backend APIs.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

project_root = Path(__file__).resolve().parents[2]
frontend_root = project_root / "frontend"
frontend_static = frontend_root / ".next" / "static"
frontend_index = frontend_root / ".next" / "server" / "app" / "index.html"

# Static assets are only available after a frontend build.
app.mount(
    "/static",
    StaticFiles(directory=str(frontend_static), check_dir=False),
    name="static",
)
@app.get("/", response_class=HTMLResponse)
def serve_index() -> str:
    if frontend_index.exists():
        return frontend_index.read_text(encoding="utf-8")

    return (
        "<h1>Backend is running</h1>"
        "<p>Frontend build not found. Run <code>npm run build</code> in <code>frontend/</code>.</p>"
    )


@app.get("/api/ping")
def ping() -> dict[str, str]:
    return {"message": "pong"}


@app.get("/api/board/{username}")
def get_user_board(username: str) -> dict[str, Any]:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="Username is required")

    board = get_board_for_user(normalized_username)
    return {"username": normalized_username, "board": board}


@app.put("/api/board/{username}")
def put_user_board(username: str, payload: BoardPayload) -> dict[str, Any]:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="Username is required")

    payload_board = payload.model_dump()
    if not is_valid_board_payload(payload_board):
        raise HTTPException(status_code=400, detail="Invalid board payload")

    board = update_board_for_user(normalized_username, payload_board)
    return {"username": normalized_username, "board": board}


@app.delete("/api/board/{username}")
def delete_user_board(username: str) -> dict[str, Any]:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="Username is required")

    deleted = delete_board_for_user(normalized_username)
    return {"username": normalized_username, "deleted": deleted}


@app.get("/api/ai/ping")
def ai_ping() -> dict[str, str]:
    """Quick smoke-test: ask the AI what 2+2 is."""
    from backend.app.ai import MODEL

    try:
        client = get_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "What is 2+2? Reply with just the number."}],
        )
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI request failed: {exc}") from exc

    answer = response.choices[0].message.content or ""
    return {"answer": answer.strip()}


@app.post("/api/board/{username}/chat")
def chat_with_board(username: str, body: ChatRequest) -> StreamingResponse:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="Username is required")

    board = get_board_for_user(normalized_username)

    try:
        get_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    def persist_ai_board_update(updated_board: dict[str, Any]) -> None:
        update_board_for_user(normalized_username, updated_board)

    return StreamingResponse(
        stream_chat(board, body.message, on_board_update=persist_ai_board_update),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
