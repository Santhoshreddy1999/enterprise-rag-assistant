# Contributing

Thank you for improving Enterprise RAG Assistant. Keep changes small, tested,
and explicit about what is implemented versus proposed.

## Before you start

1. Search existing issues before opening a new one.
2. Use an issue for behavior changes that affect the API, data model, security
   controls, or deployment topology.
3. Record durable architecture decisions in `docs/adr/`.
4. Do not commit credentials, private documents, database dumps, or generated
   dependency directories.

## Local setup

The supported integration path is Docker Compose:

```sh
cp .env.example .env
# Replace the placeholder database password and RAG_JWT_SECRET in .env.
docker compose --env-file .env config --quiet
docker compose --env-file .env up --build
```

On PowerShell, use `Copy-Item .env.example .env` for the first command.

The frontend requires Node.js 20.19 or newer; CI and the container build use
Node.js 24:

```sh
cd frontend
npm ci
npm run typecheck
npm test
npm run build
```

The backend validation interface expected by CI is:

```sh
cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.lock
python -m ruff check .
python -m ruff format --check .
python -m mypy app
python -m pytest --cov=app --cov-report=term-missing
```

Run `python scripts/smoke_test.py` from the repository root after the Compose
stack is healthy. Keep CI and this guide aligned if commands change.

## Change guidelines

- Preserve the `/api/v1` API boundary and document intentional contract
  changes.
- Enforce ownership in the query that loads an owned record; do not fetch first
  and authorize later.
- Treat uploaded and retrieved text as untrusted data.
- Add tests for success, authorization failure, invalid input, and ownership
  isolation.
- Keep the local deterministic providers usable without paid credentials.
- Update operational and security documentation with behavior changes.

## Pull requests

Use a focused branch and complete the pull request template. A reviewable pull
request should:

- explain the user-visible outcome and risk;
- identify implemented, in-progress, and deferred work;
- include tests or explain why a test is not applicable;
- include migration and rollback notes when data or deployment changes;
- pass backend, frontend, image-build, and applicable dependency-review checks.

Do not claim a check passed unless it ran. Label local or CI gates that could
not be run as **unverified**, with the reason.

## Reporting security problems

Do not disclose vulnerabilities in a public issue. Follow `SECURITY.md`.
