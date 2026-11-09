# Security Threat Model

**Status:** MVP threat model reviewed against the locally verified
implementation on 2026-11-09. This is not a penetration test or production
security certification.

## Scope and assumptions

This model covers the browser, React application, FastAPI backend,
document-processing code, PostgreSQL/pgvector, local providers, optional hosted
answer providers, and the local container topology.

It assumes:

- the host, container runtime, and TLS terminator are administered separately;
- PostgreSQL is not exposed to untrusted networks;
- operators replace example secrets and restrict access to environment values;
- hosted providers process submitted excerpts under their own security and
  retention terms;
- deterministic local providers offer repeatability, not protection from
  malicious input.

Cloud identity, organization-level authorization, billing, OCR, background
workers, and model training are outside this MVP.

## Assets

The primary assets are account credentials, signed session cookies, private
documents and parsed chunks, conversation content, citation links, evaluation
data, database credentials, signing secrets, hosted-provider keys, and
security-relevant logs.

The main security objectives are:

- **Confidentiality:** one user cannot read another user's content; secrets and
  raw private content do not enter logs or client bundles.
- **Integrity:** a user cannot alter another user's records, citations remain
  tied to the chunks used, and untrusted documents cannot become system
  instructions.
- **Availability:** bounded uploads and parsing prevent a single request from
  exhausting the service.

## Trust boundaries

1. The browser crosses an HTTP boundary into the API. Cookies, CORS, request
   origin, validation, and response encoding matter here.
2. The backend crosses a query boundary into PostgreSQL. Parameterization and
   ownership predicates matter here.
3. Uploaded bytes cross into parsers. File-type confusion, decompression, CPU,
   memory, and parser vulnerabilities matter here.
4. Retrieved text crosses into an answer provider. It is data controlled by a
   document author, not trusted instructions.
5. Optional provider calls cross the local environment boundary and can expose
   selected excerpts to a third party.
6. Source and manifests cross the software-supply-chain boundary during CI and
   image builds.

## Threats and required controls

### Spoofing and session abuse

Threats include credential stuffing, user enumeration, forged or replayed
cookies, session theft through transport compromise, and stale sessions after
credential changes.

Required controls:

- hash passwords with an adaptive password-hashing algorithm and unique salts;
- return generic registration/login failures where account disclosure matters;
- sign cookies with a high-entropy secret and enforce short expiration;
- set `HttpOnly` and `SameSite=Lax`, and set `Secure` in every HTTPS
  environment;
- rate-limit authentication at the edge or application before internet
  exposure;
- never store the authentication value in Web Storage.

Residual risk: the first slice has no refresh-token rotation or documented
server-side revocation. Short expiration limits but does not remove replay
risk.

### Cross-site request forgery and cross-origin access

Credentialed cookies can make state-changing requests susceptible to CSRF.
`SameSite=Lax` blocks many cross-site cookie sends, and an explicit CORS allow
list prevents unauthorized browser code from reading credentialed responses,
but CORS is not itself CSRF protection.

Required controls:

- use an exact origin allow list; never combine credentialed CORS with `*`;
- keep unsafe operations off `GET`;
- validate `Origin` or use a CSRF token for state-changing requests before
  production internet exposure;
- test disallowed origins and same-site sibling-origin scenarios;
- avoid broad cookie domain attributes.

### Broken object-level authorization

Predictable or leaked UUIDs can be used to request another user's documents,
conversations, messages, chunks, or evaluations.

Required controls:

- include the authenticated user's ownership condition in every loading,
  mutation, retrieval, and deletion query;
- derive citation access through an owned message or document;
- reject expected document IDs in evaluations when they are not owned;
- test two-user isolation for every resource route and retrieval path;
- return a non-disclosing not-found or authorization response consistently.

Fetching a record by ID and checking ownership afterward is not the preferred
pattern because it increases accidental disclosure paths.

### Injection into queries, logs, UI, and model context

Threats include SQL injection, log-forging, stored cross-site scripting, and
prompt injection embedded in a document.

Required controls:

- use parameterized SQLAlchemy expressions, including full-text search terms;
- encode text when rendering and do not inject document HTML into the DOM;
- structure logs and normalize control characters in user-controlled metadata;
- delimit excerpts, identify their source, and tell answer providers that
  excerpts are untrusted data;
- do not provide model tools, credentials, or unrestricted network access in
  the MVP;
- validate that citations refer to retrieved chunks and preserve markers.

Prompt instructions reduce accidental model compliance but are not a security
boundary. Authorization and data minimization must hold even when a model
follows malicious document text.

### Malicious document processing

