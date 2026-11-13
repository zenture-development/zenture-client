# Changelog

All notable changes to `zenture` will be documented in this file.

The project follows semantic versioning once public releases begin. Prerelease
versions may change while the Public API contract is still in release-candidate
state.

## 1.2.1 (2026-11-13)

Additive release: learning and standards. Nothing from 1.2.0 changed; see
[docs/migration.md](docs/migration.md#upgrading-to-121).

- Run results: `PublicRunResponse` exposes the optional `learning_applied`, `essence_version` and `essence`
  (your Essenz as context, on a `revise` decision), `standards_checked` (closed models `StandardsChecked` and
  `StandardCheckResult`: which of your standards a terminal Run was checked against and with what result, ids
  and codes only, never their texts) and a finding exposes `essence_focus`. Runs without these fields parse as
  before. The client has no call that reads the Essenz.
- Standards: `get_standards()`, `define_standard()` and `edit_standard()` on `ZentureClient`,
  `AsyncZentureClient`, `McpClient` and `AsyncMcpClient` list, add and change your own standards
  (`GET`/`POST /v1/standards`, `PATCH /v1/standards/{standard_id}` over an API token, the tools of the same
  names over OAuth) into the closed `AgentStandards` / `AgentStandard` models, with REST and MCP parity. Every
  standard carries `version`, `restorable_versions` (ascending, at most 20, never the current one) and
  `suggested_criterion` (or `None`). `edit_standard(..., expected_version=...)` takes field edits, or
  `restore_version`, or `use_suggested_criterion=True` (exactly one). The owner is the account of the token or
  session; the only owner argument is the kind `"user"` (default) or `"org"`, and an organisation standard needs
  an organisation context and the organisation owner's rights. REST writes take a saved `idempotency_key`; the
  MCP tools derive theirs. Closed error codes (`standard_version_conflict`, `standard_not_found`,
  `standard_forbidden`, `standard_duplicate`, `standard_invalid`, `standard_limit`, `standard_not_checkable`,
  `standards_unavailable`) arrive as `ZentureAPIError.error_code`.
- There are no calls for learnings, standard versions or accepting a suggestion (REST and MCP).
- The OpenAPI mirror is resynced with the Gateway artefact.

## 1.2.0 (2026-11-08)

The file upload flow changed and two public methods were removed. Migration
steps are in [docs/migration.md](docs/migration.md#upgrading-to-120). Text Runs, MCP
text Runs and the classic API are unchanged.

- Source check: `runs.prepare`, `runs.run` (sync and async) and the MCP client `run` accept an
  optional `reference_file` (an `art_...` reference), an uploaded source file an inline text
  answer is checked against. `PublicRunResponse` and `PublicRunListItem` carry
  `reference_file_attached` (default `False`); `SafeResultLocation.source` gains
  `reference_file`. The OpenAPI mirror and response shapes follow the Gateway.

### Changed (upgrade notes)

This release removes public methods and changes a return type; see the migration guide.

- `runs.signed_upload(...)` is removed.
  - Before: `up = client.runs.signed_upload(file_name=..., mime_type=..., byte_size=...,
    content_hash=..., idempotency_key=...)` returned `SignedUploadResponse` (`upload_id`,
    `expires_at`, optional `upload_url`).
  - After: there is no such method; `attach_artifact` issues the upload link itself.
    `SignedUploadResponse` is no longer in `zenture.types`.
- `runs.attach_artifact(...)` changes signature and result (sync and async).
  - Before: `client.runs.attach_artifact(upload_id=up.upload_id, file_name=..., mime_type=...,
    content=..., content_hash=..., idempotency_key=...)` sent the bytes with a bearer `POST
    /v1/run-artifacts` and returned `ArtifactUploadResponse` (`artifact_ref`, `content_hash`,
    `byte_size`, `content_type`).
  - After: `client.runs.attach_artifact(file_name=..., mime_type=..., content=...,
    content_hash=..., idempotency_key=...)` (no `upload_id`) issues the link and sends the
    bytes with `PUT` and `X-Upload-Token` (no bearer). It returns `ArtifactUploadAccepted`
    (`artifact_ref`, `status="pending"`, `retry_after_seconds`, `next_step`). Start the Run
    with the `artifact_ref` and handle `ZentureArtifactNotReadyError`.
- MCP `McpClient.attach_artifact(...)` returns `ArtifactUploadResponse` in a new shape (see
  below).

- File upload moves to the two-step flow. `runs.attach_artifact(...)` (sync and async) now
  issues an upload link and then sends the bytes with `PUT` and the single-use
  `X-Upload-Token` (no bearer, no redirects, never retried). It no longer takes
  `upload_id` and returns `ArtifactUploadAccepted` (`artifact_ref`, `status="pending"`,
  `retry_after_seconds`, `next_step`). The token never appears in a URL, log, repr or
  exception text, and an upload link that is not https or not on the client's API origin
  under `/v1/run-artifacts/uploads/` is refused before any byte leaves.
- Removed: `runs.signed_upload(...)` and `SignedUploadResponse` (issuing is part of
  `attach_artifact`), the bearer `POST /v1/run-artifacts` route and its
  `PublicRunArtifactResponse`, and the `X-Upload-ID`, `Content-Type` and `Content-Length`
  upload header declarations.
- New typed errors for file references: `ZentureArtifactNotReadyError` (with
  `retry_after_seconds`), `ZentureArtifactTooLargeError`, `ZentureArtifactTypeUnsupportedError`,
  `ZentureArtifactExtractFailedError`, `ZentureArtifactNotFoundError` and
  `ZentureArtifactQuotaExceededError`. `ZentureAPIError` carries `retry_after_seconds`.
- The OpenAPI mirror lists `PUT /v1/run-artifacts/uploads/{upload_id}`, the new
  `signed-upload` answer and the new error codes `artifact_not_ready`,
  `artifact_too_large`, `artifact_extract_failed` and `artifact_quota_exceeded` (HTTP 429,
  never retried by the client).
- The OpenAPI mirror follows the final Gateway contract: the upload `PUT` documents 408 and
  415, `GET /v1/run-artifacts/{artifact_id}` names its path parameter `artifact_id`, and the
  `zenture_ref` descriptor is described as an accepted reference.
- The upload `PUT` always carries `Content-Length` equal to the declared size (bytes, streams
  and files, sync and async), never chunked; new error code `length_required` (411,
  `ZentureLengthRequiredError`, not retried).
- `ZentureArtifactQuotaExceededError.retry_after_seconds` carries the Gateway's wait hint
  (1 to 3600 seconds, also sent as `Retry-After`); the client still does not retry it.
- `artifact_unavailable` raises `ZentureArtifactUnavailableError`. The upload `PUT` never
  answers it (a used or wrong token answers 401); Run prepare answers it as a retryable 503
  for a transient file-read failure, and the client now retries it with the usual backoff. The OpenAPI mirror's artifact status
  gains optional `skipped_images` (integer, at least 0).
- MCP `attach_artifact` mirrors the tool and sends no bytes: `ArtifactUploadResponse` is now an
  upload link (`upload_url`, `upload_id`, `upload_token` hidden in repr, `expires_at`) or a
  registered host-bytes file (`content_hash`, `byte_size`, `content_type`, `status`,
  `retry_after_seconds`), each with `next_steps`.
- The committed OpenAPI mirror follows the Gateway public contract: API token management routes are no longer listed. Token management stays in the web app and is not part of the SDK surface.
- A terminal Run may carry `billing_summary.status="pending"` (valid, no `final_credits`);
  the later `run.billing.settled` event is a valid event. Documented: re-read the Run with
  `runs.get()` for the final Credits.
- `runs.wait()` (sync and async) uses the server `retry_after_seconds` hint (bounded
  1 to 10 seconds) as the next poll delay and re-opens a broken event stream from its
  last cursor instead of polling for the rest of the call.
- Finding results expose `subject_kind`, `reason_code`, `defect_type`, `profile`, `what`
  and `locations`; composed content exposes `next_action_text`.
- `PublicCapabilityCoverage` accepts up to 256 `available_refs` and `unavailable_refs`
  (Backend bound); `limitation_refs` stays at 32.
- `PublicRunResponse.input_kind` and `PublicRunListItem.input_kind` (`"text"` or `"file"`) say
  whether the Run checks a submitted text or an uploaded file; the server sets it at Run
  creation and sends it on every Run, including failed ones. The models accept an absent value
  (`None`) so a new client still works against a server that does not send it yet.

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
