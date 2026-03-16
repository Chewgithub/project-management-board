import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, vi } from "vitest";
import { initialData } from "@/lib/kanban";
import Home from "./page";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Home auth flow", () => {
  it("requires login before showing the board", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /kanban studio/i })
    ).not.toBeInTheDocument();
  });

  it("logs in with valid credentials and supports logout", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "user", board: initialData }),
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<Home />);

    await userEvent.type(screen.getByPlaceholderText("Username"), "user");
    await userEvent.type(screen.getByPlaceholderText("Password"), "password");
    await userEvent.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /logout/i })).toBeInTheDocument()
    );
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /kanban studio/i })).toBeInTheDocument()
    );

    expect(fetchMock).toHaveBeenCalledWith("/api/board/user", {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    await userEvent.click(screen.getByRole("button", { name: /logout/i }));

    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
  });

  it("persists board updates to backend after login", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ username: "user", board: initialData }),
      })
      .mockResolvedValue({
        ok: true,
        json: async () => ({ username: "user", board: initialData }),
      });
    vi.stubGlobal("fetch", fetchMock);

    render(<Home />);

    await userEvent.type(screen.getByPlaceholderText("Username"), "user");
    await userEvent.type(screen.getByPlaceholderText("Password"), "password");
    await userEvent.click(screen.getByRole("button", { name: /login/i }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /kanban studio/i })).toBeInTheDocument()
    );

    const firstColumn = screen.getAllByTestId(/column-/i)[0];
    const titleInput = within(firstColumn).getByLabelText("Column title");
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "Backlog Updated");

    await waitFor(() => {
      const putCall = fetchMock.mock.calls.find(
        (call) => call[0] === "/api/board/user" && (call[1] as { method?: string })?.method === "PUT"
      );
      expect(putCall).toBeDefined();
    });
  });

  it("stays on login for invalid credentials", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    render(<Home />);

    await userEvent.type(screen.getByPlaceholderText("Username"), "wrong");
    await userEvent.type(screen.getByPlaceholderText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /login/i }));

    expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /logout/i })
    ).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
