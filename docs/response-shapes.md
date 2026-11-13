<!-- Generated from OpenAPI. Do not edit manually. -->
# Response Shapes

This page documents sanitized request examples and raw zenture Public API response bodies.
The committed OpenAPI artifact remains the contract source of truth; this file is generated from that artifact for client documentation and reviewable downstream diffs.

## Conventions

- Timestamps are ISO-8601 strings with timezone information.
- `null` means the field is optional, unavailable, or intentionally absent.
- Credit amounts use display strings such as `{"amount": "123.45", "unit": "credits"}`.
- Operation statuses are `queued`, `running`, `succeeded`, `failed`, `cancelled`, and `expired`.
- Mutating async routes return `PublicOperationResponse`; client `.run(...)` helpers wrap terminal operations in `OperationRunResult`.
- `PublicOperationError.code` is a domain operation code string and is separate from gateway error-envelope codes.
- Rate-limit data is returned as HTTP headers, not in response bodies.
- Agentic chat is not a Public V1 mode and has no public client helper.

## Product Run interpretation

See the [Run guide](run-guide.md#interpret-the-returned-run) for current typed
client interpretation and the distinction between technical completion, acceptance,
result availability and Credits. Examples below illustrate wire shapes; use the
current models and guide for optional/additive fields. MCP `get_run()` wraps its
Run in `.run`, while REST `runs.get()` returns it directly.

## Endpoint Summary

| Method | Endpoint | Success | Client surface | Client model |
| --- | --- | --- | --- | --- |
| `POST` | `/v1/run-artifacts/signed-upload` | `200` | `client.runs.attach_artifact(...)` | `PublicSignedUploadResponse` |
| `PUT` | `/v1/run-artifacts/uploads/{upload_id}` | `202` | `client.runs.attach_artifact(...)` | `PublicUploadAcceptedResponse` |
| `GET` | `/v1/run-artifacts/{artifact_id}` | `200` | `httpx` direct call | `PublicArtifactStatusResponse` |
| `GET` | `/v1/runs` | `200` | `client.runs.list(...)` | `PublicRunCollectionResponse` |
| `POST` | `/v1/runs` | `200, 202` | `client.runs.create(...)`, `client.runs.run(...)` | `PublicRunResponse` |
| `POST` | `/v1/runs/prepare` | `200` | `client.runs.prepare(...)` | `PrepareRunResponse` |
| `GET` | `/v1/runs/{run_id}` | `200` | `client.runs.get(...)` | `PublicRunResponse` |
| `POST` | `/v1/runs/{run_id}/cancel` | `200` | `client.runs.cancel(...)` | `PublicRunResponse` |
| `GET` | `/v1/runs/{run_id}/events` | `200` | `client.runs.list_events(...)` | `PublicRunEventsResponse` |
| `GET` | `/v1/runs/{run_id}/events/stream` | `200` | `client.runs.iter_events(...)` | `string` |
| `POST` | `/v1/runs/{run_id}/outcome` | `200` | `client.runs.record_outcome(...)` | `PublicRunOutcomeResponse` |
| `POST` | `/v1/chat` | `202` | `client.chat.create(...)`, `client.chat.create_operation(...)`, `client.chat.run(...)` | `PublicOperationResponse`, `OperationRunResult` |
| `GET` | `/v1/chats` | `200` | `client.chat.list(...)`, `client.chat.iter(...)` | `PublicChatCollectionResponse` |
| `GET` | `/v1/chats/{chat_id}` | `200` | `client.chat.get(...)` | `PublicChatResponse` |
| `GET` | `/v1/chats/{chat_id}/messages` | `200` | `client.chat.messages(...)`, `client.chat.iter_messages(...)` | `PublicChatMessagesResponse` |
| `POST` | `/v1/evaluate` | `202` | `client.evaluations.create(...)`, `client.evaluations.run(...)` | `PublicOperationResponse`, `OperationRunResult` |
| `GET` | `/v1/evaluations` | `200` | `client.evaluations.list(...)`, `client.evaluations.iter(...)` | `PublicEvaluationCollectionResponse` |
| `GET` | `/v1/evaluations/{evaluation_id}` | `200` | `client.evaluations.get(...)` | `PublicEvaluationResponse` |
| `GET` | `/v1/helloworld` | `200` | `client.helloworld()` | `str` |
| `POST` | `/v1/input-wizard` | `202` | `client.input_wizard.create(...)`, `client.input_wizard.run(...)` | `PublicOperationResponse`, `OperationRunResult` |
| `GET` | `/v1/limits` | `200` | `client.limits.get()` | `LimitsResponse` |
| `GET` | `/v1/models` | `200` | `client.models.list(mode=None | "single" | "multi")` | `PublicModelListResponse` |
| `GET` | `/v1/operations/{operation_id}` | `200` | `client.operations.get(...)`, `client.operations.wait(...)` | `PublicOperationResponse` |
| `GET` | `/v1/standards` | `200` | `httpx` direct call | `AgentStandards` |
| `POST` | `/v1/standards` | `201` | `httpx` direct call | `AgentStandard` |
| `PATCH` | `/v1/standards/{standard_id}` | `200` | `httpx` direct call | `AgentStandard` |
| `GET` | `/v1/usage` | `200` | `client.usage.get(...)` | `PublicUsageResponse` |
| `GET` | `/v1/wallet` | `200` | `client.wallet.get()` | `PublicWalletResponse` |

## Shared Objects

### `PublicAmountBilled`

```json
{
  "amount": "123.45",
  "unit": "credits"
}
```

### `PublicOperationResponse`

`PublicOperationResponse.result` is either `null` or a bounded `PublicOperationResult`.

```json
{
  "operation_id": "op_example",
  "status": "queued",
  "result": null,
  "error": null
}
```

Terminal success example:

```json
{
  "operation_id": "op_example",
  "status": "succeeded",
  "result": {
    "result_type": "chat",
    "chat_id": "chat_example",
    "turn_id": "turn_example",
    "model_response_id": "response_example",
    "model_response_ids": [
      "response_example"
    ],
    "status": "succeeded",
    "completed_at": "2026-06-15T10:00:30Z",
    "amount_billed": {
      "amount": "123.45",
      "unit": "credits"
    }
  },
  "error": null
}
```

Terminal failure example:

```json
{
  "operation_id": "op_example",
  "status": "failed",
  "result": null,
  "error": {
    "code": "chat_execution_failed",
    "message": "Chat execution failed."
  }
}
```

### `PublicOperationResult`

```json
{
  "result_type": "chat",
  "chat_id": "chat_example",
  "turn_id": "turn_example",
  "model_response_id": "response_example",
  "model_response_ids": [
    "response_example"
  ],
  "evaluation_id": null,
  "resource_id": "chat_example",
  "status": "succeeded",
  "completed_at": "2026-06-15T10:00:30Z",
  "amount_billed": {
    "amount": "123.45",
    "unit": "credits"
  },
  "score": null,
  "target_kind": null
}
```

### `OperationRunResult`

`OperationRunResult` is client-only and is not returned as raw HTTP JSON.

```json
{
  "operation_id": "op_example",
  "status": "succeeded",
  "result": {
    "result_type": "chat",
    "chat_id": "chat_example",
    "turn_id": "turn_example",
    "model_response_id": "response_example",
    "model_response_ids": [
      "response_example"
    ],
    "amount_billed": {
      "amount": "123.45",
      "unit": "credits"
    }
  },
  "error": null,
  "chat_turn": null,
  "evaluation": null,
  "idempotency_key": "caller-owned-idempotency-key",
  "last_request_id": null
}
```

## Endpoint Details

### `POST /v1/run-artifacts/signed-upload`

Client surface: `client.runs.attach_artifact(...)`

Client model: `PublicSignedUploadResponse`

Auth mode: `api_token`

Scopes: `evaluation:run`

Idempotency: `required`

Request body schema: `SignedUploadRequest`

Request body example:

```json
{
  "byte_size": 1,
  "content_hash": "example",
  "file_name": "example",
  "mime_type": "example"
}
```

Response `200` as `application/json`:

Schema: `PublicSignedUploadResponse`

```json
{
  "artifact_ref": "example",
  "expires_at": "example",
  "upload_id": "example",
  "upload_token": "example",
  "upload_url": "example"
}
```

### `PUT /v1/run-artifacts/uploads/{upload_id}`

Client surface: `client.runs.attach_artifact(...)`

Client model: `PublicUploadAcceptedResponse`

Auth mode: `upload_token`

Scopes: `none`

Idempotency: `not required`

Request body schema: `string`

Request body example:

```json
"example"
```

Response `202` as `application/json`:

Schema: `PublicUploadAcceptedResponse`

```json
{
  "artifact_ref": "example",
  "next_step": "start_run",
  "retry_after_seconds": 1,
  "status": "pending"
}
```

### `GET /v1/run-artifacts/{artifact_id}`

Client surface: `httpx` direct call

Client model: `PublicArtifactStatusResponse`

Auth mode: `api_token`

Scopes: `evaluation:run`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicArtifactStatusResponse`

```json
{
  "artifact_id": "example",
  "char_count": 1,
  "expires_at": "example",
  "media_type": "example",
  "retry_after_seconds": 1,
  "skipped_images": 1,
  "status": "pending"
}
```

### `GET /v1/runs`

Client surface: `client.runs.list(...)`

Client model: `PublicRunCollectionResponse`

Auth mode: `api_token`

Scopes: `evaluation:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicRunCollectionResponse`

```json
{
  "has_more": true,
  "next_cursor": "cursor_next",
  "runs": [
    {
      "created_at": "2026-06-15T10:00:00Z",
      "deadline_at": "example",
      "decision": "ready",
      "error_code": "example",
      "input_kind": "text",
      "profile": "fast",
      "reference_file_attached": true,
      "run_id": "example",
      "status": "active",
      "task_summary_ref": "example",
      "title": "example",
      "updated_at": "2026-06-15T10:00:30Z"
    }
  ]
}
```

### `POST /v1/runs`

Client surface: `client.runs.create(...)`, `client.runs.run(...)`

Client model: `PublicRunResponse`

Auth mode: `api_token`

Scopes: `evaluation:run`

Idempotency: `required`

Request body schema: `object`

Request body example:

```json
{
  "artifact": "example",
  "learning_context": "private",
  "predecessor_run_id": "example",
  "profile": "fast",
  "reference_file": {
    "type": "zenture_ref",
    "value": "example"
  },
  "standards": "organization",
  "task": "example"
}
```

Response `200` as `application/json`:

Schema: `PublicRunResponse`

```json
{
  "acceptance_decision": "ready",
  "artifact_refs": [
    "example"
  ],
  "billing_summary": {
    "final_credits": "example",
    "schema_version": "run.terminal_billing_summary.v1",
    "status": "pending"
  },
  "cancellation_requested": true,
  "capability_coverage": {
    "available_refs": [
      "example"
    ],
    "limitation_refs": [
      "example"
    ],
    "unavailable_refs": [
      "example"
    ]
  },
  "completed_at": "2026-06-15T10:00:30Z",
  "created_at": "2026-06-15T10:00:00Z",
  "deadline_at": "example",
  "essence": "example",
  "essence_scope": "personal",
  "essence_version": "example",
  "event_cursor": "example",
  "family": "knowledge",
  "generation": 1,
  "input_kind": "text",
  "learning_applied": "example",
  "learning_context": "private",
  "limitations": [
    "example"
  ],
  "next_action": "example",
  "note": "learning_context_unavailable",
  "phase": "preparing",
  "profile": "fast",
  "queue": {
    "estimate_as_of": "example",
    "estimated_completion_seconds": "example",
    "estimated_start_seconds": "example",
    "jobs_ahead": 1,
    "queue_reason": "example"
  },
  "queue_expires_at": "example",
  "reason_code": "example",
  "reference_file_attached": true,
  "result": "pending",
  "retry_after_seconds": "example",
  "run_id": "example",
  "run_insight_ref": "example",
  "safe_result_content": "example",
  "standards_checked": {
    "results": [
      "example"
    ],
    "set_hash": "example"
  },
  "started_at": "example",
  "status": "created",
  "task_contract_summary": {
    "requirement_count": 1,
    "summary_ref": "example",
    "work_type": "example"
  },
  "technical_status": "complete",
  "updated_at": "2026-06-15T10:00:30Z",
  "work_type": "example"
}
```

Response `202` as `application/json`:

Schema: `PublicRunResponse`

```json
{
  "acceptance_decision": "ready",
  "artifact_refs": [
    "example"
  ],
  "billing_summary": {
    "final_credits": "example",
    "schema_version": "run.terminal_billing_summary.v1",
    "status": "pending"
  },
  "cancellation_requested": true,
  "capability_coverage": {
    "available_refs": [
      "example"
    ],
    "limitation_refs": [
      "example"
    ],
    "unavailable_refs": [
      "example"
    ]
  },
  "completed_at": "2026-06-15T10:00:30Z",
  "created_at": "2026-06-15T10:00:00Z",
  "deadline_at": "example",
  "essence": "example",
  "essence_scope": "personal",
  "essence_version": "example",
  "event_cursor": "example",
  "family": "knowledge",
  "generation": 1,
  "input_kind": "text",
  "learning_applied": "example",
  "learning_context": "private",
  "limitations": [
    "example"
  ],
  "next_action": "example",
  "note": "learning_context_unavailable",
  "phase": "preparing",
  "profile": "fast",
  "queue": {
    "estimate_as_of": "example",
    "estimated_completion_seconds": "example",
    "estimated_start_seconds": "example",
    "jobs_ahead": 1,
    "queue_reason": "example"
  },
  "queue_expires_at": "example",
  "reason_code": "example",
  "reference_file_attached": true,
  "result": "pending",
  "retry_after_seconds": "example",
  "run_id": "example",
  "run_insight_ref": "example",
  "safe_result_content": "example",
  "standards_checked": {
    "results": [
      "example"
    ],
    "set_hash": "example"
  },
  "started_at": "example",
  "status": "created",
  "task_contract_summary": {
    "requirement_count": 1,
    "summary_ref": "example",
    "work_type": "example"
  },
  "technical_status": "complete",
  "updated_at": "2026-06-15T10:00:30Z",
  "work_type": "example"
}
```

### `POST /v1/runs/prepare`

Client surface: `client.runs.prepare(...)`

Client model: `PrepareRunResponse`

Auth mode: `api_token`

Scopes: `evaluation:run`

Idempotency: `required`

Request body schema: `PrepareRunRequest`

Request body example:

```json
{
  "artifact": {
    "type": "example",
    "value": "example"
  },
  "learning_context": "private",
  "profile": "fast",
  "reference_file": {
    "type": "zenture_ref",
    "value": "example"
  },
  "standards": "organization",
  "task": "example"
}
```

Response `200` as `application/json`:

Schema: `PrepareRunResponse`

```json
{
  "billing_projection": {
    "estimated_credits": "example",
    "maximum_credits": "example",
    "schema_version": "run.prepare_credits_projection.v1"
  },
  "estimated_credits": "example",
  "expected_duration_seconds": 1,
  "expires_at": "example",
  "guest_slot_cost": "example",
  "inferred_work_type": "example",
  "maximum_credits": "example",
  "planned_checks": [
    "example"
  ],
  "proposal_hash": "example",
  "proposal_id": "example",
  "proposal_version": 1,
  "start_admissible": true,
  "task_contract_summary": {
    "requirement_count": 1,
    "summary_ref": "example",
    "work_type": "example"
  },
  "unavailable_checks": [
    "example"
  ]
}
```

### `GET /v1/runs/{run_id}`

Client surface: `client.runs.get(...)`

Client model: `PublicRunResponse`

Auth mode: `api_token`

Scopes: `evaluation:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicRunResponse`

```json
{
  "acceptance_decision": "ready",
  "artifact_refs": [
    "example"
  ],
  "billing_summary": {
    "final_credits": "example",
    "schema_version": "run.terminal_billing_summary.v1",
    "status": "pending"
  },
  "cancellation_requested": true,
  "capability_coverage": {
    "available_refs": [
      "example"
    ],
    "limitation_refs": [
      "example"
    ],
    "unavailable_refs": [
      "example"
    ]
  },
  "completed_at": "2026-06-15T10:00:30Z",
  "created_at": "2026-06-15T10:00:00Z",
  "deadline_at": "example",
  "essence": "example",
  "essence_scope": "personal",
  "essence_version": "example",
  "event_cursor": "example",
  "family": "knowledge",
  "generation": 1,
  "input_kind": "text",
  "learning_applied": "example",
  "learning_context": "private",
  "limitations": [
    "example"
  ],
  "next_action": "example",
  "note": "learning_context_unavailable",
  "phase": "preparing",
  "profile": "fast",
  "queue": {
    "estimate_as_of": "example",
    "estimated_completion_seconds": "example",
    "estimated_start_seconds": "example",
    "jobs_ahead": 1,
    "queue_reason": "example"
  },
  "queue_expires_at": "example",
  "reason_code": "example",
  "reference_file_attached": true,
  "result": "pending",
  "retry_after_seconds": "example",
  "run_id": "example",
  "run_insight_ref": "example",
  "safe_result_content": "example",
  "standards_checked": {
    "results": [
      "example"
    ],
    "set_hash": "example"
  },
  "started_at": "example",
  "status": "created",
  "task_contract_summary": {
    "requirement_count": 1,
    "summary_ref": "example",
    "work_type": "example"
  },
  "technical_status": "complete",
  "updated_at": "2026-06-15T10:00:30Z",
  "work_type": "example"
}
```

### `POST /v1/runs/{run_id}/cancel`

Client surface: `client.runs.cancel(...)`

Client model: `PublicRunResponse`

Auth mode: `api_token`

Scopes: `evaluation:run`

Idempotency: `required`

Request body schema: `CancelRunRequest`

Request body example:

```json
{
  "reason": "user_requested"
}
```

Response `200` as `application/json`:

Schema: `PublicRunResponse`

```json
{
  "acceptance_decision": "ready",
  "artifact_refs": [
    "example"
  ],
  "billing_summary": {
    "final_credits": "example",
    "schema_version": "run.terminal_billing_summary.v1",
    "status": "pending"
  },
  "cancellation_requested": true,
  "capability_coverage": {
    "available_refs": [
      "example"
    ],
    "limitation_refs": [
      "example"
    ],
    "unavailable_refs": [
      "example"
    ]
  },
  "completed_at": "2026-06-15T10:00:30Z",
  "created_at": "2026-06-15T10:00:00Z",
  "deadline_at": "example",
  "essence": "example",
  "essence_scope": "personal",
  "essence_version": "example",
  "event_cursor": "example",
  "family": "knowledge",
  "generation": 1,
  "input_kind": "text",
  "learning_applied": "example",
  "learning_context": "private",
  "limitations": [
    "example"
  ],
  "next_action": "example",
  "note": "learning_context_unavailable",
  "phase": "preparing",
  "profile": "fast",
  "queue": {
    "estimate_as_of": "example",
    "estimated_completion_seconds": "example",
    "estimated_start_seconds": "example",
    "jobs_ahead": 1,
    "queue_reason": "example"
  },
  "queue_expires_at": "example",
  "reason_code": "example",
  "reference_file_attached": true,
  "result": "pending",
  "retry_after_seconds": "example",
  "run_id": "example",
  "run_insight_ref": "example",
  "safe_result_content": "example",
  "standards_checked": {
    "results": [
      "example"
    ],
    "set_hash": "example"
  },
  "started_at": "example",
  "status": "created",
  "task_contract_summary": {
    "requirement_count": 1,
    "summary_ref": "example",
    "work_type": "example"
  },
  "technical_status": "complete",
  "updated_at": "2026-06-15T10:00:30Z",
  "work_type": "example"
}
```

### `GET /v1/runs/{run_id}/events`

Client surface: `client.runs.list_events(...)`

Client model: `PublicRunEventsResponse`

Auth mode: `api_token`

Scopes: `evaluation:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicRunEventsResponse`

```json
{
  "events": [
    {
      "estimated_completion_seconds": {
        "max": "example",
        "min": "example"
      },
      "estimated_start_seconds": {
        "max": "example",
        "min": "example"
      },
      "event_cursor": "example",
      "event_id": "example",
      "jobs_ahead": "example",
      "message_key": "example",
      "progress_percent": "example",
      "run_id": "example",
      "sequence": 1,
      "status": "queued",
      "terminal_refs": [
        "example"
      ],
      "type": "run.event"
    }
  ],
  "has_more": true,
  "next_cursor": "cursor_next"
}
```

### `GET /v1/runs/{run_id}/events/stream`

Client surface: `client.runs.iter_events(...)`

Client model: `string`

Auth mode: `api_token`

Scopes: `evaluation:read`

Idempotency: `not required`

Request body: none

Response `200` as `text/event-stream`:

Schema: `string`

```markdown
example
```

### `POST /v1/runs/{run_id}/outcome`

Client surface: `client.runs.record_outcome(...)`

Client model: `PublicRunOutcomeResponse`

Auth mode: `api_token`

Scopes: `evaluation:run`

Idempotency: `required`

Request body schema: `RunOutcomeRequest`

Request body example:

```json
{
  "edited_artifact_ref": "example",
  "finding_adjudications": [
    {
      "finding_ref": "example",
      "outcome": "confirmed"
    }
  ],
  "outcome": "used"
}
```

Response `200` as `application/json`:

Schema: `PublicRunOutcomeResponse`

```json
{
  "acceptance_decision": "ready",
  "artifact_refs": [
    "example"
  ],
  "billing_summary": {
    "final_credits": "example",
    "schema_version": "run.terminal_billing_summary.v1",
    "status": "pending"
  },
  "cancellation_requested": true,
  "capability_coverage": {
    "available_refs": [
      "example"
    ],
    "limitation_refs": [
      "example"
    ],
    "unavailable_refs": [
      "example"
    ]
  },
  "completed_at": "2026-06-15T10:00:30Z",
  "created_at": "2026-06-15T10:00:00Z",
  "deadline_at": "example",
  "essence": "example",
  "essence_scope": "personal",
  "essence_version": "example",
  "event_cursor": "example",
  "family": "knowledge",
  "generation": 1,
  "input_kind": "text",
  "learning_applied": "example",
  "learning_context": "private",
  "limitations": [
    "example"
  ],
  "next_action": "example",
  "note": "learning_context_unavailable",
  "phase": "preparing",
  "profile": "fast",
  "queue": {
    "estimate_as_of": "example",
    "estimated_completion_seconds": "example",
    "estimated_start_seconds": "example",
    "jobs_ahead": 1,
    "queue_reason": "example"
  },
  "queue_expires_at": "example",
  "reason_code": "example",
  "reference_file_attached": true,
  "result": "pending",
  "retry_after_seconds": "example",
  "run_id": "example",
  "run_insight_ref": "example",
  "safe_result_content": "example",
  "standards_checked": {
    "results": [
      "example"
    ],
    "set_hash": "example"
  },
  "started_at": "example",
  "status": "created",
  "task_contract_summary": {
    "requirement_count": 1,
    "summary_ref": "example",
    "work_type": "example"
  },
  "technical_status": "complete",
  "updated_at": "2026-06-15T10:00:30Z",
  "work_type": "example"
}
```

### `POST /v1/chat`

Client surface: `client.chat.create(...)`, `client.chat.create_operation(...)`, `client.chat.run(...)`

Client model: `PublicOperationResponse`, `OperationRunResult`

Auth mode: `api_token`

Scopes: `chat:write`

Idempotency: `required`

Request body schema: `ChatRequest`

Request body example:

```json
{
  "message": "Summarize this support update.",
  "mode": "single"
}
```

Response `202` as `application/json`:

Schema: `PublicOperationResponse`

```json
{
  "operation_id": "op_example",
  "status": "queued",
  "result": null,
  "error": null
}
```

### `GET /v1/chats`

Client surface: `client.chat.list(...)`, `client.chat.iter(...)`

Client model: `PublicChatCollectionResponse`

Auth mode: `api_token`

Scopes: `chat:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicChatCollectionResponse`

```json
{
  "chats": [
    {
      "chat_id": "chat_example",
      "created_at": null,
      "title": null,
      "updated_at": null
    }
  ],
  "next_cursor": null
}
```

### `GET /v1/chats/{chat_id}`

Client surface: `client.chat.get(...)`

Client model: `PublicChatResponse`

Auth mode: `api_token`

Scopes: `chat:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicChatResponse`

```json
{
  "chat": {
    "chat_id": "chat_example",
    "created_at": null,
    "title": null,
    "updated_at": null
  },
  "latest_turns": [
    {
      "created_at": null,
      "model_answer": "example",
      "model_response_id": null,
      "model_response_ids": [
        "example"
      ],
      "turn_id": "turn_example",
      "user_message": "How should we respond?"
    }
  ]
}
```

### `GET /v1/chats/{chat_id}/messages`

Client surface: `client.chat.messages(...)`, `client.chat.iter_messages(...)`

Client model: `PublicChatMessagesResponse`

Auth mode: `api_token`

Scopes: `chat:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicChatMessagesResponse`

```json
{
  "chat_id": "chat_example",
  "next_cursor": null,
  "turns": [
    {
      "created_at": null,
      "model_answer": "example",
      "model_response_id": null,
      "model_response_ids": [
        "example"
      ],
      "turn_id": "turn_example",
      "user_message": "How should we respond?"
    }
  ]
}
```

### `POST /v1/evaluate`

Client surface: `client.evaluations.create(...)`, `client.evaluations.run(...)`

Client model: `PublicOperationResponse`, `OperationRunResult`

Auth mode: `api_token`

Scopes: `evaluation:run`

Idempotency: `required`

Request body schema: `EvaluateRequest`

Request body example:

```json
{
  "user_message": "How should we respond?",
  "ai_answer": "Offer a concise next step.",
  "external_id": "case-123"
}
```

Response `202` as `application/json`:

Schema: `PublicOperationResponse`

```json
{
  "operation_id": "op_example",
  "status": "queued",
  "result": null,
  "error": null
}
```

### `GET /v1/evaluations`

Client surface: `client.evaluations.list(...)`, `client.evaluations.iter(...)`

Client model: `PublicEvaluationCollectionResponse`

Auth mode: `api_token`

Scopes: `evaluation:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicEvaluationCollectionResponse`

```json
{
  "evaluations": [
    {
      "amount_billed": "example",
      "created_at": null,
      "evaluation_id": "eval_example",
      "results": null,
      "score": null,
      "sources": null,
      "status": "active",
      "zenture_kpi_details": null,
      "zenture_suggestion": null,
      "zenture_summary": null
    }
  ],
  "next_cursor": null
}
```

### `GET /v1/evaluations/{evaluation_id}`

Client surface: `client.evaluations.get(...)`

Client model: `PublicEvaluationResponse`

Auth mode: `api_token`

Scopes: `evaluation:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicEvaluationResponse`

```json
{
  "amount_billed": {
    "amount": "123.45",
    "unit": "credits"
  },
  "created_at": null,
  "evaluation_id": "eval_example",
  "results": null,
  "score": null,
  "sources": null,
  "status": "active",
  "zenture_kpi_details": null,
  "zenture_suggestion": null,
  "zenture_summary": null
}
```

### `GET /v1/helloworld`

Client surface: `client.helloworld()`

Client model: `str`

Auth mode: `none`

Scopes: `none`

Idempotency: `not required`

Request body: none

Response `200` as `text/markdown`:

Schema: `string`

```markdown
# zenture Public API

Base URL: `https://api.zenture.app/v1`

Developer docs: `https://www.zenture.app/en/developers`

Python client (`python -m pip install --upgrade zenture==1.2.1`): [zenture-development/zenture-client](https://github.com/zenture-development/zenture-client)
```

### `POST /v1/input-wizard`

Client surface: `client.input_wizard.create(...)`, `client.input_wizard.run(...)`

Client model: `PublicOperationResponse`, `OperationRunResult`

Auth mode: `api_token`

Scopes: `input_wizard:run`

Idempotency: `required`

Request body schema: `InputWizardRequest`

Request body example:

```json
{
  "mode": "prompt_improvement",
  "prompt": "Draft a customer-facing answer from these notes."
}
```

Response `202` as `application/json`:

Schema: `PublicOperationResponse`

```json
{
  "operation_id": "op_example",
  "status": "queued",
  "result": null,
  "error": null
}
```

### `GET /v1/limits`

Client surface: `client.limits.get()`

Client model: `LimitsResponse`

Auth mode: `api_token`

Scopes: `rate_limits:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `LimitsResponse`

```json
{
  "operation_statuses": [
    "example"
  ],
  "routes": {}
}
```

### `GET /v1/models`

Client surface: `client.models.list(mode=None | "single" | "multi")`

Client model: `PublicModelListResponse`

Auth mode: `api_token`

Scopes: `models:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicModelListResponse`

```json
{
  "models": [
    {
      "id": "model_public_single",
      "display_name": "Public Single",
      "modes": [
        "single"
      ],
      "capabilities": [
        "chat"
      ],
      "is_default": true,
      "is_available": true,
      "cost_class": "standard",
      "provider_display_name": "Example Provider",
      "max_input_tokens": 8192
    }
  ]
}
```

### `GET /v1/operations/{operation_id}`

Client surface: `client.operations.get(...)`, `client.operations.wait(...)`

Client model: `PublicOperationResponse`

Auth mode: `api_token`

Scopes: `none`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicOperationResponse`

```json
{
  "operation_id": "op_example",
  "status": "succeeded",
  "result": null,
  "error": null
}
```

### `GET /v1/standards`

Client surface: `httpx` direct call

Client model: `AgentStandards`

Auth mode: `api_token`

Scopes: `evaluation:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `AgentStandards`

```json
{
  "limit": 8,
  "standards": [
    {
      "active": true,
      "criterion": "example",
      "editable": true,
      "form": "written",
      "owner": "user",
      "restorable_versions": [
        "example"
      ],
      "standard_id": "example",
      "strength": "must",
      "suggested_criterion": null,
      "task_types": [
        "example"
      ],
      "text": "example",
      "version": 1
    }
  ]
}
```

### `POST /v1/standards`

Client surface: `httpx` direct call

Client model: `AgentStandard`

Auth mode: `api_token`

Scopes: `evaluation:run`

Idempotency: `required`

Request body schema: `DefineStandardRequest`

Request body example:

```json
{
  "criterion": "example",
  "owner": "user",
  "strength": "must",
  "task_types": [
    "facts_with_sources"
  ],
  "text": "example"
}
```

Response `201` as `application/json`:

Schema: `AgentStandard`

```json
{
  "active": true,
  "criterion": "example",
  "editable": true,
  "form": "written",
  "owner": "user",
  "restorable_versions": [
    1
  ],
  "standard_id": "example",
  "strength": "must",
  "suggested_criterion": null,
  "task_types": [
    "facts_with_sources"
  ],
  "text": "example",
  "version": 1
}
```

### `PATCH /v1/standards/{standard_id}`

Client surface: `httpx` direct call

Client model: `AgentStandard`

Auth mode: `api_token`

Scopes: `evaluation:run`

Idempotency: `required`

Request body schema: `EditStandardRequest`

Request body example:

```json
{
  "active": true,
  "criterion": "example",
  "expected_version": 1,
  "restore_version": 1,
  "strength": "must",
  "task_types": [
    "facts_with_sources"
  ],
  "text": "example",
  "use_suggested_criterion": true
}
```

Response `200` as `application/json`:

Schema: `AgentStandard`

```json
{
  "active": true,
  "criterion": "example",
  "editable": true,
  "form": "written",
  "owner": "user",
  "restorable_versions": [
    1
  ],
  "standard_id": "example",
  "strength": "must",
  "suggested_criterion": null,
  "task_types": [
    "facts_with_sources"
  ],
  "text": "example",
  "version": 1
}
```

### `GET /v1/usage`

Client surface: `client.usage.get(...)`

Client model: `PublicUsageResponse`

Auth mode: `api_token`

Scopes: `usage:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicUsageResponse`

```json
{
  "operation_count": 1,
  "scope": "api"
}
```

### `GET /v1/wallet`

Client surface: `client.wallet.get()`

Client model: `PublicWalletResponse`

Auth mode: `api_token`

Scopes: `wallet:read`

Idempotency: `not required`

Request body: none

Response `200` as `application/json`:

Schema: `PublicWalletResponse`

```json
{
  "credits_available": {
    "amount": "123.45",
    "unit": "credits"
  },
  "current_period_end": null,
  "plan": "free",
  "status": "active"
}
```

## Error Responses

Failed HTTP responses use a public error envelope:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "The request did not match the public API contract."
  },
  "request_id": "req_example"
}
```

Run and artifact operations accept `X-Zenture-Error-Details: issues` to request safe validation details. Missing or unknown header values preserve the coarse envelope. The header changes only error representation; successful responses, authorization, admission, idempotency and retry behavior are unchanged.

When available, `error.issues` contains 1–20 deduplicated entries. Each has a JSON Pointer `path` to a public argument and a closed `category`; optional `constraints` describe public bounds or allowed values. Input values, unknown key names and validator context are excluded. Details are omitted when unavailable, never null or an empty array.

Example of a Run prepare error when details are requested:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "The request is invalid.",
    "issues": [
      {
        "path": "/task",
        "category": "required"
      }
    ]
  },
  "request_id": "req_00000000000000000000000000000000"
}
```