Threats include extension/media-type mismatch, path traversal in filenames,
archive expansion in DOCX, pathological PDFs, parser vulnerabilities, empty or
oversized extracted content, and CPU or memory exhaustion.

Required controls:

- accept only `.txt`, `.md`, `.pdf`, and `.docx`;
- enforce the 10 MiB limit while reading, not only from `Content-Length`;
- validate extension and media type and reject unsupported content;
- keep filenames as metadata and generate any server-side identifiers;
- bound extracted text, page/part count, decompressed bytes, chunk count, and
  parser time where the library permits;
- pin and update parser dependencies;
- reject empty documents and avoid persisting partial ready state.

Because ingestion is synchronous in the first slice, resource-bound tests are
an important availability gate.

### Secret and private-data disclosure

Threats include committed `.env` files, build arguments containing secrets,
exception traces, raw request logging, database exposure, and accidental
submission of private excerpts to a hosted provider.

Required controls:

- commit only `.env.example` with non-secret placeholders;
- pass provider keys to the backend at runtime, never to the frontend build;
- redact passwords, cookies, signing values, database URLs, prompts, raw
  documents, excerpts, and provider responses from logs;
- keep PostgreSQL on an internal network;
- make hosted providers an explicit operator choice and document the data
  transfer;
- rotate any value that appears in source, logs, artifacts, or support data.

The Compose build argument `VITE_API_BASE_URL` is public configuration and must
never contain credentials.

### Tampering and repudiation

Threats include altered citations, deleted evidence, untraceable administrative
changes, and dependency or image substitution.

Required controls:

- persist citation-to-chunk links with assistant messages;
- emit request IDs and security-relevant outcomes without private payloads;
- review and pin dependency lockfiles;
- restrict workflow permissions and do not push images from untrusted pull
  requests;
- protect the default branch and require relevant CI checks.

The MVP does not define immutable audit storage. Application logs and database
records are operational evidence, not a non-repudiation guarantee.

### Denial of service

Threats include upload floods, expensive parsing, high `top_k`, large
conversation histories, repeated provider calls, and database connection
exhaustion.

Required controls:

- bound request size, extracted text, `top_k`, result excerpts, and history
  included in a provider request;
- set HTTP, database, and provider timeouts;
- constrain connection pools and container resources for the environment;
- add rate limits before public exposure;
- return controlled failures and avoid unbounded retries.

### Dependency and container compromise

Threats include malicious packages, vulnerable parsers, mutable image tags, and
over-privileged CI credentials.

Required controls:

- use lockfiles and Dependabot for Python, npm, and GitHub Actions;
- run dependency review only for pull-request events where its comparison data
  is available;
- run secret scanning and image builds in CI;
- use read-only workflow permissions by default;
- scan released images and pin base images by digest before a production
  release process is established;
- run application containers as non-root when their Dockerfiles support it.

## Verification requirements

Security-sensitive automated tests should cover:

- invalid, expired, and tampered cookies;
- cross-user list, read, delete, retrieval, citation, and evaluation access;
- disallowed origins and production cookie attributes;
- oversized, empty, mismatched, malformed, and archive-heavy uploads;
- SQL and full-text metacharacters;
- malicious document instructions and citation integrity;
- missing hosted-provider credentials and provider timeouts;
- log capture proving sensitive values are absent.

Locally verified controls:

- Argon2 password hashing and signed, expiring access cookies.
- Tampered-token rejection and no browser Web Storage token persistence.
- Explicit credentialed CORS allow list.
- Database-query ownership checks for documents, conversations, retrieval, and
  evaluations.
- Two-user API and deployed smoke tests.
- Extension/media-type, empty-file, parsed-size, and upload-size checks.
- Retrieved context marked as untrusted, bounded local answers, and persisted
  citation-to-chunk provenance.
- Runtime-only provider keys, safe provider errors, structured request logs,
  non-public database port, and non-root application images.

Open security work before internet exposure:

- CSRF token or strict `Origin` validation for state-changing requests.
- Authentication and expensive-operation rate limits.
- Stronger compressed-size, parser-time, and page/part limits for PDF/DOCX.
- Container/dependency vulnerability scan review and pull-request dependency
  review. The CI secret scan passed on 2026-11-09.
- Server-side session revocation and refresh-token strategy.
- External-provider privacy review and live timeout/failure exercise.
- Browser automation for CSP, stored-content rendering, and disallowed origins.
- Immutable audit storage, backup restoration, and incident runbooks.

## Incident response

If a secret is exposed, revoke or rotate it first, then remove it from current
source and artifacts, assess logs and provider usage, and notify affected users
when required. Rewriting Git history does not invalidate an already exposed
credential.

Report suspected vulnerabilities through the private process in
`../SECURITY.md`.
