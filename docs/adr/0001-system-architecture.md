# ADR 0001: System Architecture

- **Status:** Accepted for the MVP
- **Date:** 2026-11-09
- **Implementation status:** In progress

## Context

The first vertical slice must let a reviewer register, upload a supported
document, ask a grounded question, inspect citations, and run retrieval
evaluations without buying an AI-provider credential.

The system handles private multi-user content. Authorization must be
consistent across documents, chunks, conversations, citations, and
evaluations. The code also needs replaceable persistence, parser, embedding,
retrieval, and answer-provider implementations without requiring distributed
operations for an MVP.

## Decision

Build a modular monolith with:

- a React and TypeScript browser application;
- a FastAPI Python backend;
- PostgreSQL with pgvector for the production persistence path;
- a SQLite-compatible path for fast automated tests;
- deterministic local embedding and extractive answer providers by default;
- optional OpenAI and Anthropic answer-provider adapters;
- synchronous ingestion for bounded TXT, Markdown, PDF, and DOCX files;
- signed, short-lived authentication in an `HttpOnly` cookie;
- Docker Compose as the local integration topology.

The backend separates HTTP transport, application orchestration, framework-light
domain behavior, infrastructure adapters, and cross-cutting core concerns.
Dependency direction points inward from transport and infrastructure toward
application/domain contracts.

All private operations are user-scoped. Ownership is enforced in persistence
queries rather than relying on identifiers being unguessable or on
post-retrieval checks.

## Rationale

A modular monolith keeps transactions, authorization, local setup, and tracing
simple while the domain and API contract are still changing. Explicit adapter
boundaries preserve the ability to replace providers or persistence behavior
without paying the operational cost of independent services.

Local deterministic providers make tests reproducible and keep the primary
review path usable offline. Optional hosted providers remain integrations, not
availability dependencies.

Synchronous ingestion avoids a queue and worker in the first slice. The 10 MiB
upload limit and bounded parsing are therefore architectural requirements, not
only validation details.

## Alternatives considered

### Independent ingestion, retrieval, and chat services

Rejected for the MVP. They introduce network contracts, deployment ordering,
distributed tracing, and partial-failure handling before scale or team
boundaries justify them.

### Queue-based ingestion from the first release

Deferred. It would improve request latency and isolation for large documents,
but requires job state, workers, retries, and operational visibility. The
first slice instead accepts bounded synchronous work.

### A hosted model and embedding API as a hard dependency

Rejected. It would make local development, CI, and reviewer evaluation depend
on credentials, cost, network availability, and third-party data processing.

### Store authentication tokens in browser Web Storage

Rejected. An `HttpOnly` cookie reduces token exposure to browser JavaScript.
Cookie authentication requires deliberate CORS, CSRF, lifetime, and secure
transport controls.

## Consequences

Positive consequences:

- one backend deployment and database transaction boundary;
- a no-cost, offline happy path;
- deterministic retrieval and answer tests;
- clear seams for providers and PostgreSQL/SQLite behavior;
- fewer operational components for the first slice.

Costs and risks:

- synchronous parsing consumes API request capacity;
- the modular boundaries require code-review discipline inside one process;
- SQLite compatibility cannot prove pgvector or PostgreSQL full-text behavior;
- cookie authentication introduces CSRF considerations;
- a single backend scales ingestion, retrieval, and API traffic together;
- optional hosted providers create a separate data-egress boundary.

## Required validation

Acceptance of this decision does not mean implementation is complete. The
architecture requires:

- two-user ownership tests for every private resource path;
- bounded parser and malformed-document tests;
- deterministic provider tests;
- PostgreSQL-specific integration tests;
- frontend credentialed-request and token-storage checks;
- backend and frontend image builds;
- a Compose upload, question, and citation smoke path.

The commands and current unverified status are maintained in `../testing.md`.
