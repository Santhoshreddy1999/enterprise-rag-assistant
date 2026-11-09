# Deployment Guide

**Supported topology:** locally verified development deployment with Docker
Compose.

`compose.yaml` is not a production deployment claim. It defines a single-host
pgvector, backend, and frontend stack so the MVP can be built and exercised
consistently.

## Prerequisites

- Docker Engine or Docker Desktop.
- Docker Compose v2.
- Enough memory for PostgreSQL, two application images, parsing, and tests.
- Host ports `3000` and `8000`, unless changed in `.env`.

The backend and frontend build contexts must each contain a working
`Dockerfile`. Their image builds are an explicit verification gate.

## Configure

Copy the example without committing the result:

```sh
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

At minimum, replace:

- `POSTGRES_PASSWORD` with a long URL-safe database password;
- `RAG_JWT_SECRET` with at least 32 random bytes of entropy.

Generate a URL-safe value with:

```sh
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Important configuration groups:

- `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` configure the database
  container and the backend connection URL.
- `BACKEND_PORT` and `FRONTEND_PORT` select published host ports.
- `RAG_JWT_SECRET`, `RAG_JWT_TTL_MINUTES`, `RAG_COOKIE_SECURE`, and
  `RAG_CORS_ORIGINS` control the local authentication boundary.
- `RAG_ANSWER_PROVIDER=local` keeps answering offline; the current embedding
  provider is deterministic and local.
- `RAG_OPENAI_API_KEY` and `RAG_ANTHROPIC_API_KEY` are optional runtime backend
  values.
- `VITE_API_BASE_URL` is public browser configuration compiled into the
  frontend image; it must never contain a secret.

The exact environment names are aligned with backend settings and the frontend
build. Both images and the complete local smoke path were verified on
2026-11-09.

For local HTTP, `RAG_COOKIE_SECURE=false` is necessary for the browser to send
the cookie. Any HTTPS environment must use `RAG_COOKIE_SECURE=true`.

## Validate configuration

Compose can validate syntax and interpolation without starting containers:

```sh
docker compose --env-file .env config --quiet
```

For syntax-only CI or review, `.env.example` supplies non-secret placeholder
values:

```sh
docker compose --env-file .env.example config --quiet
```

A successful config render does not verify Dockerfiles, application
configuration, database migrations, or health endpoints.

## Start and inspect

Build and start:

```sh
docker compose --env-file .env up --build --wait
```

Inspect state and recent logs:

```sh
docker compose ps
docker compose logs backend frontend db
```

Expected host endpoints after health checks pass:

- frontend at `http://localhost:3000`;
- same-origin API through `http://localhost:3000/api/v1`;
- backend liveness at `http://localhost:8000/api/v1/health/live`;
- backend readiness at `http://localhost:8000/api/v1/health/ready`;
- backend metrics at `http://localhost:8000/api/v1/metrics`.

The database has no published host port. The backend reaches it as `db:5432`
on the private `application` network.

## Health behavior

The database health check uses `pg_isready`. Backend startup is ordered after
database health, and its health check calls `/api/v1/health/ready`. Frontend
startup is ordered after backend health, and its health check requests `/`
inside the container.

Compose dependency ordering is not a substitute for application retry and
recovery behavior. Confirm that restarting PostgreSQL and the backend produces
a controlled recovery before relying on this topology for demonstrations.

## Persistent data and backups

The named volume `pgdata` survives `docker compose down` and ordinary container
replacement:

```sh
docker compose down
```

`docker compose down --volumes` deletes the local database and must be treated
as destructive.

An example logical backup command is:

```sh
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > enterprise-rag.sql
```

The backup contains private application data. Encrypt and access-control it.
Do not assume a backup is usable until a restore has been rehearsed against a
separate database.

The backend image runs `alembic upgrade head` before starting Uvicorn. The
initial empty-database migration was verified against PostgreSQL/pgvector.
Zero-downtime upgrades and restoration into a separate database remain
unverified blockers for a production release.

## Optional hosted providers

Keep `RAG_ANSWER_PROVIDER=local` unless an external provider is intentionally
enabled. Before selecting `openai` or `anthropic`:

1. review the provider's data processing, residency, and retention terms;
2. set only that provider's key in the backend runtime environment;
3. confirm logs and error telemetry do not contain excerpts or keys;
4. apply egress controls where the environment supports them;
5. test the missing-key and provider-timeout behavior.

Do not pass provider keys as Docker build arguments or `VITE_` variables.

## Adapting for production

A production design must add or verify all of the following:

- TLS termination and `Secure` cookies;
- CSRF defense appropriate to the chosen origins;
- a managed secret store and documented rotation;
- an exact CORS allow list;
- database encryption, network policy, backups, restore tests, and migrations;
- non-root, minimally privileged, vulnerability-scanned images;
- immutable image references and a release/promotion process;
- request, parser, provider, and database timeouts;
- rate limits and resource quotas;
- centralized redacted logs, metrics, alerting, and retention;
- availability, scaling, rollback, disaster recovery, and data-deletion
  procedures.

No cloud provider, orchestrator, or high-availability design is currently
supported. The local Compose file should not be deployed directly to an
internet-facing host.

## Troubleshooting

Render the resolved configuration:

```sh
docker compose --env-file .env config
```

Inspect one service and rerun its health command:

```sh
docker compose ps
docker compose logs backend
docker compose exec backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=3)"
```

If the frontend is healthy but API calls fail, confirm that
`VITE_API_BASE_URL` is reachable from the browser, not merely from the
container network. Because Vite values are compiled into assets, changing this
value requires rebuilding the frontend image.

## Local verification record

On 2026-11-09:

- Compose configuration rendered successfully.
- Backend and frontend images built.
- PostgreSQL/pgvector, FastAPI, and Nginx containers became healthy.
- Alembic created the initial schema and vector extension.
- `scripts/smoke_test.py` passed through the direct API.
- The same smoke test passed through the Nginx `/api/v1` proxy.

This is local deployment evidence only. No remote or production deployment is
claimed.
