import type {
  AuthCredentials,
  Conversation,
  CreateConversationRequest,
  DocumentRecord,
  Message,
  SendMessageRequest,
  User,
} from "./types";

const configuredBase = import.meta.env.VITE_API_BASE_URL as string | undefined;
const API_BASE = (configuredBase || "/api/v1").replace(/\/+$/, "");

interface ApiErrorPayload {
  detail?:
    | string
    | Array<{
        msg?: string;
      }>;
  message?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function errorMessage(status: number, payload: unknown): string {
  if (payload && typeof payload === "object") {
    const apiPayload = payload as ApiErrorPayload;

    if (typeof apiPayload.detail === "string") {
      return apiPayload.detail;
    }

    if (Array.isArray(apiPayload.detail)) {
      const messages = apiPayload.detail
        .map((item) => item.msg)
        .filter((message): message is string => Boolean(message));
      if (messages.length > 0) {
        return messages.join(". ");
      }
    }

    if (typeof apiPayload.message === "string") {
      return apiPayload.message;
    }
  }

  if (status === 401) {
    return "Your session has expired. Please sign in again.";
  }
  if (status === 413) {
    return "That file is larger than the 10 MiB upload limit.";
  }
  return "The request could not be completed. Please try again.";
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: "include",
      headers,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError(
      "Unable to reach the service. Check your connection and try again.",
      0,
      null,
    );
  }

  const text = response.status === 204 ? "" : await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text) as unknown;
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    throw new ApiError(errorMessage(response.status, payload), response.status, payload);
  }

  return payload as T;
}

function jsonBody(value: unknown): string {
  return JSON.stringify(value);
}

export const api = {
  register(credentials: AuthCredentials): Promise<User> {
    return request<User>("/auth/register", {
      method: "POST",
      body: jsonBody(credentials),
    });
  },

  login(credentials: AuthCredentials): Promise<User> {
    return request<User>("/auth/login", {
      method: "POST",
      body: jsonBody(credentials),
    });
  },

  logout(): Promise<void> {
    return request<void>("/auth/logout", { method: "POST" });
  },

  me(signal?: AbortSignal): Promise<User> {
    return request<User>("/auth/me", { signal });
  },

  listDocuments(signal?: AbortSignal): Promise<DocumentRecord[]> {
    return request<DocumentRecord[]>("/documents", { signal });
  },

  uploadDocument(file: File): Promise<DocumentRecord> {
    const body = new FormData();
    body.append("file", file);
    return request<DocumentRecord>("/documents", {
      method: "POST",
      body,
    });
  },

  deleteDocument(documentId: string): Promise<void> {
    return request<void>(`/documents/${encodeURIComponent(documentId)}`, {
      method: "DELETE",
    });
  },

  listConversations(signal?: AbortSignal): Promise<Conversation[]> {
    return request<Conversation[]>("/conversations", { signal });
  },

  createConversation(
    input: CreateConversationRequest,
  ): Promise<Conversation> {
    return request<Conversation>("/conversations", {
      method: "POST",
      body: jsonBody(input),
    });
  },

  listMessages(
    conversationId: string,
    signal?: AbortSignal,
  ): Promise<Message[]> {
    return request<Message[]>(
      `/conversations/${encodeURIComponent(conversationId)}/messages`,
      { signal },
    );
  },

  sendMessage(
    conversationId: string,
    input: SendMessageRequest,
  ): Promise<Message> {
    return request<Message>(
      `/conversations/${encodeURIComponent(conversationId)}/messages`,
      {
        method: "POST",
        body: jsonBody(input),
      },
    );
  },
};
