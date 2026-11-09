import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { api } from "../api/client";
import type { Conversation, Message } from "../api/types";
import { Citations, renderContentWithCitations } from "./Citations";
import { EmptyState, ErrorState, Spinner } from "./Feedback";
import { Icon } from "./Icon";

interface ChatPanelProps {
  conversation: Conversation | null;
  onRequestNew: () => void;
}

const STARTER_QUESTIONS = [
  "Summarize the key points in my documents.",
  "What policies are described in the library?",
  "Where does the source discuss requirements?",
];

function formatMessageTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function MessageSkeleton() {
  return (
    <div className="message-skeleton" role="status">
      <span className="skeleton skeleton--message-short" />
      <span className="skeleton skeleton--message-long" />
      <span className="skeleton skeleton--message-medium" />
      <span className="sr-only">Loading conversation history</span>
    </div>
  );
}

export function ChatPanel({
  conversation,
  onRequestNew,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [content, setContent] = useState("");
  const [topK, setTopK] = useState(5);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const activeConversationRef = useRef<string | null>(conversation?.id ?? null);

  useEffect(() => {
    activeConversationRef.current = conversation?.id ?? null;
  }, [conversation?.id]);

  useEffect(() => {
    setContent("");
    setSendError(null);
    setMessages([]);

    if (!conversation) {
      setLoading(false);
      setLoadError(null);
      return;
    }

    const conversationId = conversation.id;
    const controller = new AbortController();
    setLoading(true);
    setLoadError(null);

    void api
      .listMessages(conversationId, controller.signal)
      .then((history) => {
        if (activeConversationRef.current === conversationId) {
          setMessages(history);
        }
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") {
          return;
        }
        if (activeConversationRef.current === conversationId) {
          setLoadError(
            reason instanceof Error
              ? reason.message
              : "Unable to load this conversation.",
          );
        }
      })
      .finally(() => {
        if (
          !controller.signal.aborted &&
          activeConversationRef.current === conversationId
        ) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [conversation, reloadKey]);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = content.trim();
    if (!conversation || !question || sending) {
      return;
    }

    const conversationId = conversation.id;
    const optimisticId = `pending-${Date.now()}`;
    const optimisticMessage: Message = {
      id: optimisticId,
      role: "user",
      content: question,
      created_at: new Date().toISOString(),
      citations: [],
    };

    setMessages((current) => [...current, optimisticMessage]);
    setContent("");
    setSending(true);
    setSendError(null);

    try {
      const answer = await api.sendMessage(conversationId, {
        content: question,
        top_k: topK,
      });
      if (activeConversationRef.current === conversationId) {
        setMessages((current) => [...current, answer]);
      }
    } catch (reason) {
      if (activeConversationRef.current === conversationId) {
        setMessages((current) =>
          current.filter((message) => message.id !== optimisticId),
        );
        setContent(question);
        setSendError(
          reason instanceof Error ? reason.message : "Unable to send your question.",
        );
      }
    } finally {
      if (activeConversationRef.current === conversationId) {
        setSending(false);
      }
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      formRef.current?.requestSubmit();
    }
  }

  if (!conversation) {
    return (
      <section className="chat-panel chat-panel--welcome" aria-labelledby="welcome-title">
        <div className="welcome-orbit" aria-hidden="true">
          <span className="welcome-orbit__ring" />
          <span className="welcome-orbit__mark">
            <Icon name="spark" size={28} />
          </span>
        </div>
        <p className="eyebrow">Your research workspace</p>
        <h1 id="welcome-title">Ask your documents. Verify every answer.</h1>
        <p>
          Create a conversation, ask a focused question, and follow each
          citation back to the supporting passage.
        </p>
        <button
          className="button button--primary"
          onClick={onRequestNew}
          type="button"
        >
          <Icon name="plus" size={17} />
          Start a conversation
        </button>
      </section>
    );
  }

  return (
    <section className="chat-panel" aria-labelledby="chat-title">
      <header className="chat-heading">
        <div>
          <p className="eyebrow">Conversation</p>
          <h1 id="chat-title">{conversation.title}</h1>
        </div>
        <span className="grounded-label">
          <span aria-hidden="true" />
          Source-grounded
        </span>
      </header>

      <div
        aria-busy={loading || sending}
        aria-live="polite"
        className="message-region"
      >
        {loading ? <MessageSkeleton /> : null}
        {!loading && loadError ? (
          <ErrorState
            message={loadError}
            onRetry={() => setReloadKey((value) => value + 1)}
            title="Conversation unavailable"
          />
        ) : null}
        {!loading && !loadError && messages.length === 0 ? (
          <div className="chat-empty">
            <div className="chat-empty__icon" aria-hidden="true">
              <Icon name="spark" size={22} />
            </div>
            <h2>What would you like to understand?</h2>
            <p>
              Answers are generated from relevant passages in your document
              library and include citations when sources are found.
            </p>
            <div className="starter-questions" aria-label="Suggested questions">
              {STARTER_QUESTIONS.map((question) => (
                <button
                  key={question}
                  onClick={() => setContent(question)}
                  type="button"
                >
                  <span>{question}</span>
                  <Icon name="arrow" size={15} />
                </button>
              ))}
            </div>
          </div>
        ) : null}
        {!loading && !loadError && messages.length > 0 ? (
          <ol className="message-list">
            {messages.map((message) => {
              const citations = message.citations ?? [];
              return (
                <li
                  className={`message message--${message.role}`}
                  key={message.id}
                >
                  <div className="message__identity" aria-hidden="true">
                    {message.role === "assistant" ? (
                      <Icon name="spark" size={16} />
                    ) : (
                      <span>You</span>
                    )}
                  </div>
                  <article>
                    <div className="message__meta">
                      <strong>
                        {message.role === "assistant" ? "Northstar" : "You"}
                      </strong>
                      <time dateTime={message.created_at}>
                        {formatMessageTime(message.created_at)}
                      </time>
                    </div>
                    <p className="message__content">
                      {message.role === "assistant"
                        ? renderContentWithCitations(
                            message.content,
                            citations,
                            message.id,
                          )
                        : message.content}
                    </p>
                    {message.role === "assistant" ? (
                      <Citations citations={citations} messageId={message.id} />
                    ) : null}
                  </article>
                </li>
              );
            })}
            {sending ? (
              <li className="message message--assistant message--thinking">
                <div className="message__identity" aria-hidden="true">
                  <Icon name="spark" size={16} />
                </div>
                <article>
                  <div className="thinking-dots" role="status">
                    <span />
                    <span />
                    <span />
                    <span className="sr-only">Finding relevant passages</span>
                  </div>
                </article>
              </li>
            ) : null}
          </ol>
        ) : null}
        <div ref={endRef} />
      </div>

      <div className="composer-wrap">
        {sendError ? (
          <p className="composer-error" role="alert">
            <span aria-hidden="true">!</span>
            {sendError}
          </p>
        ) : null}
        <form className="composer" onSubmit={handleSend} ref={formRef}>
          <label className="sr-only" htmlFor="question">
            Ask a question
          </label>
          <textarea
            disabled={loading || Boolean(loadError)}
            id="question"
            onChange={(event) => setContent(event.target.value)}
            onKeyDown={handleComposerKeyDown}
            placeholder="Ask a question about your documents…"
            rows={2}
            value={content}
          />
          <div className="composer__toolbar">
            <label className="retrieval-select">
              <span>Sources to search</span>
              <select
                aria-label="Number of source passages to search"
                onChange={(event) => setTopK(Number(event.target.value))}
                value={topK}
              >
                <option value={3}>3</option>
                <option value={5}>5</option>
                <option value={8}>8</option>
              </select>
            </label>
            <span className="composer__hint">Enter to send · Shift+Enter for a line break</span>
            <button
              aria-label="Send question"
              className="send-button"
              disabled={!content.trim() || sending || loading || Boolean(loadError)}
              type="submit"
            >
              {sending ? <Spinner label="Sending question" /> : <Icon name="send" />}
            </button>
          </div>
        </form>
        <p className="disclaimer">
          Review cited passages before relying on an answer.
        </p>
      </div>
    </section>
  );
}
