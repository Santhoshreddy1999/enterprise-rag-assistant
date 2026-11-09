import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Conversation } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ChatPanel } from "../components/ChatPanel";
import { ConversationPanel } from "../components/ConversationPanel";
import { DocumentPanel } from "../components/DocumentPanel";
import { Icon } from "../components/Icon";
import { Spinner } from "../components/Feedback";

type MobilePanel = "conversations" | "documents" | null;

export function Workspace() {
  const { user, logout, clearSession } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [conversationError, setConversationError] = useState<string | null>(null);
  const [conversationReload, setConversationReload] = useState(0);
  const [creatingConversation, setCreatingConversation] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createRequestKey, setCreateRequestKey] = useState(0);
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoadingConversations(true);
    setConversationError(null);

    void api
      .listConversations(controller.signal)
      .then((items) => {
        setConversations(items);
        setSelectedId((current) => {
          if (current && items.some((item) => item.id === current)) {
            return current;
          }
          return items[0]?.id ?? null;
        });
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") {
          return;
        }
        if (reason instanceof ApiError && reason.status === 401) {
          clearSession();
          return;
        }
        setConversationError(
          reason instanceof Error
            ? reason.message
            : "Unable to load conversations.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoadingConversations(false);
        }
      });

    return () => controller.abort();
  }, [clearSession, conversationReload]);

  useEffect(() => {
    if (!mobilePanel) {
      return;
    }
    function closeOnEscape(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        setMobilePanel(null);
      }
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [mobilePanel]);

  const selectedConversation = useMemo(
    () =>
      conversations.find((conversation) => conversation.id === selectedId) ??
      null,
    [conversations, selectedId],
  );

  async function createConversation(title: string): Promise<boolean> {
    setCreatingConversation(true);
    setCreateError(null);
    try {
      const conversation = await api.createConversation({ title });
      setConversations((current) => [conversation, ...current]);
      setSelectedId(conversation.id);
      return true;
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) {
        clearSession();
        return false;
      }
      setCreateError(
        reason instanceof Error
          ? reason.message
          : "Unable to create this conversation.",
      );
      return false;
    } finally {
      setCreatingConversation(false);
    }
  }

  function requestNewConversation() {
    setCreateError(null);
    setCreateRequestKey((value) => value + 1);
    setMobilePanel("conversations");
  }

  async function handleLogout() {
    setLoggingOut(true);
    setLogoutError(null);
    try {
      await logout();
    } catch (reason) {
      setLogoutError(
        reason instanceof Error ? reason.message : "Unable to sign out.",
      );
      setLoggingOut(false);
    }
  }

  if (!user) {
    return null;
  }

  return (
    <div
      className={`workspace${mobilePanel ? ` has-${mobilePanel}-drawer` : ""}`}
    >
      <ConversationPanel
        conversations={conversations}
        createError={createError}
        createRequestKey={createRequestKey}
        creating={creatingConversation}
        loadError={conversationError}
        loading={loadingConversations}
        onCloseMobile={() => setMobilePanel(null)}
        onCreate={createConversation}
        onRetry={() => setConversationReload((value) => value + 1)}
        onSelect={setSelectedId}
        selectedId={selectedId}
      />

      <main className="workspace-main">
        <header className="workspace-topbar">
          <button
            aria-expanded={mobilePanel === "conversations"}
            aria-label="Open conversations"
            className="icon-button mobile-only"
            onClick={() => setMobilePanel("conversations")}
            type="button"
          >
            <Icon name="menu" />
          </button>

          <span className="workspace-topbar__brand">
            <span className="brand-mark">N</span>
            <span>Northstar</span>
          </span>

          <div className="workspace-topbar__actions">
            <button
              aria-expanded={mobilePanel === "documents"}
              className="button button--small button--ghost mobile-library-button"
              onClick={() => setMobilePanel("documents")}
              type="button"
            >
              <Icon name="book" size={16} />
              Library
            </button>
            <span className="user-chip" title={user.email}>
              <span aria-hidden="true">{user.email.charAt(0).toUpperCase()}</span>
              <span>{user.email}</span>
            </span>
            <button
              aria-label="Sign out"
              className="icon-button"
              disabled={loggingOut}
              onClick={() => void handleLogout()}
              title="Sign out"
              type="button"
            >
              {loggingOut ? <Spinner label="Signing out" /> : <Icon name="logout" />}
            </button>
          </div>
        </header>

        {logoutError ? (
          <div className="topbar-alert" role="alert">
            {logoutError}
            <button
              aria-label="Dismiss sign-out error"
              onClick={() => setLogoutError(null)}
              type="button"
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        ) : null}

        <ChatPanel
          conversation={selectedConversation}
          onRequestNew={requestNewConversation}
        />
      </main>

      <aside className="documents-drawer" aria-label="Document library">
        <div className="documents-drawer__mobile-head">
          <span>Document library</span>
          <button
            aria-label="Close document library"
            className="icon-button"
            onClick={() => setMobilePanel(null)}
            type="button"
          >
            <Icon name="close" />
          </button>
        </div>
        <DocumentPanel />
      </aside>

      {mobilePanel ? (
        <button
          aria-label="Close open panel"
          className="drawer-backdrop"
          onClick={() => setMobilePanel(null)}
          type="button"
        />
      ) : null}
    </div>
  );
}
