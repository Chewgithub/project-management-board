import { initialData, isBoardData, type BoardData } from "@/lib/kanban";

type BoardApiResponse = {
  username: string;
  board: BoardData;
};

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");

const apiKey = process.env.NEXT_PUBLIC_PM_API_KEY;

const authHeaders = (): Record<string, string> =>
  apiKey ? { "X-API-Key": apiKey } : {};

const boardEndpoint = (username: string) =>
  `${apiBaseUrl}/api/board/${encodeURIComponent(username)}`;

const cloneBoard = (board: BoardData): BoardData => ({
  columns: board.columns.map((column) => ({ ...column, cardIds: [...column.cardIds] })),
  cards: Object.fromEntries(
    Object.entries(board.cards).map(([id, card]) => [id, { ...card }])
  ),
});

const parseBoardResponse = async (response: Response): Promise<BoardData> => {
  const data = (await response.json()) as BoardApiResponse;
  if (!isBoardData(data.board)) {
    throw new Error("Backend returned invalid board data");
  }
  return data.board;
};

export const getFallbackBoard = (): BoardData => cloneBoard(initialData);

export const loadBoard = async (username: string): Promise<BoardData> => {
  const response = await fetch(boardEndpoint(username), {
    method: "GET",
    headers: { Accept: "application/json", ...authHeaders() },
  });

  if (!response.ok) {
    throw new Error(`Failed to load board for ${username}`);
  }

  return parseBoardResponse(response);
};

export const saveBoard = async (
  username: string,
  board: BoardData
): Promise<BoardData> => {
  const response = await fetch(boardEndpoint(username), {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(board),
  });

  if (!response.ok) {
    throw new Error(`Failed to save board for ${username}`);
  }

  return parseBoardResponse(response);
};

export type ChatEvent =
  | { type: "token"; content: string }
  | { type: "board_update"; board: unknown }
  | { type: "error"; message: string }
  | { type: "done" };

export async function* streamChat(
  username: string,
  message: string,
  board: BoardData
): AsyncGenerator<ChatEvent> {
  const response = await fetch(
    `${apiBaseUrl}/api/board/${encodeURIComponent(username)}/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ message, board }),
    }
  );

  if (!response.ok) {
    let detail = "Chat request failed";
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // Keep fallback detail.
    }
    throw new Error(detail);
  }

  if (!response.body) {
    throw new Error("Chat response body is empty");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  const parseSseDataLine = (line: string): ChatEvent | null => {
    const trimmed = line.trim();
    if (!trimmed.startsWith("data: ")) {
      return null;
    }

    try {
      return JSON.parse(trimmed.slice(6)) as ChatEvent;
    } catch {
      return null;
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buf += decoder.decode(value, { stream: true });

    const lines = buf.split("\n");
    buf = lines.pop() ?? "";

    for (const line of lines) {
      const event = parseSseDataLine(line);
      if (event) {
        yield event;
      }
    }
  }

  // Flush decoder state and parse any trailing final line with no newline.
  buf += decoder.decode();
  const trailingEvent = parseSseDataLine(buf);
  if (trailingEvent) {
    yield trailingEvent;
  }
}
