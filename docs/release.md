# Release

The client is prepared for a public beta once the critical review gate and
pre-go-live configuration are complete.

## Public Beta Expectations

- README, docs, examples, and onboarding files are public-safe.
- CI runs Ruff format, Ruff lint, mypy, Pyright, pytest, coverage, build, and
  Twine metadata checks.
- Coverage remains above the configured gate.
- Examples compile and use environment-based clients.
- The source distribution includes docs, examples, OpenAPI, tests, and public
  governance files.
- The wheel contains importable package code only.

## Publishing

PyPI publishing uses Trusted Publishing through GitHub Actions OIDC only, as
SECURITY.md and CONTRIBUTING.md require. Do not add long-lived PyPI tokens to
repository secrets, including as a fallback.

Before public go-live, confirm branch protection, required checks, CODEOWNERS,
secret scanning, push protection, and protected publishing environments.
