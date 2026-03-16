import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginForm } from "./LoginForm";
import { vi } from "vitest";

describe("LoginForm", () => {
  it("shows error for invalid credentials", async () => {
    render(<LoginForm onLogin={() => {}} />);
    await userEvent.type(screen.getByPlaceholderText("Username"), "wrong");
    await userEvent.type(screen.getByPlaceholderText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /login/i }));
    expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
  });

  it("calls onLogin for correct credentials", async () => {
    const onLogin = vi.fn();
    render(<LoginForm onLogin={onLogin} />);
    await userEvent.type(screen.getByPlaceholderText("Username"), "user");
    await userEvent.type(screen.getByPlaceholderText("Password"), "password");
    await userEvent.click(screen.getByRole("button", { name: /login/i }));
    expect(onLogin).toHaveBeenCalledWith("user");
  });
});
