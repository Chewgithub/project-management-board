from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.db import DEFAULT_BOARD
from backend.app.main import app


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "pm-test.db"
    monkeypatch.setenv("PM_DB_PATH", str(path))
    return path


@pytest.fixture
def client(db_path: Path) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_database_is_created_if_missing(client: TestClient, db_path: Path) -> None:
    assert db_path.exists()


def test_ping(client: TestClient) -> None:
    response = client.get("/api/ping")
    assert response.status_code == 200
    assert response.json() == {"message": "pong"}


def test_get_board_creates_default_board_for_user(client: TestClient) -> None:
    response = client.get("/api/board/user")
    assert response.status_code == 200

    body = response.json()
    assert body["username"] == "user"
    assert body["board"] == DEFAULT_BOARD


def test_put_board_updates_persisted_board(client: TestClient) -> None:
    updated_board = {
        "columns": [{"id": "col-1", "title": "Todo", "cardIds": ["card-99"]}],
        "cards": {
            "card-99": {
                "id": "card-99",
                "title": "Write API tests",
                "details": "Covered by backend tests.",
            }
        },
    }

    put_response = client.put("/api/board/user", json=updated_board)
    assert put_response.status_code == 200
    assert put_response.json()["board"] == updated_board

    get_response = client.get("/api/board/user")
    assert get_response.status_code == 200
    assert get_response.json()["board"] == updated_board


def test_boards_are_isolated_per_user(client: TestClient) -> None:
    board_a = {
        "columns": [{"id": "col-a", "title": "A", "cardIds": ["a-1"]}],
        "cards": {
            "a-1": {
                "id": "a-1",
                "title": "User A card",
                "details": "Only for user A.",
            }
        },
    }
    board_b = {
        "columns": [{"id": "col-b", "title": "B", "cardIds": ["b-1"]}],
        "cards": {
            "b-1": {
                "id": "b-1",
                "title": "User B card",
                "details": "Only for user B.",
            }
        },
    }

    assert client.put("/api/board/alice", json=board_a).status_code == 200
    assert client.put("/api/board/bob", json=board_b).status_code == 200

    alice_board = client.get("/api/board/alice").json()["board"]
    bob_board = client.get("/api/board/bob").json()["board"]

    assert alice_board == board_a
    assert bob_board == board_b


def test_delete_board_removes_default_board(client: TestClient) -> None:
    assert client.get("/api/board/user").status_code == 200

    delete_response = client.delete("/api/board/user")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"username": "user", "deleted": True}

    recreated_board = client.get("/api/board/user").json()["board"]
    assert recreated_board == DEFAULT_BOARD