Stable public gateway error codes are:

- `unauthorized`
- `forbidden`
- `rate_limited`
- `validation_failed`
- `missing_idempotency_key`
- `insufficient_credits`
- `dependency_unavailable`
- `capacity_unavailable`
- `internal_error`
- `idempotency_conflict`
- `operation_expired`
- `proposal_expired`
- `proposal_hash_mismatch`
- `predecessor_run_invalid`
- `account_required`
- `legal_consent_required`
- `artifact_required`
- `artifact_ambiguous`
- `artifact_unavailable`
- `artifact_not_found`
- `artifact_expired`
- `artifact_type_unsupported`
- `artifact_processing_unavailable`
- `artifact_not_ready`
- `artifact_too_large`
- `artifact_extract_failed`
- `artifact_quota_exceeded`
- `length_required`
- `prepare_rate_limited`
- `prepare_capacity_unavailable`
- `too_many_outstanding_runs`
- `capacity_temporarily_unavailable`
- `maintenance_active`
- `engine_unavailable_timeout`
- `capability_unavailable`
- `run_input_not_processable`
- `run_input_contains_contact_data`
- `run_not_found`
- `run_terminal`
- `cancel_conflict`
- `budget_ceiling_exceeded`
- `execution_failed`
- `guest_quota_exhausted`
- `price_ceiling_exceeded`
- `result_unavailable`
- `standard_not_found`
- `standard_forbidden`
- `standard_version_conflict`
- `standard_duplicate`
- `standard_invalid`
- `standard_limit`
- `standard_not_checkable`
- `standards_unavailable`

The zenture client maps known public error codes to typed exceptions where available and keeps future unknown safe error codes as `ZentureAPIError` without exposing API tokens, bearer headers, prompts, or other secrets in exception strings.
