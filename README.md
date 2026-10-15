<img src="https://ai.zenture.app/logo.svg" alt="zenture logo" width="180">

# The official zenture Python client

Hand a task and one selected answer to zenture and get back a reasoned
acceptance decision with findings, evidence and limitations, over REST or the
hosted MCP endpoint.

The default installation includes REST, hosted MCP, and native authentication;
no extra is required. API tokens stay bound to REST, and account OAuth stays
bound to MCP. The server retains authorization, Run execution, billing, and
tenant authority; this package provides no local MCP server.

`zenture` is for backend services, automation jobs, evaluation pipelines,
CI tasks, and controlled notebook environments. zenture API tokens are
server-side credentials. Do not put them in browsers, mobile apps, frontend
bundles, public notebooks, logs, analytics, traces, or customer-visible errors.

## What a zenture Run is

A **Run** evaluates one explicitly selected answer against the task it was
meant to solve. You send the original `task` (including the criteria that
matter) and the selected `artifact` (inline text). zenture works asynchronously
and reports:

- a technical `status` (for example `queued`, `running`, `completed`);
- an `acceptance_decision`: `ready`, `revise`, `human_review` or
  `insufficient_evidence`;
- findings, evidence summaries, limitations and what was actually checked
  (coverage), in `safe_result_content`;
- a `billing_summary` with the final Credits once settled.

A `completed` Run is only technically finished; it can still say `revise`.
Starting a Run may use Credits from your zenture balance. Waiting and reading
do not start new work. Runs are identified by a `run_...` ID, which differs from
the operation IDs of the classic API resources below.
Current Run execution supports inline text. File registration is available, but
Run preparation currently rejects `zenture_ref` inputs.

## Installation

```bash
python -m pip install --upgrade zenture==1.0.3
```

Version 1.0.3 is prepared locally; publication is pending. The command above
becomes available after publication.

Supported Python: CPython 3.11, 3.12, 3.13, and 3.14 (Python 3.14 is declared; the CI matrix covers it but has not yet run; there is no upper version cap).
The installation includes the `zenture` command and the `zenture.auth` and
`zenture.mcp` modules; no extra is needed. `zenture --version` prints the
installed version without logging in or touching the network.

## Quickstart: your first Run

