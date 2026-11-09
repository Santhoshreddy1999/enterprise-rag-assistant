import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { AuthCredentials } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { AuthForm } from "../components/AuthForm";
import { Icon } from "../components/Icon";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { status, acceptUser } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const isRegister = mode === "register";

  if (status === "authenticated") {
    return <Navigate replace to="/" />;
  }

  async function submit(credentials: AuthCredentials) {
    setSubmitting(true);
    setError(null);
    try {
      const user = isRegister
        ? await api.register(credentials)
        : await api.login(credentials);
      acceptUser(user);
      navigate("/", { replace: true });
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Authentication failed. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-story" aria-labelledby="story-title">
        <Link className="brand brand--light" to="/">
          <span className="brand-mark">N</span>
          <span>Northstar</span>
        </Link>

        <div className="auth-story__content">
          <p className="eyebrow eyebrow--light">Grounded document intelligence</p>
          <h1 id="story-title">Answers you can trace back to the source.</h1>
          <p className="auth-story__lede">
            Bring your internal documents together, ask focused questions, and
            inspect the evidence behind every answer.
          </p>

          <div className="source-preview" aria-hidden="true">
            <div className="source-preview__top">
              <span className="source-preview__dot" />
              <span>benefits-handbook.pdf</span>
              <span>Page 4</span>
            </div>
            <blockquote>
              “Full-time employees receive twenty days of annual leave…”
            </blockquote>
            <div className="source-preview__answer">
              <Icon name="spark" />
              <span>Answer grounded in your library</span>
              <span className="source-pill">1 source</span>
            </div>
          </div>
        </div>

        <p className="auth-story__footer">
          Private by design · Sources attached to answers
        </p>
      </section>

      <section className="auth-panel" aria-labelledby="auth-title">
        <div className="auth-panel__inner">
          <Link className="brand brand--mobile" to="/">
            <span className="brand-mark">N</span>
            <span>Northstar</span>
          </Link>

          <p className="eyebrow">{isRegister ? "Get started" : "Welcome back"}</p>
          <h2 id="auth-title">
            {isRegister ? "Create your workspace" : "Sign in to your workspace"}
          </h2>
          <p className="auth-panel__intro">
            {isRegister
              ? "Start building a searchable, source-grounded document library."
              : "Continue working with your private document library."}
          </p>

          <AuthForm
            error={error}
            mode={mode}
            onSubmit={submit}
            submitting={submitting}
          />

          <p className="auth-switch">
            {isRegister ? "Already have an account?" : "New to Northstar?"}{" "}
            <Link to={isRegister ? "/login" : "/register"}>
              {isRegister ? "Sign in" : "Create an account"}
            </Link>
          </p>

          <p className="security-note">
            <span aria-hidden="true">●</span>
            Your session is protected by a secure, HttpOnly cookie.
          </p>
        </div>
      </section>
    </main>
  );
}
