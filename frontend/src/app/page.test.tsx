import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Home from "./page";

describe("Home auth flow", () => {
  it("requires login before showing the board", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: /kanban studio/i })
    ).not.toBeInTheDocument();
  });

  it("logs in with valid credentials and supports logout", async () => {
    render(<Home />);

    await userEvent.type(screen.getByPlaceholderText("Username"), "user");
    await userEvent.type(screen.getByPlaceholderText("Password"), "password");
    await userEvent.click(screen.getByRole("button", { name: /login/i }));

    expect(screen.getByRole("button", { name: /logout/i })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /kanban studio/i })
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /logout/i }));

    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
  });

  it("stays on login for invalid credentials", async () => {
    render(<Home />);

    await userEvent.type(screen.getByPlaceholderText("Username"), "wrong");
    await userEvent.type(screen.getByPlaceholderText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /login/i }));

    expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /logout/i })
    ).not.toBeInTheDocument();
  });
});
