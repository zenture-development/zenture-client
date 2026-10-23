"""Internal contract model behavior and OpenAPI drift checks."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import BaseModel, ValidationError

import zenture

OPENAPI_PATH = (
    Path(__file__).resolve().parents[3] / "openapi" / "zenture-public-api-v1.openapi.json"
)


def _schemas() -> dict[str, Any]:
    raw_contract = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw_contract, dict)
    contract = cast("dict[str, Any]", raw_contract)
    components = contract["components"]
    assert isinstance(components, dict)
    typed_components = cast("dict[str, Any]", components)
    schemas = typed_components["schemas"]
    assert isinstance(schemas, dict)
    return cast("dict[str, Any]", schemas)


def _contract() -> dict[str, Any]:
    contract = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    assert isinstance(contract, dict)
    return cast("dict[str, Any]", contract)


def test_contract_models_are_internal_not_top_level_exports() -> None:
    assert "PublicOperationResponse" not in zenture.__all__
    assert "ChatRequest" not in zenture.__all__


def test_contract_enums_match_openapi_exactly() -> None:
    from zenture._contract import ModelMode, OperationStatus, PublicErrorCode

    schemas = _schemas()
    operation_status = schemas["OperationStatus"]
    public_error_code = schemas["PublicErrorCode"]
    assert isinstance(operation_status, dict)
    assert isinstance(public_error_code, dict)

    assert [status.value for status in OperationStatus] == operation_status["enum"]
    assert [code.value for code in PublicErrorCode] == public_error_code["enum"]
    assert PublicErrorCode.MISSING_IDEMPOTENCY_KEY.value == "missing_idempotency_key"
    assert [mode.value for mode in ModelMode] == schemas["ModelMode"]["enum"]
    assert schemas["ChatRequest"]["properties"]["mode"]["allOf"] == [
        {"$ref": "#/components/schemas/ModelMode"}
    ]
    assert "agentic" not in {mode.value for mode in ModelMode}


def test_public_operation_result_is_bounded_and_strict() -> None:
    from zenture._contract import OperationStatus, PublicOperationResult

    schema = PublicOperationResult.model_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["result_type"]

    result = PublicOperationResult(
        result_type="chat",
        chat_id="chat_abc123",
        model_response_ids=("response_123",),
        status=OperationStatus.SUCCEEDED,
    )

    assert isinstance(result, BaseModel)
    assert result.result_type == "chat"

    from_json = PublicOperationResult.model_validate(
        {
            "result_type": "chat",
            "chat_id": "chat_abc123",
            "completed_at": "2026-06-15T12:00:00Z",
            "model_response_id": "response_123",
            "model_response_ids": ["response_123"],
            "status": "succeeded",
        }
    )
    assert from_json.status is OperationStatus.SUCCEEDED
    assert from_json.completed_at == datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    assert from_json.model_response_ids == ("response_123",)

    with pytest.raises(ValidationError):
        PublicOperationResult.model_validate({"result_type": "chat", "unexpected": True})
    with pytest.raises(ValidationError):
        PublicOperationResult.model_validate({"result_type": "chat", "completed_at": "not-a-date"})


def test_public_operation_response_matches_contract_shape() -> None:
    from zenture._contract import (
        OperationStatus,
        PublicOperationError,
        PublicOperationResponse,
        PublicOperationResult,
    )

    response = PublicOperationResponse(
        operation_id="op_abc123",
        status=OperationStatus.SUCCEEDED,
        result=PublicOperationResult(result_type="evaluation", evaluation_id="eval_abc123"),
    )

    assert response.operation_id == "op_abc123"
    assert response.result is not None

    from_json = PublicOperationResponse.model_validate(
        {"operation_id": "op_abc123", "status": "queued"}
    )
    assert from_json.status is OperationStatus.QUEUED

    failed = PublicOperationResponse.model_validate(
        {
            "operation_id": "op_abc123",
            "status": "failed",
            "error": {
                "code": "chat_execution_failed",
                "message": "Chat execution failed.",
            },
        }
    )
    assert failed.status is OperationStatus.FAILED
    assert isinstance(failed.error, PublicOperationError)
    assert failed.error.code == "chat_execution_failed"

    with pytest.raises(ValidationError):
        PublicOperationResponse(operation_id="bad", status=OperationStatus.QUEUED)


def test_public_error_envelope_requires_known_error_code_and_request_id() -> None:
    from zenture._contract import PublicError, PublicErrorCode, PublicErrorEnvelope

    envelope = PublicErrorEnvelope(
        error=PublicError(
            code=PublicErrorCode.MISSING_IDEMPOTENCY_KEY,
            message="Public gateway error",
        ),
        request_id="req_00000000000000000000000000000000",
    )

    assert envelope.error.code is PublicErrorCode.MISSING_IDEMPOTENCY_KEY
    from_json = PublicErrorEnvelope.model_validate(
        {
            "error": {"code": "validation_failed", "message": "x"},
            "request_id": "req_00000000000000000000000000000000",
        }
    )
    assert from_json.error.code is PublicErrorCode.VALIDATION_FAILED

    with pytest.raises(ValidationError):
        PublicErrorEnvelope.model_validate(
            {"error": {"code": PublicErrorCode.VALIDATION_FAILED, "message": "x"}}
        )
    with pytest.raises(ValidationError):
        PublicError.model_validate({"code": "unknown_code", "message": "x"})


def test_mutation_request_models_are_strict_and_match_required_fields() -> None:
    from zenture._contract import ChatRequest, EvaluateRequest, InputWizardRequest, ModelMode

    assert ChatRequest(message="hello").message == "hello"
    assert ChatRequest(message="hello").mode is ModelMode.SINGLE
    assert ChatRequest(message="hello", mode=ModelMode.SINGLE, model="default-model").model == (
        "default-model"
    )
    assert ChatRequest.model_validate(
        {"message": "hello", "mode": "multi", "models": ["model-a", "model-b"]}
    ).models == ("model-a", "model-b")
    assert EvaluateRequest(user_message="question", ai_answer="answer").ai_answer == "answer"
    assert EvaluateRequest(
        user_message="question",
        ai_answer="answer",
        external_id="customer-eval-123",
        metadata={"customer_id": "safe-correlation"},
    ).metadata == {"customer_id": "safe-correlation"}
    assert (
        EvaluateRequest(
            user_message="question",
            ai_answer="answer",
            chat_id="chat_12345678",
            turn_id="turn_123",
            model_response_id="response_123",
        ).model_response_id
        == "response_123"
    )
    assert InputWizardRequest(mode="prompt_improvement", prompt="make this better").mode == (
        "prompt_improvement"
    )

    with pytest.raises(ValidationError):
        ChatRequest(message="")
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"message": "hello", "extra_field": True})
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"message": "hello", "mode": "single", "models": ["model-a"]})
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"message": "hello", "mode": "multi"})
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {
                "message": "hello",
                "mode": "multi",
                "model": "model-a",
                "models": ["model-b"],
            }
        )
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {"message": "hello", "mode": "multi", "models": ["model-a", "model-a"]}
        )
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"message": "hello", "mode": "multi", "models": [""]})
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"message": "hello", "mode": "multi", "models": ["m" * 141]})
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"message": "hello", "mode": "agentic"})
    with pytest.raises(ValidationError):
        EvaluateRequest.model_validate({"user_message": "question"})
    with pytest.raises(ValidationError):
        EvaluateRequest.model_validate(
            {
                "user_message": "question",
                "ai_answer": "answer",
                "chat_id": "chat_12345678",
            }
        )
    with pytest.raises(ValidationError):
        EvaluateRequest.model_validate(
            {
                "user_message": "question",
                "ai_answer": "answer",
                "model_response_id": "response_",
            }
        )
    with pytest.raises(ValidationError):
        EvaluateRequest.model_validate(
            {
                "user_message": "question",
                "ai_answer": "answer",
                "external_id": "x" * 256,
            }
        )
    with pytest.raises(ValidationError):
        InputWizardRequest.model_validate({"mode": "other", "prompt": "x"})


def test_mutation_request_models_required_fields_match_openapi() -> None:
    from zenture._contract import ChatRequest, EvaluateRequest, InputWizardRequest

    schemas = _schemas()

    assert ChatRequest.model_json_schema()["required"] == schemas["ChatRequest"]["required"]
    assert EvaluateRequest.model_json_schema()["required"] == schemas["EvaluateRequest"]["required"]
    assert (
        InputWizardRequest.model_json_schema()["required"]
        == schemas["InputWizardRequest"]["required"]
    )


def test_sdk_tolerates_omitted_pending_amount_without_changing_openapi_contract() -> None:
    from zenture._contract import TerminalBillingSummaryV1

    assert "final_credits" not in TerminalBillingSummaryV1.model_json_schema()["required"]
    assert "final_credits" in _schemas()["TerminalBillingSummaryV1"]["required"]


def test_phase_four_response_models_match_required_fields() -> None:
    from zenture._contract import (
        LimitsResponse,
        PublicChatCollectionResponse,
        PublicChatMessagesResponse,
        PublicChatResponse,
        PublicEvaluationCollectionResponse,
        PublicEvaluationResponse,
        PublicModelListResponse,
        PublicUsageResponse,
        PublicWalletResponse,
    )

    schemas = _schemas()

    model_pairs: dict[str, type[BaseModel]] = {
        "LimitsResponse": LimitsResponse,
        "PublicModelListResponse": PublicModelListResponse,
        "PublicWalletResponse": PublicWalletResponse,
        "PublicChatCollectionResponse": PublicChatCollectionResponse,
        "PublicChatMessagesResponse": PublicChatMessagesResponse,
        "PublicChatResponse": PublicChatResponse,
        "PublicEvaluationCollectionResponse": PublicEvaluationCollectionResponse,
        "PublicEvaluationResponse": PublicEvaluationResponse,
        "PublicUsageResponse": PublicUsageResponse,
    }

    for schema_name, model_type in model_pairs.items():
        assert model_type.model_json_schema()["additionalProperties"] is False
        assert model_type.model_json_schema()["required"] == schemas[schema_name]["required"]


def test_phase_four_response_models_validate_api_json() -> None:
    from zenture._contract import (
        LimitsResponse,
        ModelMode,
        PublicChatCollectionResponse,
        PublicEvaluationCollectionResponse,
        PublicModelListResponse,
        PublicUsageResponse,
        PublicWalletResponse,
    )

    models = PublicModelListResponse.model_validate(
        {
            "models": [
                {
                    "id": "model-public-1",
                    "display_name": "General model",
                    "modes": ["single", "multi"],
                    "capabilities": ["chat"],
                    "is_default": True,
                    "is_available": True,
                    "cost_class": "standard",
                    "provider_display_name": None,
                    "max_input_tokens": 16000,
                }
            ]
        }
    )
    chat_collection = PublicChatCollectionResponse.model_validate(
        {
            "chats": [
                {
                    "chat_id": "chat_abc123",
                    "created_at": "2026-06-15T10:00:00Z",
                    "title": None,
                }
            ],
            "next_cursor": None,
        }
    )
    evaluation_collection = PublicEvaluationCollectionResponse.model_validate(
        {"evaluations": [{"evaluation_id": "eval_abc123", "status": "queued"}]}
    )
    wallet = PublicWalletResponse.model_validate(
        {
            "plan": "pro",
            "status": "active",
            "credits_available": {"amount": "123.45", "unit": "credits"},
        }
    )
    usage = PublicUsageResponse.model_validate({"scope": "api", "operation_count": 3})
    limits = LimitsResponse.model_validate(
        {
            "routes": {
                "POST /v1/chat": {
                    "auth_mode": "api_token",
                    "scopes": ["chat:create"],
                    "cost_class": "expensive",
                    "idempotency_required": True,
                    "cors_policy": "server_only",
                    "max_body_bytes": 65536,
                    "rate_limit_per_minute": 10,
                }
            },
            "operation_statuses": ["queued", "running", "succeeded"],
        }
    )

    assert models.models[0].modes == (ModelMode.SINGLE, ModelMode.MULTI)
    assert chat_collection.chats[0].chat_id == "chat_abc123"
    assert evaluation_collection.evaluations[0].evaluation_id == "eval_abc123"
    assert wallet.plan == "pro"
    assert wallet.credits_available.amount == "123.45"
    assert usage.operation_count == 3
    assert limits.routes["POST /v1/chat"].scopes == ("chat:create",)

    with pytest.raises(ValidationError):
        PublicModelListResponse.model_validate(
            {
                "models": [
                    {
                        "id": "model-public-1",
                        "display_name": "General model",
                        "modes": ["single"],
                        "capabilities": [""],
                        "is_default": True,
                        "is_available": True,
                        "cost_class": "standard",
                    }
                ]
            }
        )
    with pytest.raises(ValidationError):
        PublicModelListResponse.model_validate(
            {
                "models": [
                    {
                        "id": "model-public-1",
                        "display_name": "General model",
                        "modes": ["single"],
                        "capabilities": ["c" * 41],
                        "is_default": True,
                        "is_available": True,
                        "cost_class": "standard",
                    }
                ]
            }
        )


def test_phase_four_collection_models_are_deeply_immutable() -> None:
    from zenture._contract import LimitsResponse, PublicChatCollectionResponse

    chat_collection = PublicChatCollectionResponse.model_validate(
        {
            "chats": [
                {
                    "chat_id": "chat_abc123",
                    "created_at": "2026-06-15T10:00:00Z",
                }
            ]
        }
    )
    limits = LimitsResponse.model_validate(
        {
            "routes": {
                "POST /v1/chat": {
                    "auth_mode": "api_token",
                    "scopes": ["chat:create"],
                    "cost_class": "expensive",
                    "idempotency_required": True,
                    "cors_policy": "server_only",
                    "max_body_bytes": 65536,
                    "rate_limit_per_minute": 10,
                }
            },
            "operation_statuses": ["queued"],
        }
    )

    assert chat_collection.chats == (chat_collection.chats[0],)
    assert limits.operation_statuses == ("queued",)
    assert limits.routes["POST /v1/chat"].scopes == ("chat:create",)


def test_rate_limit_header_helpers_match_openapi_headers() -> None:
    from zenture._contract import RATE_LIMIT_HEADER_NAMES, RateLimitInfo, parse_rate_limit_headers

    contract = _contract()
    components = contract["components"]
    assert isinstance(components, dict)
    typed_components = cast("dict[str, Any]", components)
    headers = typed_components["headers"]
    assert isinstance(headers, dict)
    typed_headers = cast("dict[str, Any]", headers)

    assert set(RATE_LIMIT_HEADER_NAMES) == {
        "RateLimit-Limit",
        "RateLimit-Remaining",
        "RateLimit-Reset",
        "Retry-After",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
    }
    assert set(typed_headers) == {
        "RateLimitLimit",
        "RateLimitRemaining",
        "RateLimitReset",
        "RetryAfter",
        "XRateLimitLimit",
        "XRateLimitRemaining",
        "XRateLimitReset",
    }
    assert parse_rate_limit_headers({"RateLimit-Limit": "10"}) == RateLimitInfo(limit=10)


def test_contract_surface_excludes_api_token_management_models() -> None:
    import zenture._contract as contract

    exported_names = set(contract.__all__)

    assert "ApiToken" not in "".join(exported_names)
    assert "API_TOKEN_MANAGEMENT_PATHS" not in exported_names


def test_run_request_models_use_gateway_bounds_and_reference_grammar() -> None:
    from pydantic import ValidationError

    from zenture._contract import PrepareKnowledgeRunRequest, RunTextArtifact

    PrepareKnowledgeRunRequest.model_validate(
        {"task": "x" * 20_000, "artifact": {"type": "text", "value": "x" * 50_000}}
    )
    PrepareKnowledgeRunRequest.model_validate(
        {"task": "😀" * 20_000, "artifact": {"type": "text", "value": "é" * 50_000}}
    )
    RunTextArtifact(type="text", value="x" * 20_000)
    RunTextArtifact(type="text", value="x" * 50_000)

    with pytest.raises(ValidationError):
        PrepareKnowledgeRunRequest.model_validate(
            {"task": "x" * 20_001, "artifact": {"type": "text", "value": "x"}}
        )
    with pytest.raises(ValidationError):
        RunTextArtifact(type="text", value="x" * 50_001)
    for value in ("HTTPS://example.invalid", "data:text/plain,x", "file:///tmp/input"):
        with pytest.raises(ValidationError):
            RunTextArtifact(type="text", value=value)


def test_run_success_models_enforce_gateway_upload_and_cursor_constraints() -> None:
    from pydantic import ValidationError

    from zenture._contract import (
        ArtifactUploadResponse,
        ListRunEventsResponse,
        ListRunsResponse,
        PublicRunEvent,
        PublicRunResponse,
        SignedUploadResponse,
    )

    upload = "upload_abcdefgh"
    ArtifactUploadResponse(
        upload_id=upload,
        artifact_ref="art_abcdefgh",
        content_hash="a" * 64,
        byte_size=1,
        content_type="text/plain",
    )
    SignedUploadResponse.model_validate({"upload_id": upload, "expires_at": "2026-01-01T00:00:00Z"})
    for invalid in ("short", "upload_bad value", "upload_abc"):
        with pytest.raises(ValidationError):
            SignedUploadResponse.model_validate(
                {"upload_id": invalid, "expires_at": "2026-01-01T00:00:00Z"}
            )
    for response_type in (ListRunsResponse, ListRunEventsResponse):
        for invalid in (
            "x" * 513,
            "cursor with spaces",
            "cursor+plus",
            "cursor/slash",
            "cursor\nheader",
            "é",
        ):
            with pytest.raises(ValidationError):
                response_type.model_validate(
                    {
                        "runs" if response_type is ListRunsResponse else "events": [],
                        "has_more": False,
                        "next_cursor": invalid,
                    }
                )

    run = {
        "run_id": "run_1234567890abcdef",
        "generation": 1,
        "family": "knowledge",
        "work_type": "answer",
        "profile": "standard",
        "status": "completed",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    for invalid in ("cursor with spaces", "cursor+plus", "cursor\nheader"):
        with pytest.raises(ValidationError):
            PublicRunResponse.model_validate({**run, "event_cursor": invalid})

    event = {
        "type": "run.event",
        "event_id": "event_1",
        "run_id": "run_1234567890abcdef",
        "sequence": 1,
        "phase": "completed",
        "status": "completed",
        "message_key": "run.completed",
        "event_cursor": "cursor_1",
    }
    for invalid in ("", "ref with spaces", "ref+plus", "ref?query", "ref#fragment", "é"):
        with pytest.raises(ValidationError):
            PublicRunEvent.model_validate({**event, "terminal_refs": [invalid]})


def test_run_responses_accept_additive_fields_but_keep_known_fields_strict() -> None:
    from pydantic import ValidationError

    from zenture._contract import PrepareKnowledgeRunRequest, PublicRunListItem, PublicRunResponse

    run = {
        "run_id": "run_1234567890abcdef",
        "generation": 1,
        "family": "knowledge",
        "work_type": "answer",
        "profile": "standard",
        "status": "queued",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "deadline_at": "2026-01-01T00:01:00Z",
        "queue": {
            "queue_reason": "queue:admitted",
            "jobs_ahead": 0,
            "future_queue_hint": "ignored",
        },
        "future_run_field": {"opaque": True},
    }
    response = PublicRunResponse.model_validate(run)

    assert response.deadline_at is not None
    assert response.deadline_at.isoformat() == "2026-01-01T00:01:00+00:00"
    assert not hasattr(response, "future_run_field")
    list_item = PublicRunListItem.model_validate(
        {
            "run_id": run["run_id"],
            "status": run["status"],
            "profile": run["profile"],
            "created_at": run["created_at"],
            "updated_at": run["updated_at"],
            "deadline_at": run["deadline_at"],
            "future_list_field": True,
        }
    )
    assert list_item.deadline_at == response.deadline_at

    with pytest.raises(ValidationError):
        PublicRunResponse.model_validate({**run, "status": "future_status"})
    with pytest.raises(ValidationError):
        PrepareKnowledgeRunRequest.model_validate(
            {
                "task": "review",
                "artifact": {"type": "text", "value": "answer"},
                "future_request_field": True,
            }
        )


def test_run_deadline_requires_an_aware_timestamp() -> None:
    from pydantic import ValidationError

    from zenture._contract import PublicRunResponse

    run = {
        "run_id": "run_1234567890abcdef",
        "generation": 1,
        "family": "knowledge",
        "work_type": "answer",
        "profile": "standard",
        "status": "queued",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }

    with pytest.raises(ValidationError):
        PublicRunResponse.model_validate({**run, "deadline_at": "2026-01-01T00:01:00"})


_RUN_BASE = {
    "run_id": "run_1234567890abcdef",
    "generation": 1,
    "family": "knowledge",
    "work_type": "answer",
    "profile": "standard",
    "status": "queued",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


def test_accept_run_request_carries_the_one_call_prepare_fields() -> None:
    from zenture._contract import AcceptRunRequest, RunProfile

    schema = _schemas()["AcceptRunRequest"]
    assert set(AcceptRunRequest.model_fields) == set(schema["properties"])

    request = AcceptRunRequest.model_validate(
        {
            "task": "review this",
            "artifact": {"type": "text", "value": "answer"},
            "predecessor_run_id": "run_abc123",
        }
    )
    assert request.profile is RunProfile.STANDARD
    assert request.predecessor_run_id == "run_abc123"

    for bad in (
        {"task": " ", "artifact": {"type": "text", "value": "a"}},
        {"task": "t", "artifact": {"type": "text", "value": "a"}, "predecessor_run_id": "x"},
        {"task": "t", "artifact": {"type": "text", "value": "a"}, "unknown": 1},
    ):
        with pytest.raises(ValidationError):
            AcceptRunRequest.model_validate(bad)


def test_public_error_retryable_is_only_ever_true() -> None:
    from zenture._contract import PublicErrorEnvelope

    schema = _schemas()["PublicError"]["properties"]["retryable"]
    assert schema["const"] is True
    envelope = {
        "error": {"code": "capacity_unavailable", "message": "later", "retryable": True},
        "request_id": "req_" + "a" * 32,
    }
    assert PublicErrorEnvelope.model_validate(envelope).error.retryable is True
    omitted = {"error": {"code": "internal_error", "message": "x"}, "request_id": "req_" + "a" * 32}
    assert PublicErrorEnvelope.model_validate(omitted).error.retryable is None
    envelope["error"]["retryable"] = False  # type: ignore[index]
    with pytest.raises(ValidationError):
        PublicErrorEnvelope.model_validate(envelope)


def test_api_error_exposes_retryable_and_retry_after() -> None:
    from zenture.errors import error_from_response

    payload = {
        "error": {"code": "dependency_unavailable", "message": "later", "retryable": True},
        "request_id": "req_" + "b" * 32,
    }
    error = error_from_response(status_code=503, payload=payload, headers={"Retry-After": "7"})
    assert error.retryable is True
    assert error.retry_after == 7.0

    plain = {"error": {"code": "forbidden", "message": "no"}, "request_id": "req_" + "b" * 32}
    assert error_from_response(status_code=403, payload=plain, headers={}).retryable is False


def test_run_response_reads_accepted_request_and_technical_status() -> None:
    from zenture._contract import PublicRunResponse

    properties = _schemas()["PublicRunResponse"]["properties"]
    assert set(PublicRunResponse.model_fields) >= set(properties) - {"decision"}

    accepted = PublicRunResponse.model_validate(
        {
            **_RUN_BASE,
            "phase": "preparing",
            "queue_expires_at": "2026-01-01T00:10:00Z",
            "retry_after_seconds": 5,
        }
    )
    assert accepted.phase == "preparing"
    assert accepted.queue_expires_at is not None
    assert accepted.retry_after_seconds == 5

    failed = PublicRunResponse.model_validate(
        {**_RUN_BASE, "status": "failed", "technical_status": "failed", "result": "pending"}
    )
    assert failed.technical_status == "failed"
    assert failed.result == "pending"
    assert failed.acceptance_decision is None

    for bad in ({"phase": "later"}, {"retry_after_seconds": 61}, {"result": "ready"}):
        with pytest.raises(ValidationError):
            PublicRunResponse.model_validate({**_RUN_BASE, **bad})


def test_retry_after_is_declared_on_transient_gateway_failures() -> None:
    paths = cast("dict[str, dict[str, Any]]", _contract()["paths"])
    declared: dict[str, set[tuple[str, str]]] = {"502": set(), "503": set(), "504": set()}
    for path, item in paths.items():
        for method, raw_operation in item.items():
            operation = cast("dict[str, Any]", raw_operation)
            responses = cast("dict[str, dict[str, Any]]", operation.get("responses", {}))
            for status, response in responses.items():
                headers = cast("dict[str, Any]", response.get("headers", {}))
                has_retry_after = any(name.lower() == "retry-after" for name in headers)
                if status in declared:
                    assert has_retry_after, (method, path, status)
                    declared[status].add((method, path))
                if status == "431":
                    assert not has_retry_after, (method, path)

    run_routes = {key for key in declared["503"] if key[1].startswith("/v1/run")}
    assert len(declared["503"]) == 24
    assert len(run_routes) == 10
    assert declared["502"] == run_routes
    assert declared["504"] == run_routes
