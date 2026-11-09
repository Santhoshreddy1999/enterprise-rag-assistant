# Architecture

**Architecture status:** accepted for the MVP; implementation and end-to-end
verification are in progress.

This document expands the contract in `implementation-spec.md`. It describes
the intended system and does not assert that an unverified component is
complete.

## Goals

- Keep every document, conversation, retrieval, and evaluation operation
  scoped to the authenticated user.
- Produce answers that can be traced to stored chunks through citations.
- Provide repeatable local development and tests without a paid AI provider.
- Use the same application behavior with PostgreSQL/pgvector in the deployed
  path and SQLite-compatible storage in automated tests.
- Keep provider, parser, retrieval, and persistence details behind explicit
  interfaces.

The MVP does not include organizations, queues, OCR, streaming responses,
billing, or a supported cloud topology.

## Runtime components

### Browser application

The React application owns routing and presentation for authentication,
documents, conversations, chat, and citations. It calls `/api/v1` with
`credentials: "include"` and does not persist authentication tokens in browser
storage.

### HTTP API

FastAPI is the transport boundary. Route handlers validate HTTP input, invoke
application use cases, and serialize responses. Authentication and ownership
checks happen before private data is returned.

The backend follows these dependency directions:

```text
api -> application -> domain
                   -> infrastructure
core supports configuration, security, and telemetry
```

- `api` contains routes, schemas, and request dependencies.
- `application` coordinates registration, ingestion, retrieval, messaging, and
  evaluation.
- `domain` contains framework-light entities and retrieval behavior.
- `infrastructure` implements SQLAlchemy persistence, document parsing,
  embeddings, rankers, and answer-provider adapters.
- `core` owns configuration, cookie security, and telemetry.

Pragmatic exceptions are acceptable when they do not couple retrieval or
security policy to the web framework.

### PostgreSQL and pgvector

PostgreSQL is the production persistence contract. Relational columns hold
ownership and application state; pgvector columns hold chunk embeddings.
PostgreSQL full-text search provides lexical candidates. A named Compose volume
persists the database across normal container replacement.

SQLite is a test compatibility path, not the documented production database.
It computes vector and lexical scores in application code while preserving
ownership, fusion, and citation semantics.

### Provider adapters

The default embedding and answer providers are deterministic and local. Their
purpose is repeatability and offline operation, not state-of-the-art answer
quality. OpenAI and Anthropic answer adapters are optional and inactive unless
selected and configured through environment variables.

## Request and data flows

### Authentication

Registration and login verify credentials, issue a short-lived signed value in
an `HttpOnly` cookie, and return the user representation. Logout clears the
cookie. Protected handlers resolve the current user from the cookie and return
a generic authentication failure when validation fails.

### Document ingestion

1. Authenticate the request.
2. Enforce the 10 MiB request limit and supported extension/media-type policy.
3. Treat the client filename as metadata only.
4. Parse bounded content, reject empty content, and normalize text.
5. Chunk deterministically and generate deterministic embeddings.
6. Store the owned document and its chunks atomically when practical.
7. Return metadata and the resulting chunk count.

The first slice processes ingestion inline. A background queue is deliberately
deferred, so request duration is bounded by upload and parsing limits.

### Grounded questions

1. Load the owned conversation using an ownership-scoped query.
2. Persist the user's message.
3. Search only chunks visible to that user.
4. Produce semantic and lexical candidate rankings.
5. Fuse rankings with reciprocal rank fusion and select `top_k`.
6. Delimit retrieved excerpts and identify them as untrusted data.
7. Ask the selected provider for an answer that preserves citation markers.
8. Persist the assistant message and citation-to-chunk links.
9. Return the answer and inspectable citation metadata.

No retrieval result is allowed to broaden the caller's authorization scope.

### Retrieval evaluation

An authenticated user submits named cases containing a query and expected
owned document IDs. The same retrieval path returns candidate IDs. The
application computes hit rate and mean reciprocal rank and stores the owned
evaluation result.

## Security and trust boundaries

There are four primary boundaries:

- browser to API, where cookies, CORS, CSRF assumptions, and input validation
  apply;
- API to database, where parameterized queries and ownership predicates apply;
- parser to uploaded bytes, where resource and format limits apply;
- backend to hosted model providers, where private text leaves the local trust
  boundary only through explicit operator configuration.

See `security.md` for threats and required controls.

## Availability and failure behavior

- Liveness indicates that the backend process can serve requests.
- Readiness indicates that required dependencies are usable.
- Compose starts the backend only after PostgreSQL is healthy and starts the
  frontend only after backend readiness succeeds.
- Missing credentials for an explicitly selected hosted provider are a
  configuration error. They must not silently fall back and change data-flow
  expectations.
- Provider failures should return a controlled error and must not expose keys,
  raw prompts, or private document content in logs.
- Partial ingestion must not expose a document as ready. Transaction or cleanup
  behavior belongs in implementation tests.

## Observability

The contract includes structured application logs and an `/api/v1/metrics`
endpoint. Logs may include request IDs, route templates, status, duration,
provider name, and aggregate retrieval counts. They must exclude passwords,
cookies, keys, raw documents, prompts, retrieved excerpts, and complete
provider responses.

No production monitoring, alerting, retention, or service-level objective is
defined for the first vertical slice.

## Deployment boundary

`compose.yaml` is a local single-host topology, not a production reference
architecture. It publishes the frontend and backend, keeps PostgreSQL on the
internal network, and persists database state in `pgdata`. TLS termination,
managed secrets, backups, high availability, migrations, and provider egress
controls remain deployer responsibilities.

## Decisions

- [ADR 0001](adr/0001-system-architecture.md) records the modular monolith and
  local-first provider architecture.
- [ADR 0002](adr/0002-pgvector-hybrid-retrieval.md) records PostgreSQL,
  pgvector, full-text search, and reciprocal rank fusion.
