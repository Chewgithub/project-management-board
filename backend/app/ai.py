from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

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
Never omit or drop existing cards or columns.

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


def is_valid_board_payload(board: Any) -> bool:
    """Validate board payload shape and card references."""
    if not isinstance(board, dict):
        return False

    columns = board.get("columns")
    cards = board.get("cards")

    if not isinstance(columns, list) or not isinstance(cards, dict):
        return False

    for column in columns:
        if not isinstance(column, dict):
            return False
        if not isinstance(column.get("id"), str):
            return False
        if not isinstance(column.get("title"), str):
            return False

        card_ids = column.get("cardIds")
        if not isinstance(card_ids, list):
            return False
        if any(not isinstance(card_id, str) for card_id in card_ids):
            return False

    for card_id, card in cards.items():
        if not isinstance(card_id, str) or not isinstance(card, dict):
            return False
        if not isinstance(card.get("id"), str):
            return False
        if not isinstance(card.get("title"), str):
            return False
        if not isinstance(card.get("details"), str):
            return False

    # Keep board references consistent so UI rendering cannot break.
    for column in columns:
        for card_id in column["cardIds"]:
            if card_id not in cards:
                return False

    return True


def stream_chat(
    board: dict[str, Any],
    user_message: str,
    on_board_update: Callable[[dict[str, Any]], None] | None = None,
) -> Iterator[str]:
    """Stream SSE-formatted lines for the AI chat response.

    Each yielded string is a complete ``data: ...\\n\\n`` SSE line.
    Events:
      {"type": "token", "content": "<text>"}
      {"type": "board_update", "board": {...}}
            {"type": "error", "message": "<error text>"}
            {"type": "done"}

        If provided, ``on_board_update`` is called once with the updated board before
        the ``board_update`` event is emitted.
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

            # Stream text tokens
            if delta.content:
                yield _sse({"type": "token", "content": delta.content})

            # Accumulate tool call arguments
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

    # If update_board was called, parse and emit updated board.
    for index in sorted(tool_args_by_index.keys()):
        if tool_name_by_index.get(index) != "update_board":
            continue

        tool_args_buf = "".join(tool_args_by_index[index]).strip()
        if not tool_args_buf:
            continue

        try:
            updated_board = json.loads(tool_args_buf)

            # LLMs often omit unchanged cards or columns. Repair both so validation passes.
            if not isinstance(updated_board.get("cards"), dict):
                updated_board["cards"] = {}
            for card_id, card in board["cards"].items():
                updated_board["cards"].setdefault(card_id, card)

            if isinstance(updated_board.get("columns"), list):
                existing_col_ids = {col.get("id") for col in updated_board["columns"] if isinstance(col, dict)}
                for col in board["columns"]:
                    if col["id"] not in existing_col_ids:
                        updated_board["columns"].append(col)

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
        except json.JSONDecodeError:
            pass
        break

    yield _sse({"type": "done"})
