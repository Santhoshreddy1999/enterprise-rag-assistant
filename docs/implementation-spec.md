# Enterprise RAG Assistant — Implementation Specification

**Status:** MVP verified locally on 2026-11-09
**Started:** 2026-11-09
**MVP goal:** A reviewer can register, upload a supported document, ask a grounded question, inspect citations, and run retrieval tests without a paid AI credential.

## Product boundary

Implemented in the first vertical slice:

- Email/password registration and login.
- Short-lived authentication in an `HttpOnly` cookie.
- Per-user document ownership.
- Text, Markdown, PDF, and DOCX upload.
- Deterministic chunking and embedding.
- PostgreSQL/pgvector production storage.
- SQLite-compatible automated test path.
- Semantic plus lexical hybrid retrieval.
- Source-grounded local answer provider.
- Optional OpenAI and Anthropic adapters configured only through environment variables.
- Conversation history.
- Retrieval evaluation.
- React interface.
- Docker Compose and CI.

Not in the first vertical slice:

- Organization administration.
- Refresh-token rotation.
- Background queues.
- OCR.
- Streaming model responses.
- Cloud deployment.
- Billing.

## API contract

All application routes use `/api/v1`.

### Authentication

`POST /auth/register`

```json
{
  "email": "engineer@example.com",
  "password": "correct horse battery staple"
}
```

Creates the account, sets the access cookie, and returns:

```json
{
  "id": "uuid",
  "email": "engineer@example.com"
}
```

`POST /auth/login` uses the same request and response shape.

`POST /auth/logout` clears the cookie and returns HTTP 204.

`GET /auth/me` returns the authenticated user.

### Documents

`POST /documents` accepts multipart form field `file`.

Response:

```json
{
  "id": "uuid",
  "filename": "handbook.pdf",
  "media_type": "application/pdf",
  "status": "ready",
  "chunk_count": 12,
  "created_at": "ISO-8601 timestamp"
}
```

`GET /documents` returns the current user's documents.

`DELETE /documents/{document_id}` removes an owned document and returns HTTP 204.

Limits:

- Maximum upload: 10 MiB.
- Allowed: `.txt`, `.md`, `.pdf`, `.docx`.
- Empty documents are rejected.
- Filenames are metadata only and never become server filesystem paths.

### Conversations

`POST /conversations`

```json
{
  "title": "Benefits handbook"
}
```

`GET /conversations` lists owned conversations.

`GET /conversations/{conversation_id}/messages` returns message history.

`POST /conversations/{conversation_id}/messages`

```json
{
  "content": "How many annual leave days are provided?",
  "top_k": 5
}
```

Response:

```json
{
  "id": "uuid",
  "role": "assistant",
  "content": "The handbook provides ... [1]",
  "created_at": "ISO-8601 timestamp",
  "citations": [
    {
      "index": 1,
      "document_id": "uuid",
      "filename": "handbook.pdf",
      "chunk_id": "uuid",
      "page": 4,
      "excerpt": "..."
    }
  ]
}
```

### Evaluation

`POST /evaluations/retrieval`

```json
{
  "name": "benefits-smoke",
  "top_k": 5,
  "cases": [
    {
      "query": "annual leave allowance",
      "expected_document_ids": ["uuid"]
    }
  ]
}
```

Returns hit-rate and mean reciprocal rank plus per-case retrieved document IDs.

### Operations

- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`

## Backend boundaries

```text
backend/app/
├── api/            # HTTP schemas, routes, dependencies
├── application/    # use cases and orchestration
├── core/           # configuration, security, telemetry
├── domain/         # framework-light entities and value behavior
├── infrastructure/ # SQLAlchemy, parsers, providers, retrieval
└── main.py
```

Pragmatic exceptions are allowed when they reduce ceremony without coupling core retrieval/security behavior to FastAPI.

## Data model

- `users`
- `documents`
- `chunks`
- `conversations`
- `messages`
- `message_citations`
- `evaluation_runs`

All owned records carry `user_id` directly or through a required owned parent. Queries enforce ownership.

## Retrieval

The deterministic embedding provider tokenizes normalized text, hashes tokens into a fixed-size vector, applies signed term frequency, and L2-normalizes the result. It is not presented as a state-of-the-art semantic model; it exists for offline development and repeatable tests.

Production PostgreSQL path:

- pgvector cosine distance for vector candidates.
- PostgreSQL full-text ranking for lexical candidates.
- Reciprocal rank fusion.

SQLite test path:

- Cosine scoring and token-overlap lexical scoring over the authenticated user's chunks.
- The same fusion and citation behavior.

## Answer providers

- `local`: extractive answer assembled only from retrieved excerpts.
- `openai`: OpenAI chat API with configured model and key.
- `anthropic`: Anthropic messages API with configured model and key.

Provider output must preserve citation markers. Missing external credentials fail configuration safely and do not affect local tests.

## Security

- Adaptive password hashing.
- Signed short-lived cookie.
- `HttpOnly`, `SameSite=Lax`; `Secure` enabled by configuration.
- Explicit CORS allow list with credentials.
- Generic authentication errors.
- Ownership filters in every document, conversation, retrieval, and evaluation query.
- Upload size, extension, media type, and parsed-content limits.
- Retrieved content delimited and identified as untrusted data.
- No raw documents, passwords, cookies, prompts, or provider keys in logs.

## Frontend routes

- `/login`
- `/register`
- `/` authenticated workspace containing documents, upload, conversations, chat, and citations.

The frontend sends `credentials: "include"` and never stores authentication tokens in Web Storage.

## Verification targets

- Backend formatting/lint/type checks.
- Backend unit and API tests.
- PostgreSQL integration test through Docker.
- Frontend type check, component tests, and production build.
- Backend and frontend images build.
- Compose health and end-to-end smoke path.
- Secret scan and dependency review in CI.
