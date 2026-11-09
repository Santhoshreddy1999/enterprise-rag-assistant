import type { ReactNode } from "react";
import { Icon } from "./Icon";

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span className="spinner-wrap" role="status">
      <span aria-hidden="true" className="spinner" />
      <span className="sr-only">{label}</span>
    </span>
  );
}

export function LoadingScreen() {
  return (
    <main className="centered-page">
      <div className="brand-mark brand-mark--large" aria-hidden="true">
        N
      </div>
      <div className="loading-copy" role="status">
        <span className="loading-bar" aria-hidden="true" />
        <span>Preparing your workspace…</span>
      </div>
    </main>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  compact = false,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
  compact?: boolean;
}) {
  return (
    <div
      className={compact ? "error-state error-state--compact" : "error-state"}
      role="alert"
    >
      <div className="error-state__icon" aria-hidden="true">
        !
      </div>
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
        {onRetry ? (
          <button className="text-button" onClick={onRetry} type="button">
            <Icon name="refresh" size={15} />
            Try again
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-state__icon" aria-hidden="true">
        {icon}
      </div>
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </div>
  );
}

export function StatusMessage({
  children,
  tone = "success",
  onDismiss,
}: {
  children: ReactNode;
  tone?: "success" | "neutral";
  onDismiss?: () => void;
}) {
  return (
    <div
      className={`status-message status-message--${tone}`}
      role="status"
      tabIndex={-1}
    >
      <Icon name={tone === "success" ? "check" : "spark"} size={16} />
      <span>{children}</span>
      {onDismiss ? (
        <button
          aria-label="Dismiss notification"
          className="icon-button icon-button--small"
          onClick={onDismiss}
          type="button"
        >
          <Icon name="close" size={14} />
        </button>
      ) : null}
    </div>
  );
}
