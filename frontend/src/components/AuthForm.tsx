import { useEffect, useRef, useState, type FormEvent } from "react";
import type { AuthCredentials } from "../api/types";
import { Icon } from "./Icon";
import { Spinner } from "./Feedback";

interface AuthFormProps {
  mode: "login" | "register";
  error: string | null;
  submitting: boolean;
  onSubmit: (credentials: AuthCredentials) => Promise<void>;
}

export function AuthForm({
  mode,
  error,
  submitting,
  onSubmit,
}: AuthFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const isRegister = mode === "register";

  useEffect(() => {
    if (error) {
      errorRef.current?.focus();
    }
  }, [error]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) {
      return;
    }
    void onSubmit({ email: email.trim(), password });
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      {error ? (
        <div
          className="form-alert"
          ref={errorRef}
          role="alert"
          tabIndex={-1}
        >
          <span aria-hidden="true">!</span>
          <p>{error}</p>
        </div>
      ) : null}

      <div className="field">
        <label htmlFor="email">Work email</label>
        <input
          autoComplete="email"
          autoFocus
          id="email"
          inputMode="email"
          name="email"
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@company.com"
          required
          type="email"
          value={email}
        />
      </div>

      <div className="field">
        <div className="field__label-row">
          <label htmlFor="password">Password</label>
          {isRegister ? (
            <span id="password-hint">Use a long, unique passphrase</span>
          ) : null}
        </div>
        <div className="password-field">
          <input
            aria-describedby={isRegister ? "password-hint" : undefined}
            autoComplete={isRegister ? "new-password" : "current-password"}
            id="password"
            name="password"
            onChange={(event) => setPassword(event.target.value)}
            required
            type={showPassword ? "text" : "password"}
            value={password}
          />
          <button
            aria-label={showPassword ? "Hide password" : "Show password"}
            className="password-toggle"
            onClick={() => setShowPassword((value) => !value)}
            type="button"
          >
            {showPassword ? "Hide" : "Show"}
          </button>
        </div>
      </div>

      <button className="button button--primary button--wide" disabled={submitting}>
        {submitting ? (
          <>
            <Spinner label={isRegister ? "Creating account" : "Signing in"} />
            {isRegister ? "Creating account…" : "Signing in…"}
          </>
        ) : (
          <>
            {isRegister ? "Create workspace" : "Sign in"}
            <Icon name="arrow" />
          </>
        )}
      </button>
    </form>
  );
}
