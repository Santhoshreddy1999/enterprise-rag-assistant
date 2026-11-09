import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AuthForm } from "./AuthForm";

describe("AuthForm", () => {
  it("submits normalized credentials without storing a token", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn(async () => undefined);
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");

    render(
      <AuthForm
        error={null}
        mode="login"
        onSubmit={onSubmit}
        submitting={false}
      />,
    );

    await user.type(screen.getByLabelText("Work email"), "  engineer@example.com  ");
    await user.type(
      screen.getByLabelText("Password"),
      "correct horse battery staple",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(onSubmit).toHaveBeenCalledWith({
      email: "engineer@example.com",
      password: "correct horse battery staple",
    });
    expect(storageSpy).not.toHaveBeenCalled();
  });

  it("exposes the registration password guidance and visibility control", async () => {
    const user = userEvent.setup();

    render(
      <AuthForm
        error={null}
        mode="register"
        onSubmit={vi.fn(async () => undefined)}
        submitting={false}
      />,
    );

    const password = screen.getByLabelText("Password");
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAccessibleDescription("Use a long, unique passphrase");

    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Hide password" })).toBeVisible();
  });

  it("moves focus to an authentication error", () => {
    render(
      <AuthForm
        error="Invalid authentication credentials"
        mode="login"
        onSubmit={vi.fn(async () => undefined)}
        submitting={false}
      />,
    );

    expect(screen.getByRole("alert")).toHaveFocus();
  });
});
