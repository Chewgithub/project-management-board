"use client";

import { useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import { LoginForm } from "@/components/LoginForm";

export default function Home() {
  const [loggedIn, setLoggedIn] = useState(false);

  return loggedIn ? (
    <>
      <button
        onClick={() => setLoggedIn(false)}
        className="fixed top-4 right-4 rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white shadow-md hover:brightness-110 z-50"
      >
        Logout
      </button>
      <KanbanBoard />
    </>
  ) : (
    <LoginForm onLogin={() => setLoggedIn(true)} />
  );
}
