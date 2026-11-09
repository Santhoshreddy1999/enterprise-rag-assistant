# Testing Strategy

**Status:** local MVP gates and the first full remote CI run passed on
2026-11-09. No gate is considered passed merely because its workflow exists.

## Principles

- Prefer deterministic local embeddings and answers in automated tests.
- Use synthetic documents; never place private or regulated content in
  fixtures, logs, snapshots, or CI artifacts.
- Test authorization with at least two users.
- Assert citations and ownership, not only answer wording.
- Keep a fast SQLite-compatible path while exercising PostgreSQL-specific
  vector and full-text behavior separately.
- Treat flaky, skipped, and not-run checks as visible work, not success.

## Backend checks

The backend CI interface is:

```sh
cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.lock
python -m ruff check .
python -m ruff format --check .
python -m mypy app
python -m pytest --cov=app --cov-report=term-missing
```

Latest local result: lint, formatting, and mypy passed; 22 tests passed with
87% measured coverage. One upstream Starlette/AnyIO deprecation warning remains.

### Unit tests

Unit tests should cover deterministic chunk boundaries, embedding
normalization, cosine and lexical scoring, reciprocal rank fusion, metric
calculation, password and cookie helpers, and citation-marker handling.

### API tests

API tests should cover the request and response contract in
`implementation-spec.md`, including:

- register, login, logout, current-user, and invalid authentication paths;
- upload type, size, empty-content, malformed-file, list, and deletion paths;
- conversation ownership, message history, grounded answer, and citation
  metadata;
- retrieval evaluation inputs and metric output;
- liveness, readiness, and safe metrics exposure.

Every owned resource suite should create two users and demonstrate that a valid
identifier does not bypass ownership.

### PostgreSQL integration tests

The PostgreSQL layer must exercise behavior SQLite cannot prove:

- pgvector extension and vector column setup;
- cosine-distance candidate ordering;
- PostgreSQL full-text query behavior;
- reciprocal rank fusion over database candidate sets;
- migrations against an empty database;
- ownership predicates in the PostgreSQL queries.

The local Compose smoke run applied Alembic to PostgreSQL 16 with pgvector and
exercised registration, persisted chunks, vector and full-text candidate
queries, rank fusion, citations, evaluation, and two-user isolation. The fast
pytest suite remains SQLite-backed; a dedicated PostgreSQL pytest suite for
ordering edge cases remains planned.

## Frontend checks

`frontend/package.json` defines the following commands and requires Node.js
20.19 or newer:

```sh
cd frontend
npm ci
npm run typecheck
npm test
npm run build
```

Component and route tests should cover authentication transitions, upload
validation feedback, document list updates, conversation selection, message
submission, citation rendering, loading states, and accessible error messages.
Mock the network boundary; do not duplicate backend retrieval logic in the UI.

The production build is a separate gate because tests do not prove TypeScript
project references, Vite bundling, or browser asset generation succeed.

## Container and Compose checks

Build images independently:

```sh
docker build -t enterprise-rag-backend:local backend
docker build -t enterprise-rag-frontend:local frontend
```

Validate Compose interpolation with example values:

```sh
docker compose --env-file .env.example config --quiet
```

For a runtime smoke check, first copy `.env.example` to `.env` and replace its
two secret placeholders, then run:

```sh
docker compose --env-file .env up --build --wait
docker compose ps
```

Verify liveness and readiness:

```sh
curl --fail http://localhost:8000/api/v1/health/live
curl --fail http://localhost:8000/api/v1/health/ready
```

PowerShell equivalents:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health/live
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
```

Run the authenticated end-to-end path:

```sh
python scripts/smoke_test.py
```

To exercise the frontend Nginx proxy:

```sh
RAG_SMOKE_API_URL=http://localhost:3000/api/v1 python scripts/smoke_test.py
```

The script registers two synthetic users, uploads a synthetic document, creates
a conversation, asks a question, verifies citation provenance and history,
runs retrieval evaluation, and confirms cross-user isolation.

Clean up containers while preserving database data:

```sh
docker compose down
```

## CI event behavior

The main CI workflow is intended to run backend checks, frontend checks,
secret scanning, and both image builds for pushes and pull requests.

Dependency review is intentionally a separate pull-request-only workflow. The
GitHub dependency-review action requires base/head comparison data and is not a
valid push-event gate.

Dependabot updates package manifests and GitHub Actions independently. Its pull
requests still require the same checks as human-authored changes.

## Release evidence

A release candidate should retain links or logs for:

- backend lint, formatting, typing, and tests;
- explicit PostgreSQL integration tests;
- frontend typing, component tests, and build;
- backend and frontend image builds;
- Compose health plus the authenticated end-to-end smoke path;
- secret scan and dependency review;
- migration and restore rehearsal for any schema change.

Coverage percentages can help find untested code, but this project has not set a
numeric coverage threshold. Do not imply one exists.

## Verification record

Verified locally on 2026-11-09:

- Ruff lint and formatting.
- Mypy over 16 backend source files.
- 22 backend tests; 87% measured coverage.
- TypeScript check.
- 9 frontend tests across API, authentication form, and citation behavior.
- Vite production build.
- Backend and frontend Docker image builds.
- Compose config, migration, three healthy services, direct API smoke, and
  same-origin Nginx-proxy smoke.

Still unverified:

- Pull-request dependency review on a maintained feature PR; the job is
  intentionally skipped on pushes.
- Live OpenAI/Anthropic calls.
- Browser automation, load testing, cloud deployment, and backup restoration.

Remote evidence:

- [GitHub Actions run 42589088728](https://github.com/Santhoshreddy1999/enterprise-rag-assistant/actions/runs/42589088728)
  passed backend, frontend, Compose validation, secret scan, both image builds,
  and PostgreSQL end-to-end smoke on commit `9958a53`.
