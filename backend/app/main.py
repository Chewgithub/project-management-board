from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.app.db import delete_board_for_user, get_board_for_user, init_db, update_board_for_user


class BoardPayload(BaseModel):
    columns: list[dict[str, Any]]
    cards: dict[str, dict[str, Any]]



@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

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

    board = update_board_for_user(normalized_username, payload.model_dump())
    return {"username": normalized_username, "board": board}


@app.delete("/api/board/{username}")
def delete_user_board(username: str) -> dict[str, Any]:
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="Username is required")

    deleted = delete_board_for_user(normalized_username)
    return {"username": normalized_username, "deleted": deleted}
