import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import type { Conversation } from "../api/types";
import { EmptyState, ErrorState, Spinner } from "./Feedback";
import { Icon } from "./Icon";

interface ConversationPanelProps {
  conversations: Conversation[];
  selectedId: string | null;
  createRequestKey: number;
  loading: boolean;
  loadError: string | null;
  creating: boolean;
  createError: string | null;
  onCreate: (title: string) => Promise<boolean>;
  onRetry: () => void;
  onSelect: (conversationId: string) => void;
  onCloseMobile: () => void;
}

function formatConversationDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const today = new Date();
  const sameDay =
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate();

  return new Intl.DateTimeFormat(undefined, sameDay
    ? { hour: "numeric", minute: "2-digit" }
    : { month: "short", day: "numeric" }).format(date);
}

export function ConversationPanel({
  conversations,
  selectedId,
  createRequestKey,
  loading,
  loadError,
  creating,
  createError,
  onCreate,
  onRetry,
  onSelect,
  onCloseMobile,
}: ConversationPanelProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (showCreate) {
      inputRef.current?.focus();
    }
  }, [showCreate]);

  useEffect(() => {
    if (createRequestKey > 0) {
      setShowCreate(true);
    }
  }, [createRequestKey]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedTitle = title.trim();
    if (!normalizedTitle || creating) {
      return;
    }
    const created = await onCreate(normalizedTitle);
    if (!created) {
      return;
    }
    setTitle("");
    setShowCreate(false);
    onCloseMobile();
  }

  return (
    <aside className="conversation-panel" aria-labelledby="conversations-title">
      <div className="conversation-panel__mobile-head">
        <span>Conversations</span>
        <button
          aria-label="Close conversations"
          className="icon-button"
          onClick={onCloseMobile}
          type="button"
        >
          <Icon name="close" />
        </button>
      </div>

      <div className="conversation-panel__brand">
        <span className="brand-mark">N</span>
        <span>Northstar</span>
      </div>

      <button
        className="button button--primary new-chat-button"
        onClick={() => setShowCreate(true)}
        type="button"
      >
        <Icon name="plus" size={17} />
        New conversation
      </button>

      {showCreate ? (
        <form className="new-conversation-form" onSubmit={handleCreate}>
          <label htmlFor="conversation-title">Conversation title</label>
          <input
            id="conversation-title"
            onChange={(event) => setTitle(event.target.value)}
            placeholder="e.g. Benefits handbook"
            ref={inputRef}
            required
            value={title}
          />
          {createError ? (
            <p className="field-error" role="alert">
              {createError}
            </p>
          ) : null}
          <div>
            <button
              className="button button--small button--primary"
              disabled={creating || !title.trim()}
              type="submit"
            >
              {creating ? (
                <>
                  <Spinner label="Creating conversation" />
                  Creating…
                </>
              ) : (
                "Create"
              )}
            </button>
            <button
              className="button button--small button--ghost"
              disabled={creating}
              onClick={() => {
                setShowCreate(false);
                setTitle("");
              }}
              type="button"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      <div className="conversation-panel__heading">
        <h2 id="conversations-title">Conversations</h2>
        {!loading && !loadError ? (
          <span className="count-badge">{conversations.length}</span>
        ) : null}
      </div>

      <nav aria-label="Conversation history" className="conversation-nav">
        {loading ? (
          <div className="conversation-loading" role="status">
            <span className="skeleton skeleton--conversation" />
            <span className="skeleton skeleton--conversation" />
            <span className="skeleton skeleton--conversation" />
            <span className="sr-only">Loading conversations</span>
          </div>
        ) : null}
        {!loading && loadError ? (
          <ErrorState
            compact
            message={loadError}
            onRetry={onRetry}
            title="History unavailable"
          />
        ) : null}
        {!loading && !loadError && conversations.length === 0 ? (
          <EmptyState
            icon={<Icon name="message" size={20} />}
            title="No conversations yet"
            action={
              <button
                className="text-button"
                onClick={() => setShowCreate(true)}
                type="button"
              >
                Start your first
                <Icon name="arrow" size={14} />
              </button>
            }
          >
            Create a focused thread for your questions.
          </EmptyState>
        ) : null}
        {!loading && !loadError && conversations.length > 0 ? (
          <ul className="conversation-list">
            {conversations.map((conversation) => {
              const isSelected = selectedId === conversation.id;
              return (
                <li key={conversation.id}>
                  <button
                    aria-current={isSelected ? "page" : undefined}
                    className={`conversation-link${isSelected ? " is-active" : ""}`}
                    onClick={() => {
                      onSelect(conversation.id);
                      onCloseMobile();
                    }}
                    type="button"
                  >
                    <Icon name="message" size={16} />
                    <span>
                      <strong>{conversation.title}</strong>
                      <small>{formatConversationDate(conversation.updated_at ?? conversation.created_at)}</small>
                    </span>
                    {isSelected ? <Icon name="chevron" size={14} /> : null}
                  </button>
                </li>
              );
            })}
          </ul>
        ) : null}
      </nav>

      <div className="conversation-panel__foot">
        <Icon name="book" size={15} />
        Answers include source citations
      </div>
    </aside>
  );
}
