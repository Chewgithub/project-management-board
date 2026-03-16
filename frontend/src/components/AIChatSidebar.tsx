"use client";

import { useRef, useState, useEffect } from "react";
import { streamChat, type ChatEvent } from "@/lib/api";
import { isBoardData, type BoardData } from "@/lib/kanban";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type AIChatSidebarProps = {
  username: string;
  onBoardChange: (board: BoardData) => void;
};

export const AIChatSidebar = ({
  username,
  onBoardChange,
}: AIChatSidebarProps) => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || streaming) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setStreaming(true);

    // Placeholder for streaming assistant message
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      let assistantContent = "";

      for await (const event of streamChat(username, text)) {
        const e = event as ChatEvent;
        if (e.type === "token") {
          assistantContent += e.content;
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              role: "assistant",
              content: assistantContent,
            };
            return updated;
          });
        } else if (e.type === "board_update") {
          if (!isBoardData(e.board)) {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                role: "assistant",
                content: "AI returned an invalid board update. Please try again.",
              };
              return updated;
            });
            continue;
          }
          onBoardChange(e.board);
        } else if (e.type === "error") {
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              role: "assistant",
              content: e.message,
            };
            return updated;
          });
        }
      }
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : "Something went wrong. Please try again.";
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: message,
        };
        return updated;
      });
    } finally {
      setStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  return (
    <>
      {/* Toggle button */}
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Close AI chat" : "Open AI chat"}
        className="fixed bottom-6 right-6 z-50 inline-flex items-center gap-2 rounded-full bg-[var(--secondary-purple)] px-4 py-3 text-white shadow-lg hover:brightness-110"
      >
        {open ? (
          <svg width="16" height="16" viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <line x1="2" y1="2" x2="16" y2="16" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
            <line x1="16" y1="2" x2="2" y2="16" stroke="white" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path
              d="M18 13a2 2 0 0 1-2 2H6l-4 4V4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9Z"
              stroke="white"
              strokeWidth="1.8"
              strokeLinejoin="round"
              fill="none"
            />
          </svg>
        )}
        <span className="text-[11px] font-semibold uppercase tracking-[0.18em]">
          {open ? "Close AI" : "AI Chat"}
        </span>
      </button>

      {/* Sidebar panel */}
      {open && (
        <div className="fixed bottom-24 right-3 z-40 flex w-[min(22rem,calc(100vw-1.5rem))] flex-col overflow-hidden rounded-2xl border border-[var(--stroke)] bg-white shadow-xl sm:right-6"
          style={{ maxHeight: "calc(100vh - 120px)" }}
        >
          {/* Header */}
          <div className="flex items-center gap-3 border-b border-[var(--stroke)] bg-[var(--surface)] px-4 py-3">
            <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--navy-dark)]">
              AI Assistant
            </p>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0" style={{ maxHeight: "60vh" }}>
            {messages.length === 0 && (
              <p className="text-xs text-[var(--gray-text)] leading-5">
                Ask me to create, move, or edit cards on your board.
              </p>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`text-sm leading-6 rounded-xl px-3 py-2 ${
                  msg.role === "user"
                    ? "bg-[var(--primary-blue)] text-white self-end ml-6"
                    : "bg-[var(--surface)] border border-[var(--stroke)] text-[var(--navy-dark)] mr-6"
                }`}
                style={{ whiteSpace: "pre-wrap" }}
              >
                {msg.content}
                {msg.role === "assistant" && streaming && i === messages.length - 1 && (
                  <span className="inline-block w-1.5 h-3.5 ml-0.5 bg-[var(--primary-blue)] animate-pulse rounded-sm align-middle" />
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="border-t border-[var(--stroke)] p-3 flex gap-2">
            <textarea
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask the AI..."
              disabled={streaming}
              className="flex-1 resize-none rounded-lg border border-[var(--stroke)] bg-[var(--surface)] px-3 py-2 text-xs text-[var(--navy-dark)] placeholder:text-[var(--gray-text)] focus:outline-none focus:ring-1 focus:ring-[var(--primary-blue)] disabled:opacity-50"
            />
            <button
              onClick={() => void handleSend()}
              disabled={streaming || !input.trim()}
              className="self-end rounded-lg bg-[var(--secondary-purple)] px-3 py-2 text-xs font-semibold text-white hover:brightness-110 disabled:opacity-40"
            >
              Send
            </button>
          </div>
        </div>
      )}
    </>
  );
};
