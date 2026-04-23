"""Tests for AI endpoints — OpenAI calls are mocked."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
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


@pytest.fixture
def seeded_user(client: TestClient) -> str:
    """Ensure the default 'user' exists in the DB before chat tests run."""
    response = client.get("/api/board/user")
    assert response.status_code == 200
    return "user"


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


def test_chat_streams_text_tokens(client: TestClient, seeded_user: str) -> None:
    chunks = [
        _make_chunk(content="Hello"),
        _make_chunk(content=" world"),
    ]
    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter(chunks)
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "hi", "board": DEFAULT_BOARD}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    token_events = [e for e in events if e["type"] == "token"]
    assert "".join(e["content"] for e in token_events) == "Hello world"

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1


def test_chat_streams_board_update(client: TestClient, seeded_user: str) -> None:
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

        with client.stream("POST", "/api/board/user/chat", json={"message": "add a card", "board": DEFAULT_BOARD}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    board_events = [e for e in events if e["type"] == "board_update"]
    assert len(board_events) == 1
    emitted = board_events[0]["board"]
    # AI's column with the new card is present.
    backlog = next(col for col in emitted["columns"] if col["id"] == "col-backlog")
    assert "card-new" in backlog["cardIds"]
    assert "card-new" in emitted["cards"]
    # Missing columns were repaired from the original board.
    emitted_col_ids = {col["id"] for col in emitted["columns"]}
    for col in DEFAULT_BOARD["columns"]:
        assert col["id"] in emitted_col_ids


def test_chat_handles_fragmented_tool_args_and_persists_board(client: TestClient, seeded_user: str) -> None:
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

        with client.stream("POST", "/api/board/user/chat", json={"message": "add AI task", "board": DEFAULT_BOARD}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    board_events = [e for e in events if e["type"] == "board_update"]
    assert len(board_events) == 1
    emitted = board_events[0]["board"]
    # AI's column with the new card is present.
    backlog = next(col for col in emitted["columns"] if col["id"] == "col-backlog")
    assert "card-xyz" in backlog["cardIds"]
    assert "card-xyz" in emitted["cards"]
    # Missing columns were repaired from the original board.
    emitted_col_ids = {col["id"] for col in emitted["columns"]}
    for col in DEFAULT_BOARD["columns"]:
        assert col["id"] in emitted_col_ids

    # Ensure backend persisted the repaired board update.
    persisted = client.get("/api/board/user")
    assert persisted.status_code == 200
    assert "card-xyz" in persisted.json()["board"]["cards"]


def test_chat_repairs_incomplete_cards_in_board_update(client: TestClient, seeded_user: str) -> None:
    """AI returns only the moved card in the cards dict; existing cards must be preserved."""
    # Board after move: card-1 is in In Progress, but AI only returns card-1 in cards dict.
    partial_board = {
        "columns": [
            {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-2"]},
            {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
            {"id": "col-progress", "title": "In Progress", "cardIds": ["card-4", "card-5", "card-1"]},
            {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
            {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8"]},
        ],
        "cards": {
            # AI only returned card-1 — omitted all the rest
            "card-1": {"id": "card-1", "title": "Align roadmap themes", "details": "Draft quarterly themes with impact statements and metrics."},
        },
    }

    chunks = [
        _make_chunk(content="Moved the card."),
        _make_chunk(tool_id="call-1", tool_name="update_board", tool_index=0, tool_args=json.dumps(partial_board)),
    ]

    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter(chunks)
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "move Align roadmap themes to In Progress", "board": DEFAULT_BOARD}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    error_events = [e for e in events if e["type"] == "error"]
    board_events = [e for e in events if e["type"] == "board_update"]

    assert len(error_events) == 0, f"Unexpected error: {error_events}"
    assert len(board_events) == 1

    # All original cards must be present in the emitted board.
    emitted_cards = board_events[0]["board"]["cards"]
    for card_id in DEFAULT_BOARD["cards"]:
        assert card_id in emitted_cards, f"Card {card_id} was dropped"


def test_chat_repairs_missing_cards_field_in_board_update(client: TestClient, seeded_user: str) -> None:
    """AI returns columns but omits the cards field entirely; repair must add all original cards."""
    board_no_cards = {
        "columns": [
            {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-2"]},
            {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
            {"id": "col-progress", "title": "In Progress", "cardIds": ["card-4", "card-5"]},
            {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
            {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8", "card-1"]},
        ],
        # cards field intentionally omitted
    }

    chunks = [
        _make_chunk(content="Moved it."),
        _make_chunk(tool_id="call-1", tool_name="update_board", tool_index=0, tool_args=json.dumps(board_no_cards)),
    ]

    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter(chunks)
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "move card to Done", "board": DEFAULT_BOARD}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    error_events = [e for e in events if e["type"] == "error"]
    board_events = [e for e in events if e["type"] == "board_update"]

    assert len(error_events) == 0, f"Unexpected error: {error_events}"
    assert len(board_events) == 1

    emitted_cards = board_events[0]["board"]["cards"]
    for card_id in DEFAULT_BOARD["cards"]:
        assert card_id in emitted_cards, f"Card {card_id} was dropped"


def test_chat_repairs_missing_columns_in_board_update(client: TestClient, seeded_user: str) -> None:
    """AI returns only the two affected columns; missing columns must be restored from the original."""
    partial_columns_board = {
        "columns": [
            {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-2"]},
            {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8", "card-1"]},
        ],
        "cards": {
            "card-1": {"id": "card-1", "title": "Align roadmap themes", "details": "Draft quarterly themes with impact statements and metrics."},
        },
    }

    chunks = [
        _make_chunk(content="Done."),
        _make_chunk(tool_id="call-1", tool_name="update_board", tool_index=0, tool_args=json.dumps(partial_columns_board)),
    ]

    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter(chunks)
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "move to Done", "board": DEFAULT_BOARD}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    error_events = [e for e in events if e["type"] == "error"]
    board_events = [e for e in events if e["type"] == "board_update"]

    assert len(error_events) == 0, f"Unexpected error: {error_events}"
    assert len(board_events) == 1

    emitted_col_ids = {col["id"] for col in board_events[0]["board"]["columns"]}
    for col in DEFAULT_BOARD["columns"]:
        assert col["id"] in emitted_col_ids, f"Column {col['id']} was dropped"


def test_chat_rejects_invalid_board_update_payload(client: TestClient, seeded_user: str) -> None:
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

        with client.stream("POST", "/api/board/user/chat", json={"message": "move a card", "board": DEFAULT_BOARD}) as resp:
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


def test_chat_returns_503_when_ai_is_unconfigured(client: TestClient, seeded_user: str) -> None:
    with patch("backend.app.main.get_client", side_effect=RuntimeError("OPENAI_API_KEY is not set")):
        response = client.post("/api/board/user/chat", json={"message": "hi", "board": DEFAULT_BOARD})

    assert response.status_code == 503
    assert response.json() == {"detail": "OPENAI_API_KEY is not set"}


def test_chat_streams_error_event_when_openai_request_fails(client: TestClient, seeded_user: str) -> None:
    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = OpenAIError("invalid model ID")
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "hi", "board": DEFAULT_BOARD}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    error_events = [e for e in events if e["type"] == "error"]
    done_events = [e for e in events if e["type"] == "done"]
    assert len(error_events) == 1
    assert "OpenAI request failed" in error_events[0]["message"]
    assert len(done_events) == 1


def test_chat_uses_client_submitted_board_not_db(client: TestClient, seeded_user: str) -> None:
    """The AI must see the board the client submits, not the DB's older copy.

    Regression for the drift bug: drag-and-drop PUTs are debounced; a chat
    request that arrives before the PUT must still see the live UI state.
    """
    client_board = {
        "columns": [
            {"id": "col-only", "title": "Only", "cardIds": ["card-only"]},
        ],
        "cards": {
            "card-only": {"id": "card-only", "title": "Client card", "details": "Only on client"},
        },
    }

    captured_messages: list[list[dict[str, Any]]] = []

    def capture_create(**kwargs: Any) -> Iterator[Any]:
        captured_messages.append(kwargs["messages"])
        return iter([_make_chunk(content="ok")])

    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = capture_create
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "hi", "board": client_board}) as resp:
            assert resp.status_code == 200
            resp.read()

    assert len(captured_messages) == 1
    system_content = captured_messages[0][0]["content"]
    assert "card-only" in system_content
    assert "Client card" in system_content
    # DEFAULT_BOARD's seed cards must not have leaked from DB.
    assert "Refine status language" not in system_content


def test_chat_allows_ai_to_delete_card(client: TestClient, seeded_user: str) -> None:
    """AI removing a card from both cardIds and the cards dict honors the delete."""
    board_after_delete = {
        "columns": [
            {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1", "card-2"]},
            {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
            # card-4 removed from In Progress AND from cards dict below.
            {"id": "col-progress", "title": "In Progress", "cardIds": ["card-5"]},
            {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
            {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8"]},
        ],
        "cards": {
            cid: card for cid, card in DEFAULT_BOARD["cards"].items() if cid != "card-4"
        },
    }

    chunks = [
        _make_chunk(content="Deleted."),
        _make_chunk(tool_id="call-1", tool_name="update_board", tool_index=0, tool_args=json.dumps(board_after_delete)),
    ]

    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter(chunks)
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "delete card-4", "board": DEFAULT_BOARD}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    board_events = [e for e in events if e["type"] == "board_update"]
    assert len(board_events) == 1
    emitted = board_events[0]["board"]
    assert "card-4" not in emitted["cards"], "Deleted card was incorrectly restored"
    in_progress = next(col for col in emitted["columns"] if col["id"] == "col-progress")
    assert "card-4" not in in_progress["cardIds"]


def test_chat_emits_error_event_on_malformed_tool_json(client: TestClient, seeded_user: str) -> None:
    chunks = [
        _make_chunk(content="here"),
        _make_chunk(tool_id="call-1", tool_name="update_board", tool_index=0, tool_args="{not valid json"),
    ]

    with patch("backend.app.ai.get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter(chunks)
        mock_get_client.return_value = mock_client

        with client.stream("POST", "/api/board/user/chat", json={"message": "x", "board": DEFAULT_BOARD}) as resp:
            assert resp.status_code == 200
            resp.read()
            raw = resp.text

    events = [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert "malformed" in error_events[0]["message"].lower()


def test_chat_returns_404_for_unknown_user(client: TestClient) -> None:
    response = client.post(
        "/api/board/ghost/chat",
        json={"message": "hi", "board": DEFAULT_BOARD},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


def test_api_key_required_when_env_set(client: TestClient, seeded_user: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PM_API_KEY", "secret-token")

    no_header = client.get("/api/board/user")
    assert no_header.status_code == 401

    bad_header = client.get("/api/board/user", headers={"X-API-Key": "wrong"})
    assert bad_header.status_code == 401

    good_header = client.get("/api/board/user", headers={"X-API-Key": "secret-token"})
    assert good_header.status_code == 200


def test_api_key_not_required_when_env_unset(client: TestClient, seeded_user: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PM_API_KEY", raising=False)

    response = client.get("/api/board/user")
    assert response.status_code == 200


def test_ping_remains_unauthenticated(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PM_API_KEY", "secret-token")
    response = client.get("/api/ping")
    assert response.status_code == 200
