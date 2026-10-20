# Changelog

All notable changes to `zenture` will be documented in this file.

The project follows semantic versioning once public releases begin. Prerelease
versions may change while the Public API contract is still in release-candidate
state.

## Unreleased

- A terminal Run may carry `billing_summary.status="pending"` (valid, no `final_credits`);
  the later `run.billing.settled` event is a valid event. Documented: re-read the Run with
  `runs.get()` for the final Credits.
- `runs.wait()` (sync and async) uses the server `retry_after_seconds` hint (bounded
  1 to 10 seconds) as the next poll delay and re-opens a broken event stream from its
  last cursor instead of polling for the rest of the call.
- Finding results expose `subject_kind`, `reason_code`, `defect_type`, `profile`, `what`
  and `locations`; composed content exposes `next_action_text`.

## 1.1.0 - 2026-10-19

- Error handling: `PublicError` and `ZentureAPIError` carry `retryable`, which is
  `True` when the gateway marks a failure as safe to retry and `False` otherwise.
- Five new error codes: `run_input_not_processable`, `run_input_contains_contact_data`,
  `guest_quota_exhausted`, `price_ceiling_exceeded` and `result_unavailable`.
- New `AcceptRunRequest` starts a Run in one call: the Prepare fields plus an optional
  `predecessor_run_id` pointing at one of your finished Runs.
- Run responses expose `technical_status`, `phase`, `queue_expires_at`, `result` and
  `retry_after_seconds` when the gateway reports them.
- The bundled OpenAPI mirror matches the current gateway contract, including
  `Retry-After` on 503 responses and on 502/504 for Run routes.

## 1.0.3 - 2026-10-15

- Align current developer documentation and API-token links with the canonical
  public destinations.
- Make the migration install command upgrade an existing `zenture` installation.

## 1.0.2 - 2026-10-10

- Run event iteration (`iter_events`, sync and async) stops with a polling timeout once a
  reconnect wait consumes the caller's budget, so a coarse monotonic clock (e.g. on Windows)
  cannot start one more request after the deadline.
- Package description and documentation call the package the zenture client instead of an SDK.

## 1.0.1 - 2026-10-10

- Documentation leads with Runs; the classic API resources are documented as secondary.

- MCP peers keep authorization failures (`AuthorizationRequired`,
  `PermissionDenied`, including inside an `ExceptionGroup`) classified and
  do not retry them in `wait_run` or discovery; only unknown transport failures
  are wrapped as retryable `mcp_transport_unavailable`.

- MCP result-contract errors no longer chain the Pydantic validation error, so
  submitted values do not appear in tracebacks.

- The MCP run review example uses `wait_run` under one caller budget that also
  covers the final full read; a late completion raises `ZenturePollingTimeoutError`.

- The end-to-end example reports a billed total only when every component is
  known, and names the operations included in each total.

- Documented `wait_run` on both MCP peers and clarified that MCP `run()` only
  starts a Run. Documented in-process `login(session_only=True)`; the CLI
  `--session-only` option is verification only. PyPI publication requires
  Trusted Publishing without a long-lived token fallback.

- Examples print identifiers and status by default; evaluation results and the
  optimized prompt require `--show-result` / `--show-prompt`.

- Added immutable typed validation `issues` on REST and MCP errors, bounded by
  public field schemas, and content-free local Run `ValidationError` summaries.
  Sync/async REST Run and artifact requests automatically negotiate safe details
  with `X-Zenture-Error-Details: issues`; older servers remain supported.

- Added sync/async `get_tool_catalog()` and public `zenture.mcp.McpToolDefinition`
  for detached registered schemas, descriptions and annotations, with bounded
  complete pagination. Existing name-only `list_tools()` behavior is preserved.

- MCP Run peers now allocate or accept a strict caller-owned idempotency key and
  expose validated Run-only success/error receipts for deliberate recovery.
  Save an explicit key before interruption; default model serialization and
  REST models retain their existing shape.

- Rename the repository to `zenture-client`, the distribution to `zenture`, and
  public API classes to `ZentureClient` / `AsyncZentureClient` without aliases.
- Preserve API-token resource behavior and caller-provided bearer MCP support;
  Public package publication remains outside this source cutover.
- Added native authorization for the hosted MCP endpoint: explicit browser
  (PKCE, loopback) and headless device login through `zenture.auth.login` /
  `login_async`, secure credential storage (macOS Keychain proven; Windows
  Credential Manager and Linux Secret Service implemented, not yet verified)
  with a session-only mode, and safe refresh that requires a new login after an
  interrupted refresh.
- Added the `zenture` command: `zenture auth login [--device] [--session-only]`,
  `zenture auth status` and `zenture auth clear` with documented exit codes.
- Added the public `zenture.mcp` module with `McpClient` and `AsyncMcpClient`
  exposing the six Run tools; the former `zenture._mcp` path is internal and no
  alias exists (hard cutover).
- Declared CPython 3.14 support and configured the CI matrix for 3.11 to 3.14
  across Linux, macOS and Windows (configured, not yet run).

- Added nullable `deadline_at` Run response fields, additive response tolerance,
  and finite sync/async Run waits with deadline-aware timeout context.
- Added an opt-in, internal MCP client peer adapter with sync/async transport
  ports, official Streamable HTTP integration, typed Run mappings, bounded safe
  errors and local cross-channel composition tests. The API-only installation
  remains unchanged; public `zenture-client` promotion is deferred.

## 1.0.0rc3 - 2026-06-28

- Clarified external vs. internal evaluation flows across SDK docs.
- Added local SDK validation for internal evaluation target payloads.
- Updated evaluation error handling docs for local `ValidationError` and API
  `ZentureValidationError`.

## 1.0.0rc2 - 2026-06-27

- Updated the README logo to use the public production-hosted zenture logo so
  PyPI renders the project description correctly.

## 1.0.0rc1 - 2026-06-27

- Added `client.wallet.get()` and `await client.wallet.get()` for the public
  `GET /v1/wallet` account projection with `wallet:read` scope.
- Removed the unpublished `client.billing.get()` mapping and `/v1/billing`
  SDK surface in favor of wallet terminology before public release.
- Added optional `chat.run(..., include_content=True)` and
  `evaluations.run(..., include_detail=True)` attachments for common
  chat-then-evaluate application flows.
- Added an end-to-end chat evaluation smoke example with wallet, model
  discovery, input wizard, chat, evaluation, and billed-amount summary output.
- Synced the Public API OpenAPI artifact with pagination parameters for chats,
  chat messages, and evaluations.
- Added `limit` and `cursor` support plus sync/async iterator helpers for chat
  summaries, chat messages, and evaluations.
- Added pagination documentation and an executable pagination example.
- Updated operation-error contract handling to match the current OpenAPI
  `PublicOperationError` schema.

## 0.1.0b1 - 2026-06-15

- Added SDK architecture and implementation plan.
- Added repository governance bootstrap documents.
- Added public sync/async clients, private httpx transport, strict contract
  models, model discovery, single-/multi-model chat, evaluation creation,
  operation reads, billing, usage, limits, idempotency, retry, timeout and
  polling primitives.

- Add sync/async MCP `wait_run` with finite deadlines, same-Run summary observation, safe read retries and official per-call read budgets.
