import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError
from pydantic import BaseModel

from backend.app.ai import MODEL, get_client, stream_chat
from backend.app.db import (
    delete_board_for_user,
    get_board_for_user,
    init_db,
    is_valid_board_payload,
    update_board_for_user,
    user_exists,
)

logger = logging.getLogger(__name__)


class BoardPayload(BaseModel):
    columns: list[dict[str, Any]]
    cards: dict[str, dict[str, Any]]


class ChatRequest(BaseModel):
    message: str
    board: BoardPayload


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Optional shared-secret check, gated on PM_API_KEY env var.

    If PM_API_KEY is unset (dev/test default), no check is performed. When set,
    every protected request must present a matching X-API-Key header.
    """
    expected = os.getenv("PM_API_KEY")
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if not frontend_index.exists():
        logger.warning(
            "Next.js index.html not found at %s — '/' will serve a placeholder. "
            "Run `npm run build` in frontend/.",
            frontend_index,
        )
    yield


project_root = Path(__file__).resolve().parents[2]
frontend_root = project_root / "frontend"
frontend_static = frontend_root / ".next" / "static"
frontend_index = frontend_root / ".next" / "server" / "app" / "index.html"


app = FastAPI(lifespan=lifespan)

# Local dev only: tighten origins/methods/headers to what the frontend actually uses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "PUT", "POST", "DELETE"],
    allow_headers=["Content-Type", "Accept", "X-API-Key"],
)

# Next.js build output references /_next/static/... so mount at that path.
app.mount(
    "/_next/static",
    StaticFiles(directory=str(frontend_static), check_dir=False),
    name="next-static",
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


@app.get("/api/board/{username}", dependencies=[Depends(require_api_key)])
def get_user_board(username: str) -> dict[str, Any]:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="Username is required")

    board = get_board_for_user(normalized_username)
    return {"username": normalized_username, "board": board}


@app.put("/api/board/{username}", dependencies=[Depends(require_api_key)])
def put_user_board(username: str, payload: BoardPayload) -> dict[str, Any]:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="Username is required")

    payload_board = payload.model_dump()
    if not is_valid_board_payload(payload_board):
        raise HTTPException(status_code=400, detail="Invalid board payload")

    board = update_board_for_user(normalized_username, payload_board)
    return {"username": normalized_username, "board": board}


@app.delete("/api/board/{username}", dependencies=[Depends(require_api_key)])
def delete_user_board(username: str) -> dict[str, Any]:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="Username is required")

    deleted = delete_board_for_user(normalized_username)
    return {"username": normalized_username, "deleted": deleted}


@app.get("/api/ai/ping", dependencies=[Depends(require_api_key)])
def ai_ping() -> dict[str, str]:
    """Quick smoke-test: ask the AI what 2+2 is."""
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


@app.post("/api/board/{username}/chat", dependencies=[Depends(require_api_key)])
def chat_with_board(username: str, body: ChatRequest) -> StreamingResponse:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="Username is required")

    if not user_exists(normalized_username):
        raise HTTPException(status_code=404, detail="User not found")

    # Use the board sent by the client so the AI sees exactly what the user sees.
    # Avoids drift from unsynced drag-and-drop or races with in-flight PUTs.
    board = body.board.model_dump()
    if not is_valid_board_payload(board):
        raise HTTPException(status_code=400, detail="Invalid board payload")

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
