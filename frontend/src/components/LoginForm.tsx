"use client";

import { useState } from "react";

const USER = "user";
const PASS = "password";

export function LoginForm({ onLogin }: { onLogin: (username: string) => void | Promise<void> }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (username === USER && password === PASS) {
      setError("");
      void onLogin(username);
    } else {
      setError("Invalid credentials");
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="max-w-xs mx-auto mt-16 p-6 rounded-2xl border border-[var(--stroke)] bg-white shadow-[var(--shadow)] flex flex-col gap-4"
      data-testid="login-form"
    >
      <h2 className="text-xl font-semibold text-[var(--navy-dark)]">Sign In</h2>
      <input
        type="text"
        placeholder="Username"
        aria-label="Username"
        value={username}
        onChange={e => setUsername(e.target.value)}
        className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm font-medium text-[var(--navy-dark)]"
        autoFocus
      />
      <input
        type="password"
        placeholder="Password"
        aria-label="Password"
        value={password}
        onChange={e => setPassword(e.target.value)}
        className="rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm font-medium text-[var(--navy-dark)]"
      />
      {error && <div className="text-red-600 text-sm">{error}</div>}
      <button type="submit" className="rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110">
        Login
      </button>
    </form>
  );
}
