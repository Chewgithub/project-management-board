"use client";

import { useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import { LoginForm } from "@/components/LoginForm";
import { AIChatSidebar } from "@/components/AIChatSidebar";
import { getFallbackBoard, loadBoard, saveBoard } from "@/lib/api";
import type { BoardData } from "@/lib/kanban";

export default function Home() {
  const [loggedInUser, setLoggedInUser] = useState<string | null>(null);
  const [board, setBoard] = useState<BoardData | null>(null);
  const [isLoadingBoard, setIsLoadingBoard] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  const handleLogin = async (username: string) => {
    setLoggedInUser(username);
    setBoard(null);
    setIsLoadingBoard(true);
    setSyncMessage(null);

    try {
      const persistedBoard = await loadBoard(username);
      setBoard(persistedBoard);
    } catch {
      // Keep working locally when backend isn't reachable during frontend-only runs.
      setBoard(getFallbackBoard());
      setSyncMessage("Backend unavailable. Using local board data.");
    } finally {
      setIsLoadingBoard(false);
    }
  };

  const handleLogout = () => {
    setLoggedInUser(null);
    setBoard(null);
    setIsLoadingBoard(false);
    setSyncMessage(null);
  };

  const handleBoardChange = (nextBoard: BoardData) => {
    setBoard(nextBoard);

    if (!loggedInUser) {
      return;
    }

    void saveBoard(loggedInUser, nextBoard)
      .then(() => setSyncMessage(null))
      .catch(() => setSyncMessage("Could not sync changes to backend."));
  };

  if (!loggedInUser) {
    return <LoginForm onLogin={handleLogin} />;
  }

  return (
    <>
      <button
        onClick={handleLogout}
        className="fixed top-4 right-4 rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white shadow-md hover:brightness-110 z-50"
      >
        Logout
      </button>
      {syncMessage ? (
        <div
          role="status"
          className="fixed left-4 top-4 z-50 rounded-lg border border-[var(--stroke)] bg-white px-3 py-2 text-xs font-semibold text-[var(--gray-text)] shadow"
        >
          {syncMessage}
        </div>
      ) : null}

      {isLoadingBoard || !board ? (
        <main className="mx-auto flex min-h-screen max-w-[1500px] items-center justify-center px-6 py-12">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
            Loading board...
          </p>
        </main>
      ) : (
        <>
          <KanbanBoard board={board} onBoardChange={handleBoardChange} />
          <AIChatSidebar
            username={loggedInUser}
            onBoardChange={handleBoardChange}
          />
        </>
      )}
    </>
  );
}
