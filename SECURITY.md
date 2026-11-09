# Security Policy

## Supported versions

This project is pre-release. Security fixes are applied to the default branch;
there are no supported release branches yet.

## Report a vulnerability

Do not open a public issue or include exploit details in a pull request.

Use GitHub's **Report a vulnerability** private reporting feature for this
repository when it is enabled. If it is unavailable, contact the repository
owner through a private channel and include:

- the affected revision and component;
- impact and prerequisites;
- minimal reproduction steps or a proof of concept;
- any known mitigation;
- whether the report may be credited publicly.

Do not include real user documents, credentials, cookies, or provider keys.
Use synthetic data in reproductions.

We aim to acknowledge a complete report within five business days. Remediation
timing depends on severity and the availability of a safe fix. Please allow
time for triage before public disclosure.

## Security scope

Reports are especially useful for:

- authentication or signed-cookie bypass;
- cross-user access to documents, chunks, conversations, or evaluations;
- unsafe document parsing, path traversal, or upload-limit bypass;
- prompt injection that crosses a trust boundary or exposes secrets;
- SQL injection or unsafe query construction;
- accidental logging or exposure of credentials and private content;
- vulnerable production dependencies or container configuration.

Provider output quality by itself is not a security vulnerability. A report is
in scope when model behavior causes unauthorized access, data disclosure, or
execution across a documented trust boundary.

## Operational baseline

Deployers are responsible for replacing all example values, enabling secure
cookies behind HTTPS, using an explicit CORS allow list, restricting database
network access, rotating exposed credentials, and applying dependency and base
image updates. See `docs/security.md` for the threat model and
`docs/deployment.md` for deployment limits.
