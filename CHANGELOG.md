# Changelog

All notable changes are documented here. This project follows Semantic
Versioning for published releases.

## 0.1.0 — 2026-11-09

First locally and remotely verified MVP.

### Added

- FastAPI registration, login, logout, and short-lived `HttpOnly` cookie
  authentication.
- Per-user ownership for documents, conversations, retrieval, and evaluations.
- TXT, Markdown, PDF, and DOCX ingestion with bounded parsing and deterministic
  chunking.
- Deterministic offline embeddings and extractive cited answers.
- PostgreSQL/pgvector semantic retrieval, PostgreSQL full-text retrieval, and
  reciprocal-rank fusion.
- Optional OpenAI and Anthropic answer-provider adapters.
- Conversation history, citation provenance, and retrieval evaluation.
- Responsive React/TypeScript authentication, document, conversation, chat,
  and citation interface.
- Alembic migration, structured logs, Prometheus metrics, liveness/readiness,
  non-root images, Nginx proxy, and Docker Compose topology.
- Backend, frontend, security, image-build, and PostgreSQL smoke CI gates.
- Architecture decisions, threat model, testing/deployment guides, contribution
  policy, issue forms, pull-request template, and grouped dependency updates.

### Verification

- 22 backend tests passed with 87% measured coverage.
- 9 frontend tests, TypeScript checking, and Vite production build passed.
- Backend and frontend container images built.
- PostgreSQL 16/pgvector migration and three-service health passed.
- Direct and Nginx-proxied registration, upload, hybrid retrieval, citations,
  history, evaluation, and ownership-isolation smoke paths passed.
- GitHub Actions run
  [42589088728](https://github.com/Santhoshreddy1999/enterprise-rag-assistant/actions/runs/42589088728)
  passed on commit `9958a53`.

### Known limitations

- No refresh-token rotation or server-side session revocation.
- No application rate limiting or production CSRF token.
- Document ingestion is synchronous and does not include OCR.
- External provider adapters are mock-tested but have not been called with live
  credentials.
- No browser automation, load test, cloud deployment, or backup restoration
  claim.
