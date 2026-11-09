export interface User {
  id: string;
  email: string;
}

export interface AuthCredentials {
  email: string;
  password: string;
}

export interface DocumentRecord {
  id: string;
  filename: string;
  media_type: string;
  status: string;
  chunk_count: number;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at?: string;
}

export interface Citation {
  index: number;
  document_id: string;
  filename: string;
  chunk_id: string;
  page?: number | null;
  excerpt: string;
}

export type MessageRole = "user" | "assistant" | "system";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  created_at: string;
  citations?: Citation[];
}

export interface CreateConversationRequest {
  title: string;
}

export interface SendMessageRequest {
  content: string;
  top_k: number;
}
