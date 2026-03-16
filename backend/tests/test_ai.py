"""Tests for AI endpoints — OpenAI calls are mocked."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from openai import OpenAIError

from backend.app.db import DEFAULT_BOARD
from backend.app.main import app


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "pm-test-ai.db"
    monkeypatch.setenv("PM_DB_PATH", str(path))
    return path


@pytest.fixture
def client(db_path: Path) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _make_completion(content: str) -> MagicMock:
    """Build a minimal OpenAI ChatCompletion mock."""
    msg = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=msg)
    return SimpleNamespace(choices=[choice])


def _make_chunk(
    content: str | None = None,
    tool_id: str | None = None,
    tool_name: str | None = None,
    tool_args: str | None = None,
    tool_index: int | None = None,
) -> MagicMock:
    """Build a minimal streaming chunk mock."""
    tool_calls = None
    if tool_id or tool_name or tool_args:
        fn = SimpleNamespace(name=tool_name, arguments=tool_args or "")
        tc = SimpleNamespace(id=tool_id, function=fn, index=tool_index)
        tool_calls = [tc]
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(delta=delta)
    return SimpleNamespace(choices=[choice])


def test_ai_ping(client: TestClient) -> None:
    mock_response = _make_completion("4")
    with patch("backend.app.main.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        response = client.get("/api/ai/ping")

    assert response.status_code == 200
    assert response.json() == {"answer": "4"}


def test_ai_ping_returns_503_when_ai_is_unconfigured(client: TestClient) -> None:
    with patch("backend.app.main.get_client", side_effect=RuntimeError("OPENAI_API_KEY is not set")):
        response = client.get("/api/ai/ping")

    assert response.status_code == 503
    assert response.json() == {"detail": "OPENAI_API_KEY is not set"}


def test_ai_ping_returns_502_when_openai_request_fails(client: TestClient) -> None:
    with patch("backend.app.main.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = OpenAIError("invalid model ID")
        mock_get_client.return_value = mock_client

        response = client.get("/api/ai/ping")

    assert response.status_code == 502
    assert "OpenAI request failed" in response.json()["detail"]


def test_chat_streams_text_tokens(client: TestClient) -> None:
    chunks = [
        _make_chunk(content="Hello"),
        _make_chunk(content=" world"),
    ]
    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter(chunks)
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "hi"}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    token_events = [e for e in events if e["type"] == "token"]
    assert "".join(e["content"] for e in token_events) == "Hello world"

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1


def test_chat_streams_board_update(client: TestClient) -> None:
    new_board = {
        "columns": [{"id": "col-backlog", "title": "Backlog", "cardIds": ["card-new"]}],
        "cards": {"card-new": {"id": "card-new", "title": "New task", "details": "Details."}},
    }
    chunks = [
        _make_chunk(content="Done!"),
        _make_chunk(
            tool_id="call-1",
            tool_name="update_board",
            tool_index=0,
            tool_args=json.dumps(new_board),
        ),
    ]
    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter(chunks)
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "add a card"}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    board_events = [e for e in events if e["type"] == "board_update"]
    assert len(board_events) == 1
    assert board_events[0]["board"] == new_board


def test_chat_handles_fragmented_tool_args_and_persists_board(client: TestClient) -> None:
    new_board = {
        "columns": [{"id": "col-backlog", "title": "Backlog", "cardIds": ["card-xyz"]}],
        "cards": {
            "card-xyz": {"id": "card-xyz", "title": "AI task", "details": "Created by AI."}
        },
    }
    args = json.dumps(new_board)
    split = len(args) // 2

    chunks = [
        _make_chunk(content="Applying update"),
        _make_chunk(
            tool_id="call-1",
            tool_name="update_board",
            tool_index=0,
            tool_args=args[:split],
        ),
        _make_chunk(tool_name="update_board", tool_index=0, tool_args=args[split:]),
    ]

    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter(chunks)
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "add AI task"}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    board_events = [e for e in events if e["type"] == "board_update"]
    assert len(board_events) == 1
    assert board_events[0]["board"] == new_board

    # Ensure backend persisted the AI-generated board update.
    persisted = client.get("/api/board/user")
    assert persisted.status_code == 200
    assert persisted.json()["board"] == new_board


def test_chat_rejects_invalid_board_update_payload(client: TestClient) -> None:
    invalid_board = {
        "columns": [{"id": "col-backlog", "title": "Backlog", "cardIds": ["card-missing"]}],
        # Missing cards map on purpose.
    }

    chunks = [
        _make_chunk(content="I will move the card."),
        _make_chunk(
            tool_id="call-1",
            tool_name="update_board",
            tool_index=0,
            tool_args=json.dumps(invalid_board),
        ),
    ]

    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter(chunks)
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "move a card"}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    error_events = [e for e in events if e["type"] == "error"]
    board_events = [e for e in events if e["type"] == "board_update"]
    assert len(error_events) == 1
    assert "invalid board update" in error_events[0]["message"].lower()
    assert len(board_events) == 0

    # Ensure invalid board update was not persisted.
    persisted = client.get("/api/board/user")
    assert persisted.status_code == 200
    assert persisted.json()["board"] == DEFAULT_BOARD


def test_chat_returns_503_when_ai_is_unconfigured(client: TestClient) -> None:
    with patch("backend.app.main.get_client", side_effect=RuntimeError("OPENAI_API_KEY is not set")):
        response = client.post("/api/board/user/chat", json={"message": "hi"})

    assert response.status_code == 503
    assert response.json() == {"detail": "OPENAI_API_KEY is not set"}


def test_chat_streams_error_event_when_openai_request_fails(client: TestClient) -> None:
    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = OpenAIError("invalid model ID")
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "hi"}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    error_events = [e for e in events if e["type"] == "error"]
    done_events = [e for e in events if e["type"] == "done"]
    assert len(error_events) == 1
    assert "OpenAI request failed" in error_events[0]["message"]
    assert len(done_events) == 1
