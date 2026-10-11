# Security Policy

## Supported Versions

`zenture` is prerelease software. Security reports are welcome for client
runtime behavior, documentation, examples, packaging, CI, and release workflows.

## Reporting a Vulnerability

Report suspected vulnerabilities privately by email to
[security@zenture.app](mailto:security@zenture.app). Do not open a public issue
for anything that could be exploited before a fix is available. Include the
details listed below, use fake tokens and synthetic data only, and expect an
acknowledgement before any public discussion.

Open a GitHub issue in the `zenture-client` repository only for security
hardening requests, dependency concerns, release-process issues, documentation
gaps, or redaction problems that are not exploitable and do not include active
secrets, exploit payloads, private customer data, or instructions for abusing
zenture systems.

Use a clear title such as `Security: <short description>` and include:

- affected file, workflow, package, or behavior
- expected security property
- observed risk
- reproduction steps using fake tokens and synthetic data only
- suggested severity if known

Do not post real zenture API tokens, JWTs, customer data, private prompts,
provider payloads, production URLs with sensitive query strings, or working
exploit instructions in GitHub issues.

High-impact vulnerabilities and anything that requires coordinated disclosure
go to the private email route above, never to a public issue.

## Secret Handling Expectations

zenture API tokens are server-side credentials. They must not be embedded in
browsers, mobile apps, frontend bundles, public repositories, notebooks with
shared output, logs, analytics, traces, or customer-visible error reports.

The client must not log or expose:

- API tokens or Authorization headers
- JWTs
- prompts or model answers
- raw request or response bodies
- payment, billing, or provider payloads

Examples and tests must use fake credentials only.

## Token Environment Binding

zenture API tokens are environment-bound. Public client users should use tokens
only with the production zenture API.

The client performs client-side validation to prevent accidental cross-environment
token use. The API must enforce the same rule server-side. Public client
documentation must not publish non-production API hostnames, deployment names,
local port conventions, or token validation internals.

## Release Security

Public package publishing must use PyPI Trusted Publishing through GitHub
Actions OIDC. Long-lived PyPI API tokens are not allowed in repository secrets.

Before any public PyPI release, the repository must have:

- branch protection or rulesets on the default branch
- required CI checks
- CODEOWNERS review for protected paths
- secret scanning and push protection
- protected `pypi` release environment with manual approval
