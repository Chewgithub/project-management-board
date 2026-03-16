import { describe, expect, it, vi, afterEach } from "vitest";
import { initialData } from "@/lib/kanban";
import { getFallbackBoard, loadBoard, saveBoard, streamChat } from "@/lib/api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("api helpers", () => {
  it("loads a user board from backend API", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ username: "user", board: initialData }),
    });

    vi.stubGlobal("fetch", fetchMock);

    const result = await loadBoard("user");

    expect(fetchMock).toHaveBeenCalledWith("/api/board/user", {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    expect(result).toEqual(initialData);
  });

  it("throws when backend returns invalid board payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ username: "user", board: { columns: [] } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadBoard("user")).rejects.toThrow(/invalid board data/i);
  });

  it("saves a user board via backend API", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ username: "user", board: initialData }),
    });

    vi.stubGlobal("fetch", fetchMock);

    const result = await saveBoard("user", initialData);

    expect(fetchMock).toHaveBeenCalledWith("/api/board/user", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(initialData),
    });
    expect(result).toEqual(initialData);
  });

  it("returns a deep copy for fallback board", () => {
    const fallback = getFallbackBoard();

    expect(fallback).toEqual(initialData);
    expect(fallback).not.toBe(initialData);
    expect(fallback.columns).not.toBe(initialData.columns);
    expect(fallback.cards).not.toBe(initialData.cards);
  });

  it("parses streamed chat events including trailing final line", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode('data: {"type":"token","content":"Hello"}\n')
        );
        // No trailing newline to ensure final buffered event is handled.
        controller.enqueue(encoder.encode('data: {"type":"done"}'));
        controller.close();
      },
    });

    const fetchMock = vi.fn().mockResolvedValue({ ok: true, body });
    vi.stubGlobal("fetch", fetchMock);

    const events = [];
    for await (const event of streamChat("user", "hi")) {
      events.push(event);
    }

    expect(fetchMock).toHaveBeenCalledWith("/api/board/user/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "hi" }),
    });
    expect(events).toEqual([
      { type: "token", content: "Hello" },
      { type: "done" },
    ]);
  });

  it("throws backend detail when chat request fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: "OpenAI request failed: invalid model ID" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const iterator = streamChat("user", "hi");
    await expect(iterator.next()).rejects.toThrow(/invalid model ID/i);
  });
});
