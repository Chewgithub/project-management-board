"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import { LoginForm } from "@/components/LoginForm";
import { AIChatSidebar } from "@/components/AIChatSidebar";
import { getFallbackBoard, loadBoard, saveBoard } from "@/lib/api";
import type { BoardData } from "@/lib/kanban";

const SAVE_DEBOUNCE_MS = 300;

export default function Home() {
  const [loggedInUser, setLoggedInUser] = useState<string | null>(null);
  const [board, setBoard] = useState<BoardData | null>(null);
  const [isLoadingBoard, setIsLoadingBoard] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [isFallback, setIsFallback] = useState(false);

  const pendingBoardRef = useRef<BoardData | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveChainRef = useRef<Promise<void>>(Promise.resolve());

  const cancelPendingSave = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    pendingBoardRef.current = null;
  }, []);

  const flushSave = useCallback((username: string) => {
    const next = pendingBoardRef.current;
    pendingBoardRef.current = null;
    if (!next) return;

    // Serialize PUTs so an older snapshot can never overwrite a newer one.
    saveChainRef.current = saveChainRef.current
      .then(() => saveBoard(username, next))
      .then(() => {
        setSyncMessage(null);
      })
      .catch(() => {
        setSyncMessage("Could not sync changes to backend.");
      });
  }, []);

  const scheduleSave = useCallback(
    (username: string, nextBoard: BoardData) => {
      pendingBoardRef.current = nextBoard;
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
      saveTimerRef.current = setTimeout(() => {
        saveTimerRef.current = null;
        flushSave(username);
      }, SAVE_DEBOUNCE_MS);
    },
    [flushSave]
  );

  useEffect(() => {
    return () => cancelPendingSave();
  }, [cancelPendingSave]);

  const handleLogin = async (username: string) => {
    setLoggedInUser(username);
    setBoard(null);
    setIsLoadingBoard(true);
    setSyncMessage(null);
    setIsFallback(false);

    try {
      const persistedBoard = await loadBoard(username);
      setBoard(persistedBoard);
    } catch {
      setBoard(getFallbackBoard());
      setIsFallback(true);
      setSyncMessage("Backend unavailable. Using local board data.");
    } finally {
      setIsLoadingBoard(false);
    }
  };

  const handleRetryConnection = async () => {
    if (!loggedInUser) return;
    setSyncMessage("Reconnecting...");
    try {
      const persistedBoard = await loadBoard(loggedInUser);
      setBoard(persistedBoard);
      setIsFallback(false);
      setSyncMessage(null);
    } catch {
      setSyncMessage("Backend unavailable. Using local board data.");
    }
  };

  const handleLogout = () => {
    cancelPendingSave();
    setLoggedInUser(null);
    setBoard(null);
    setIsLoadingBoard(false);
    setSyncMessage(null);
    setIsFallback(false);
  };

  const handleBoardChange = (nextBoard: BoardData) => {
    setBoard(nextBoard);
    if (!loggedInUser || isFallback) {
      return;
    }
    scheduleSave(loggedInUser, nextBoard);
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
          className="fixed left-4 top-4 z-50 flex items-center gap-3 rounded-lg border border-[var(--stroke)] bg-white px-3 py-2 text-xs font-semibold text-[var(--gray-text)] shadow"
        >
          <span>{syncMessage}</span>
          {isFallback ? (
            <button
              type="button"
              onClick={() => void handleRetryConnection()}
              className="rounded-full bg-[var(--primary-blue)] px-3 py-1 text-[10px] font-semibold uppercase tracking-wide text-white hover:brightness-110"
            >
              Retry
            </button>
          ) : null}
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
          {isFallback ? null : (
            <AIChatSidebar
              username={loggedInUser}
              board={board}
              onBoardChange={handleBoardChange}
            />
          )}
        </>
      )}
    </>
  );
}
