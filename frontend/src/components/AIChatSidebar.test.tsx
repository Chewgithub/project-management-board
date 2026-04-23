import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { AIChatSidebar } from "@/components/AIChatSidebar";
import { initialData, type BoardData } from "@/lib/kanban";

const streamChatMock = vi.fn();

vi.mock("@/lib/api", () => ({
  streamChat: (...args: unknown[]) => streamChatMock(...args),
}));

afterEach(() => {
  vi.clearAllMocks();
});

beforeAll(() => {
  Object.defineProperty(Element.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
});

const asAsyncGenerator = async function* (events: unknown[]) {
  for (const event of events) {
    yield event;
  }
};

describe("AIChatSidebar", () => {
  it("streams assistant tokens into the chat panel", async () => {
    streamChatMock.mockImplementation(() =>
      asAsyncGenerator([
        { type: "token", content: "Hello" },
        { type: "token", content: " there" },
        { type: "done" },
      ])
    );

    const onBoardChange = vi.fn();
    render(
      <AIChatSidebar username="user" board={initialData} onBoardChange={onBoardChange} />
    );

    await userEvent.click(screen.getByRole("button", { name: /open ai chat/i }));
    await userEvent.type(screen.getByPlaceholderText(/ask the ai/i), "help me");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(streamChatMock).toHaveBeenCalledWith("user", "help me", initialData);
    });
    await waitFor(() => {
      expect(screen.getByText("Hello there")).toBeInTheDocument();
    });
  });

  it("emits board updates from streamed AI events", async () => {
    const updatedBoard: BoardData = {
      columns: [{ id: "col-backlog", title: "Backlog", cardIds: ["card-1"] }],
      cards: {
        "card-1": { id: "card-1", title: "New card", details: "Created by AI" },
      },
    };

    streamChatMock.mockImplementation(() =>
      asAsyncGenerator([
        { type: "board_update", board: updatedBoard },
        { type: "done" },
      ])
    );

    const onBoardChange = vi.fn();
    render(
      <AIChatSidebar username="user" board={initialData} onBoardChange={onBoardChange} />
    );

    await userEvent.click(screen.getByRole("button", { name: /open ai chat/i }));
    await userEvent.type(screen.getByPlaceholderText(/ask the ai/i), "add card");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(onBoardChange).toHaveBeenCalledWith(updatedBoard);
    });
  });

  it("shows streamed error messages from backend", async () => {
    streamChatMock.mockImplementation(() =>
      asAsyncGenerator([
        { type: "error", message: "OpenAI request failed: invalid model ID" },
        { type: "done" },
      ])
    );

    const onBoardChange = vi.fn();
    render(
      <AIChatSidebar username="user" board={initialData} onBoardChange={onBoardChange} />
    );

    await userEvent.click(screen.getByRole("button", { name: /open ai chat/i }));
    await userEvent.type(screen.getByPlaceholderText(/ask the ai/i), "help");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText(/OpenAI request failed/i)).toBeInTheDocument();
    });
  });

  it("ignores invalid board_update payloads and shows error text", async () => {
    streamChatMock.mockImplementation(() =>
      asAsyncGenerator([
        { type: "board_update", board: { columns: [] } },
        { type: "done" },
      ])
    );

    const onBoardChange = vi.fn();
    render(
      <AIChatSidebar username="user" board={initialData} onBoardChange={onBoardChange} />
    );

    await userEvent.click(screen.getByRole("button", { name: /open ai chat/i }));
    await userEvent.type(screen.getByPlaceholderText(/ask the ai/i), "move a card");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid board update/i)).toBeInTheDocument();
    });
    expect(onBoardChange).not.toHaveBeenCalled();
  });
});
