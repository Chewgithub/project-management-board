from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

from backend.app.db import is_valid_board_payload

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        _client = OpenAI(api_key=api_key)
    return _client


SYSTEM_PROMPT = """You are a helpful Kanban board assistant. \
The user's current board is provided below as JSON.

When the user asks you to create, move, edit, or delete cards, \
use the update_board tool to return the full updated board. \
Always explain what you did in plain text as well.

IMPORTANT: update_board requires the COMPLETE board. \
Always include every column and every card — even ones that were not changed. \
To delete a card, remove it from both its column's cardIds AND from the cards object. \
Never drop columns.

If no board change is needed, just reply in plain text."""

UPDATE_BOARD_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "update_board",
        "description": "Return the complete updated Kanban board after making requested changes.",
        "parameters": {
            "type": "object",
            "properties": {
                "columns": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "cardIds": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": ["id", "title", "cardIds"],
                    },
                },
                "cards": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "details": {"type": "string"},
                        },
                        "required": ["id", "title", "details"],
                    },
                },
            },
            "required": ["columns", "cards"],
        },
    },
}


def _repair_board_update(original: dict[str, Any], updated: dict[str, Any]) -> dict[str, Any]:
    """Restore omitted columns and cards while honoring genuine deletions.

    Cards that the AI removes from ALL cardIds are treated as deletions; cards
    that are still referenced but missing from the ``cards`` dict are restored
    from the original board. Columns are never deletable, so any column missing
    from the AI's response is restored.
    """
    if not isinstance(updated.get("columns"), list):
        updated["columns"] = list(original["columns"])
    else:
        existing_col_ids = {col.get("id") for col in updated["columns"] if isinstance(col, dict)}
        for col in original["columns"]:
            if col["id"] not in existing_col_ids:
                updated["columns"].append(col)

    if not isinstance(updated.get("cards"), dict):
        updated["cards"] = {}

    referenced: set[str] = set()
    for col in updated["columns"]:
        if isinstance(col, dict):
            for cid in col.get("cardIds", []):
                if isinstance(cid, str):
                    referenced.add(cid)

    for card_id in referenced:
        if card_id not in updated["cards"] and card_id in original["cards"]:
            updated["cards"][card_id] = original["cards"][card_id]

    return updated


def stream_chat(
    board: dict[str, Any],
    user_message: str,
    on_board_update: Callable[[dict[str, Any]], None] | None = None,
) -> Iterator[str]:
    """Stream SSE-formatted lines for the AI chat response.

    Each yielded string is a complete ``data: ...\\n\\n`` SSE line. Events:
        {"type": "token", "content": "<text>"}
        {"type": "board_update", "board": {...}}
        {"type": "error", "message": "<error text>"}
        {"type": "done"}

    If provided, ``on_board_update`` is called once with the updated board
    before the ``board_update`` event is emitted.
    """
    client = get_client()

    messages = [
        {
            "role": "system",
            "content": f"{SYSTEM_PROMPT}\n\nCurrent board:\n{json.dumps(board)}",
        },
        {"role": "user", "content": user_message},
    ]

    def _sse(event: dict[str, Any]) -> str:
        return f"data: {json.dumps(event)}\n\n"

    try:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=[UPDATE_BOARD_TOOL],
            tool_choice="auto",
            stream=True,
        )
    except OpenAIError as exc:
        yield _sse({"type": "error", "message": f"OpenAI request failed: {exc}"})
        yield _sse({"type": "done"})
        return

    # Tool call arguments arrive in fragments when streaming. Buffer by tool call index.
    tool_name_by_index: dict[int, str] = {}
    tool_args_by_index: dict[int, list[str]] = {}

    try:
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            if delta.content:
                yield _sse({"type": "token", "content": delta.content})

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    index = getattr(tc, "index", 0) or 0
                    fn = tc.function
                    if fn and fn.name:
                        tool_name_by_index[index] = fn.name
                    if fn and fn.arguments:
                        tool_args_by_index.setdefault(index, []).append(fn.arguments)
    except OpenAIError as exc:
        yield _sse({"type": "error", "message": f"OpenAI request failed: {exc}"})
        yield _sse({"type": "done"})
        return

    # Only `update_board` is registered as a tool today; if we ever add more,
    # this loop would need to route by tool name instead of picking the first.
    for index in sorted(tool_args_by_index.keys()):
        if tool_name_by_index.get(index) != "update_board":
            continue

        tool_args_buf = "".join(tool_args_by_index[index]).strip()
        if not tool_args_buf:
            continue

        try:
            updated_board = json.loads(tool_args_buf)
        except json.JSONDecodeError:
            yield _sse(
                {
                    "type": "error",
                    "message": "AI returned malformed board JSON. Please try again.",
                }
            )
            break

        updated_board = _repair_board_update(board, updated_board)

        if not is_valid_board_payload(updated_board):
            yield _sse(
                {
                    "type": "error",
                    "message": "AI returned an invalid board update. Please try again.",
                }
            )
            break

        if on_board_update is not None:
            on_board_update(updated_board)
        yield _sse({"type": "board_update", "board": updated_board})
        break

    yield _sse({"type": "done"})