Create an API token at `https://ai.zenture.app/?settings=developer`, keep it
outside source code (`ZENTURE_API_KEY`, see [Authentication](#authentication)),
and save an idempotency key for the Run **before** you start it.

```python
from zenture import ZentureClient

with ZentureClient.from_env() as client:
    run = client.runs.run(  # prepares and starts; does not wait
        task="Check that the answer names exactly two colours.",
        artifact={"type": "text", "value": "Blue and green."},
        idempotency_key="review-case-123",  # your saved identity of this one review
    )
    client.runs.wait(run.run_id, timeout=120.0)  # finite polling, returns a summary
    result = client.runs.get(run.run_id, view="full")

    print(result.status, result.acceptance_decision)
    content = result.safe_result_content
    if content is not None and content.status == "available":
        print(content.content.summary)
```

The same Run through MCP uses your zenture account instead of an API token.
Log in once from a terminal (`zenture auth login`), then:

```python
from zenture.mcp import McpClient

with McpClient.connect() as client:  # stored authorization; never starts a login
    client.require_product_tools()
    run = client.run(  # starts the Run; does not wait
        task="Check that the answer names exactly two colours.",
        artifact={"type": "text", "value": "Blue and green."},
        idempotency_key="review_case_123",  # save before dispatch
    )
    client.wait_run(run.run_id, timeout=120.0)
    result = client.get_run(run.run_id, view="full").run

    print(result.status, result.acceptance_decision)
```

A local wait timeout raises `ZenturePollingTimeoutError`; it neither cancels the
Run nor loses it. Keep the `run_id` and read it later. Complete, tested versions
that also keep the budget over the final read:
[`examples/run_review.py`](./examples/run_review.py) (REST) and
[`examples/mcp_run_review.py`](./examples/mcp_run_review.py) (MCP).

### Anatomy of a Run result

| Field | Meaning |
|---|---|
| `run_id`, `profile`, `generation` | Identity and the requested profile (`standard` by default; `fast` or `detailed` only with explicit intent) |
| `status` | Nonterminal: `created`, `queued`, `running`, `waiting_for_dependency`, `partially_complete`, `cancel_requested`. Terminal: `completed`, `failed`, `cancelled`, `expired`, `budget_exhausted` |
| `acceptance_decision` | `ready`, `revise`, `human_review`, `insufficient_evidence`; absent is not `ready` |
| `safe_result_content` | `status="available"` carries `content`: `summary`, `findings`, `evidence_summaries`, `limitations`, `decision` (with `reason_code`, `next_action`) and `coverage`. `status="unavailable"` carries a `reason_code` instead |
| `capability_coverage`, `limitations` | What could and could not be checked; do not assume all requested checks ran |
| `billing_summary` | `pending`, `settled`, `released` or `unavailable`; final Credits when known. Unavailable is not zero |
| `deadline_at`, `queue`, `next_action`, `reason_code` | Timing and service guidance |
| `cancellation_requested` | A cancel was requested; the actual `status` remains authoritative |

`ready` is scoped to the evaluated requirements and evidence, not a universal
correctness guarantee. Details: [Run guide](./docs/run-guide.md#interpret-the-returned-run).

### Core Run operations

| Operation | REST (`client.runs`) | MCP (`McpClient` / `AsyncMcpClient`) |
|---|---|---|
| Preview without starting | `prepare(...)` | included in `run(...)` |
| Start | `run(...)`, or `create(...)` from a prepared proposal | `run(...)` |
| Follow-up to an earlier Run | `predecessor_run_id=` on `run`/`create` | raw tool only; the Python wrapper has no such parameter yet |
| Wait (finite) | `wait(run_id, timeout=...)` | `wait_run(run_id, timeout)` |
| Read | `get(run_id, view="summary" or "full")` | `get_run(run_id, view=...)`, result in `.run` |
| List your Runs | `list(status=..., decision=..., limit=..., cursor=...)` | `list_runs(...)` |
| Progress events | `list_events`, `iter_events` | `get_run(..., include_event_replay=True)`, `replay_events` |
| Cancel | `cancel(run_id, idempotency_key=...)` | `cancel_run(run_id)` |
| Record what you did with it | `record_outcome(run_id, outcome=..., idempotency_key=...)` | `record_run_outcome(run_id, outcome=...)` |

Outcomes are `used`, `edited`, `rejected`, `escalated` and `not_sure`; recording
one preserves the original decision. Mutating calls need a caller-owned
`idempotency_key`: reuse the same key and the identical request to recover from
an uncertain outcome, and use a new key only for a deliberately new evaluation.
See [idempotency](./docs/idempotency.md) and
[MCP Run idempotency](./docs/mcp-client.md#run-idempotency). Every field,
bound and method is in the [Run guide](./docs/run-guide.md).

## Authentication

Two separate credentials; they never mix.

| Channel | Credential | How |
|---|---|---|
| REST (`ZentureClient`, `AsyncZentureClient`) | zenture API token | Create it in the Developer overlay with an existing account at `https://ai.zenture.app/?settings=developer`; read from `ZENTURE_API_KEY` |
| Hosted MCP (`zenture.mcp`) | Your zenture account | `zenture auth login` (browser) or `zenture auth login --device` (headless) |

Keep the token outside Python source code:

```bash
# .env, not committed
ZENTURE_API_KEY=your_webapp_created_api_token
```

```bash
set -a
. ./.env
set +a
```

The client intentionally does not parse `.env` files. Load environment variables
through your runtime, deployment platform, secrets manager, or preferred local
loader. Public client usage targets the production API origin:
`https://api.zenture.app`. The client has no API-token management surface.
Full details, including MCP login, secure storage and refresh safety:
[authentication](./docs/authentication.md).

## Documentation

- [Run guide](./docs/run-guide.md): payloads, methods, results, feedback, recovery (start here).
- [MCP client](./docs/mcp-client.md) and [authentication](./docs/authentication.md).
- [Errors](./docs/errors.md), [idempotency](./docs/idempotency.md), [rate limits](./docs/rate-limits.md), [pagination](./docs/pagination.md).
- [Migration](./docs/migration.md) from the former `zenture-sdk` package: a hard
  source cutover to `ZentureClient` / `AsyncZentureClient`, no legacy aliases;
  do not install both distributions into one environment.
- Classic API: [API reference](./docs/api-reference.md), [client call reference](./docs/sdk-call-reference.md), [response shapes](./docs/response-shapes.md).
- Public API documentation: `https://www.zenture.app/en/developers`. The committed
  OpenAPI artifact is the client's local contract source of truth.

## MCP and native login

Besides the REST client, `zenture` talks to the hosted zenture MCP endpoint as a
peer channel. It authorizes *you* (a zenture account), not an API token: nothing
is read from `ZENTURE_API_KEY` and the REST client is unchanged.

Log in once from a terminal:

```bash
zenture auth login                 # opens your browser (PKCE, loopback redirect)
zenture auth login --device        # headless: shows a code to enter on another device
zenture auth login --session-only  # verify the login but store nothing
zenture auth status                # verify the stored authorization
zenture auth clear                 # delete the local record only
```

- **Explicit login only.** Ordinary calls such as `McpClient.connect()` never open a
  browser and never start a login. Without a usable authorization they raise
  `AuthorizationRequired`; you decide when to run `zenture auth login`.
- **One stored account.** This machine keeps one stored account per user profile
  (one stored account, one connection). Logging in again replaces it.
- **Device login** waits at most 10 minutes for approval and is never started
  automatically when the browser is unavailable.
- **`zenture auth clear` is local.** It deletes only the record on this machine.
  Revoke the connection itself in zenture under
  *Zugriff & Sicherheit -> Verbindungen*.
- **Secure storage.** The authorization is kept in the operating system's
  credential store. `session_only=True` keeps it in memory for the current process
  instead; the CLI `--session-only` option only verifies and discards it.

| Platform | Credential store | Status |
|---|---|---|
| macOS | Keychain | proven |
| Windows | Credential Manager | implemented, not yet verified |
| Linux | Secret Service (for example GNOME Keyring) | implemented, not yet verified |

For deliberate Run recovery, save an explicit `idempotency_key` before calling
`run` and reuse it with the same request. The named `run.idempotency_key` receipt
is excluded from default model serialization. Cancellation requires the key to
have been saved beforehand; receipts do not prove completion or billing. See
[Run idempotency](./docs/mcp-client.md#run-idempotency).

The Client supports six known MCP tool methods: `run`, `attach_artifact`,
`list_runs`, `get_run`, `cancel_run` and `record_run_outcome`. Its readiness
check requires the five core tools; `attach_artifact` is optional and is
available only when the host advertises it with an approved artifact resolver.
Artifact bytes come from that host-selected source and are not carried in MCP
JSON. See [the MCP Client guide](./docs/mcp-client.md) for details.

Synchronous (from ordinary code, not from inside a running event loop):

```python
from zenture.mcp import McpClient

with McpClient.connect() as client:  # uses the stored authorization
    client.require_product_tools()
    run = client.run(
        task="Review the selected answer",
        artifact={"type": "text", "value": "selected answer"},
        idempotency_key="review_case_123",  # persisted identity of this one review
    )
    print(client.get_run(run.run_id).run.status)
```

Asynchronous, with an explicit login in the same program:

```python
import asyncio

from zenture.auth import login_async
from zenture.mcp import AsyncMcpClient


async def main() -> None:
    with await login_async() as session:
        async with AsyncMcpClient.connect(session=session) as client:
            page = await client.list_runs(limit=5)
            print(len(page.runs))


asyncio.run(main())
```

Runnable variants live in [`examples/`](./examples/): `mcp_async_login.py`,
`mcp_sync_stored_login.py` and `mcp_device_login.py` (each supports `--help`).

### Errors and next actions

Import these from `zenture.auth`. Messages carry a fixed code, never a credential.

| Error | Meaning | What to do |
|---|---|---|
| `AuthorizationRequired` | No stored authorization, or it can no longer be used (for example after an interrupted refresh or a revoked connection) | Run `zenture auth login` |
| `AuthUnavailable` | Authorization could not be checked now; the stored state is unchanged | Try again later |
| `SecureStoreUnavailable` | No protected credential store on this system | Use in-process `login(session_only=True)`; CLI `--session-only` only verifies |
| `PermissionDenied` | The server refused access for this authorization (HTTP 403) | Contact the zenture account owner; logging in again does not widen access |
| `LoginCancelled` | The authorization was declined, cancelled or stopped | Nothing was connected; run the login again if you meant it |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | success (status: connected) |
| `1` | status: not_logged_in |
| `2` | invalid command line |
| `3` | authorization_required: log in again |
| `4` | unavailable: nothing changed; the message says whether retrying later helps |
| `5` | store_unavailable: no protected credential store (CLI `--session-only` only verifies) |
| `6` | login cancelled (denied or declined) |
| `7` | permission denied by the server |
| `130` | interrupted (Ctrl+C, also while waiting for a device login) |

Details: [`docs/authentication.md`](./docs/authentication.md) and
[`docs/mcp-client.md`](./docs/mcp-client.md).

## Classic API resources (secondary)

The sections below document the other REST resources: models, chat, input
wizard (prompt optimization), evaluations, account reads and operation polling.
They are independent of Runs and return Async Operations (`operation_id`)
rather than Runs; `.run(...)` on these resources polls to a terminal status.
Package names: distribution `zenture`, import package `zenture`, clients
`ZentureClient` and `AsyncZentureClient`, command line `zenture`. Full call
and response references: [`docs/sdk-call-reference.md`](./docs/sdk-call-reference.md),
[`docs/response-shapes.md`](./docs/response-shapes.md) and
[`docs/api-reference.md`](./docs/api-reference.md).

### Sync Quickstart

```python
from zenture import ZentureClient

with ZentureClient.from_env() as client:
    print(client.helloworld())

    models = client.models.list(mode="single")
    for model in models.models:
        print(model.id, model.display_name)
```

### Async Quickstart

```python
import asyncio

from zenture import AsyncZentureClient


async def main() -> None:
    async with AsyncZentureClient.from_env() as client:
        result = await client.chat.run(
            message="Summarize this support note.",
            mode="single",
            idempotency_key="case-123-chat-single-v1",
            timeout=120.0,
        )
        print(result.status)


if __name__ == "__main__":
    asyncio.run(main())
```

### Models

```python
from zenture import ZentureClient

with ZentureClient.from_env() as client:
    single_models = client.models.list(mode="single")
    multi_models = client.models.list(mode="multi")
    print(single_models.models[0].id)
    print(multi_models.models[0].id)
```

### Chat

Single-model chat:

```python
from zenture import ZentureClient

with ZentureClient.from_env() as client:
    available_models = [
        model.id for model in client.models.list(mode="single").models if model.is_available
    ]
    if not available_models:
        raise RuntimeError("No available single-mode model for this token.")

    result = client.chat.run(
        message="Summarize this customer update.",
        mode="single",
        model=available_models[0],
        idempotency_key="case-123-chat-single-v1",
        timeout=120.0,
    )
    print(result.operation_id, result.status)
    print(result.result.amount_billed)
    print(result.result.chat_id, result.result.turn_id, result.result.model_response_id)
```

Multi-model chat:

```python
from zenture import ZentureClient

with ZentureClient.from_env() as client:
    available_models = [
        model.id for model in client.models.list(mode="multi").models if model.is_available
    ]
    if len(available_models) < 2:
        raise RuntimeError("At least two available multi-mode models are required.")

    result = client.chat.run(
        message="Compare these draft answers for factual consistency.",
        mode="multi",
        models=available_models[:2],
        idempotency_key="case-123-chat-multi-v1",
        timeout=120.0,
    )
    print(result.status)
    print(result.result.amount_billed)
```

Agentic chat mode is not part of Public V1. Do not document or add public
helpers for it in this client.

Continue a chat with a follow-up turn:

```python
from zenture import ZentureClient
from zenture.idempotency import idempotency_key

with ZentureClient.from_env() as client:
    first = client.chat.run(
        message="Give me a concise onboarding checklist for a new API user.",
        mode="single",
        idempotency_key=idempotency_key("case-123", "chat-turn-1", "v1"),
        timeout=120.0,
    )
    chat_id = first.result.chat_id

    follow_up = client.chat.run(
        message="Turn that checklist into three implementation steps.",
        chat_id=chat_id,
        mode="single",
        idempotency_key=idempotency_key("case-123", "chat-turn-2", "v1"),
        timeout=120.0,
    )
    print(follow_up.result.amount_billed)
    print(follow_up.result.turn_id, follow_up.result.model_response_id)
```

Read chat turns when you need the exact `user_message`, `model_answer`, and
`model_response_id` for evaluation:

```python
from zenture import ZentureClient

with ZentureClient.from_env() as client:
    messages = client.chat.messages("chat_example")
    turn = messages.turns[0]
    print(turn.user_message, turn.model_answer, turn.model_response_id)
```

### Input Wizard

```python
from zenture import ZentureClient

with ZentureClient.from_env() as client:
    result = client.input_wizard.run(
        prompt="Improve this onboarding prompt for a support assistant.",
        idempotency_key="case-123-input-wizard-v1",
        timeout=120.0,
    )
    print(result.operation_id, result.status)
    if result.result and result.result.optimized_prompt:
        print(result.result.optimized_prompt)
```

### Evaluations

There are two evaluation flows. Keep them separate:

- **External evaluation:** the answer came from your application or another AI
  system. Send `user_message`, `ai_answer`, optional `external_id`, and optional
  `metadata`. Do not send `chat_id`, `turn_id`, or `model_response_id`.
- **Internal zenture chat evaluation:** the answer came from a zenture chat
  turn. Send `user_message`, `ai_answer`, and the AI-answer
  `model_response_id`. `chat_id` and `turn_id` are optional correlation fields,
  but if either is sent, `model_response_id` is required and must belong to the
  same zenture user.

External answer evaluation creates an external evaluation-only record. It does
not add the submitted content to normal zenture chat history. If the answer
contains sources, include them directly in `ai_answer` as Markdown links,
footnotes, or plain URLs:

```python
from zenture import ZentureClient
from zenture.idempotency import idempotency_key

with ZentureClient.from_env() as client:
    result = client.evaluations.run(
        user_message="What is zenture?",
        ai_answer=("zenture evaluates AI outputs. [Source](https://example.com/product-brief)"),
        external_id="support-ticket-123-answer-a",
        metadata={"source": "support_bot", "answer_format": "markdown_with_sources"},
        idempotency_key=idempotency_key("support-ticket-123-answer-a", "evaluate", "v1"),
        timeout=120.0,
    )
    print(result.operation_id, result.status)
    print(result.result.amount_billed)

    detail = client.evaluations.get(result.result.evaluation_id)
    print(detail.zenture_summary)
    print(detail.sources)
```

Internal zenture chat-answer evaluation uses the AI-answer `model_response_id`.
That id is not the user-message id. Passing only `chat_id` or `turn_id` is not
enough; the API rejects that request with `422 validation_failed` before it
creates an operation or checks credits.

The client also validates that shape locally. `chat_id` or `turn_id` without
`model_response_id` raises Pydantic `ValidationError` before an HTTP request is
sent. A valid-looking target that the API user does not own raises
`ZentureValidationError` from the API.

```python
from zenture import ZentureClient
from zenture.idempotency import idempotency_key
from pydantic import ValidationError
from zenture.errors import ZentureValidationError

with ZentureClient.from_env() as client:
    try:
        chat = client.chat.run(
            message="Draft three customer-support next steps.",
            mode="single",
            idempotency_key=idempotency_key("case-456", "chat-turn-1", "v1"),
            timeout=120.0,
        )
        chat_id = chat.result.chat_id
        turn_id = chat.result.turn_id
        model_response_id = chat.result.model_response_id or chat.result.model_response_ids[0]

        turn = next(item for item in client.chat.messages(chat_id).turns if item.turn_id == turn_id)

        evaluation = client.evaluations.run(
            user_message=turn.user_message,
            ai_answer=turn.model_answer,
            chat_id=chat_id,
            turn_id=turn_id,
            model_response_id=model_response_id,
            idempotency_key=idempotency_key(model_response_id, "evaluate", "v1"),
            timeout=120.0,
        )
        print(evaluation.result.evaluation_id, evaluation.status)
        print(evaluation.result.amount_billed)
    except ValidationError:
        # Local client validation, for example chat_id/turn_id without model_response_id.
        handle_invalid_evaluation_target()
    except ZentureValidationError as exc:
        # Server-side validation, for example a model_response_id not owned by this user.
        handle_api_validation_error(exc.status_code, exc.error_code, exc.request_id)
```

Use `external_id` only as optional caller-side correlation. Use
`idempotency_key` as the required retry-safety key for each mutating request.

### End-to-End Chat Evaluation

For a complete local smoke flow, use:

```bash
python3 examples/end_to_end_chat_evaluation.py
```

The script reads configuration from environment variables, calls `wallet.get()`,
selects an available single-model chat model with a Haiku preference, runs
`input_wizard`, chats, reads the generated turn, evaluates the answer, and
prints a JSON summary with per-operation `amount_billed` plus `total_billed`.

For smaller application code, `chat.run(..., include_content=True)` attaches
the matching public chat turn as `result.chat_turn`, and
`evaluations.run(..., include_detail=True)` attaches the public evaluation
detail as `result.evaluation`. These flags are explicit so normal operation
polling does not perform extra read requests.

### Account Reads

Read wallet, usage, and route limits without creating billable work:

```python
from zenture import ZentureClient

with ZentureClient.from_env() as client:
    wallet = client.wallet.get()
    api_usage = client.usage.get(scope="api")
    all_usage = client.usage.get(scope="all")
    limits = client.limits.get()

    print(wallet.plan, wallet.status, wallet.credits_available.amount)
    print(api_usage.operation_count, all_usage.operation_count)
    print(limits.operation_statuses)
```

### Operation Polling

Low-level create methods return an operation immediately. Use
`client.operations.wait(...)` when you want to poll explicitly.

```python
from zenture import ZentureClient

with ZentureClient.from_env() as client:
    operation = client.chat.create_operation(
        message="Review this response.",
        mode="single",
        idempotency_key="case-123-chat-create-v1",
    )
    final_operation = client.operations.wait(operation.operation_id, timeout=120.0)
    print(final_operation.status)
```

Terminal statuses are `succeeded`, `failed`, `cancelled`, and `expired`.

If `.run(...)` creates an operation and local polling later times out or is
stopped, the exception exposes `operation_id` and `idempotency_key` attributes.
Use `client.operations.get(exc.operation_id)` or retry with the same
`exc.idempotency_key`. Do not retry a billable mutation with a new key.

For a successful settled Product Run, the canonical status is `completed`.
`client.runs.list(status=["completed"])` selects that success category;
`succeeded` remains a deprecated list-filter input and a historical Run response
value. Async Operations still use `succeeded` for terminal success.

For public Runs, `client.runs.wait(run_id)` is always finite. When the first
response includes `deadline_at`, an omitted timeout ends at that deadline plus
the fixed 35-second recovery allowance and one polling interval. A caller
supplied finite timeout remains authoritative. The timeout exception includes
the last status and observed deadline as safe metadata. Run event streaming
remains an optional lower-latency path; `runs.wait(...)` is the bounded polling
fallback when a stream is unavailable.

### Pagination

List-style read helpers support `limit` and `cursor`. The default page size is
`limit=50`, the maximum is `100`, and cursors are opaque strings. Responses
include `next_cursor`; `None` means there is no further page.

```python
from zenture import ZentureClient

with ZentureClient.from_env() as client:
    page = client.chat.list(limit=50)
    print(page.next_cursor)

    for chat in client.chat.iter(limit=50):
        print(chat.chat_id)
```

Available iterators:

- `client.chat.iter(limit=50, cursor=None)`
- `client.chat.iter_messages(chat_id, limit=50, cursor=None)`
- `client.evaluations.iter(limit=50, cursor=None)`

### Idempotency

Mutating routes require `Idempotency-Key`. Use stable caller-owned keys that do
not contain prompts, answers, API tokens, customer PII, or request bodies.

```python
from zenture import ZentureClient
from zenture.idempotency import idempotency_key

with ZentureClient.from_env() as client:
    key = idempotency_key("case-123", "chat-turn-1", "v1")
    result = client.chat.run(
        message="Create a concise summary.",
        idempotency_key=key,
        timeout=120.0,
    )
    print(result.idempotency_key)
```

Example keys:

- `idempotency_key("case-123", "chat-turn-1", "v1")`
- `idempotency_key("case-123", "chat-turn-2", "v1")`
- `idempotency_key("support-ticket-123-answer-a", "evaluate", "v1")`
- `idempotency_key("response_abc123", "evaluate", "v1")`

### Errors

```python
from zenture import ZentureClient
from zenture.errors import (
    ZentureAPIError,
    ZentureInsufficientCreditsError,
    ZenturePollingTimeoutError,
    ZentureRateLimitError,
)

with ZentureClient.from_env() as client:
    try:
        result = client.chat.run(
            message="Summarize this incident.",
            idempotency_key="case-123-error-example-v1",
            timeout=120.0,
        )
        print(result.status)
    except ZenturePollingTimeoutError as exc:
        print(exc.operation_id)
    except ZentureInsufficientCreditsError:
        wallet = client.wallet.get()
        print(wallet.credits_available)
    except ZentureRateLimitError as exc:
        print(exc.retry_after)
    except ZentureAPIError as exc:
        print(exc.request_id)
```

Client exceptions redact sensitive content. Request and response bodies are not
included in exception strings.

### Timeout, Retry, Polling, and Rate Limits

- client-owned HTTP clients use explicit timeouts: connect `5s`,
  read/write/pool `30s`.
- `operations.wait(timeout=...)` and `.run(timeout=...)` use a total operation
  polling budget, not the raw HTTP read timeout.
- Polling uses deterministic intervals: `initial_interval=1s`, doubled up to
  `max_interval=8s`, with no jitter.
- Manual `GET /v1/operations/{operation_id}` polling should use the same
  `1s -> 2s -> 4s -> 8s` cadence, should not poll faster than once per second
  per operation, and must stop at terminal status.
- Retry default is `max_retries=2`.
- Retryable HTTP responses include `429`, `500`, `502`, `503`, and `504` when
  the public error code is retryable.
- `Retry-After` is honored before deterministic exponential backoff.
- Mutating requests are retried only when an `Idempotency-Key` is present.

### Base URL Policy

- Default production API origin: `https://api.zenture.app`
- Never derive `base_url` from user input.
- URL credentials, paths, query strings, fragments, and arbitrary HTTPS origins
  are rejected.

### Public V1 Scope

- No browser, mobile, or frontend bundle usage.
- No API-token management surface.
- No public helper for agentic chat mode in Public V1.
- No top-level exports from internal `_contract` modules.

## Local Verification

```bash
python3 -m ruff format --check .
python3 -m ruff check .
python3 -m mypy
python3 -m pyright
python3 -m pytest
python3 -m coverage run -m pytest
python3 -m coverage report
python3 -m build
python3 -m twine check dist/*
```

## Security

See [`SECURITY.md`](./SECURITY.md) for vulnerability reporting and security
expectations. Do not publish API tokens in issues, logs, screenshots, or support
requests.

## License

Apache License 2.0. See [`LICENSE`](./LICENSE).
