"""The standards surface: get/define/edit over REST and MCP with the same closed models (P6.10)."""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from pydantic import ValidationError

from zenture import AsyncZentureClient, ZentureClient
from zenture._mcp import AsyncMcpClient, McpClient
from zenture.errors import (
    ZentureAPIError,
    ZentureMCPError,
    ZentureMCPProtocolError,
    ZentureMissingIdempotencyKeyError,
    ZentureResponseError,
    ZentureValidationError,
)
from zenture.types import AgentStandard, AgentStandards

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

API_KEY = "zt_" + "live_" + "client_123"
STANDARD_ID = "5b0f3c1e-8a52-4f6e-9d57-3a1e2f6c7b10"
STANDARD = {
    "standard_id": STANDARD_ID,
    "owner": "user",
    "version": 1,
    "strength": "must",
    "task_types": ["facts_with_sources"],
    "active": True,
    "text": "Cite a source for every figure",
    "criterion": "Every figure names its source",
    "editable": True,
}
LIST = {"standards": [STANDARD], "limit": 8}
DEFINE = {
    "text": "Cite a source for every figure",
    "strength": "must",
    "task_types": ["facts_with_sources"],
}
KEY = "standard-key-0001"


class _SyncMcp:
    def __init__(self, payload: object, *, is_error: bool = False) -> None:
        self.payload = payload
        self.is_error = is_error
        self.calls: list[tuple[str, Mapping[str, object]]] = []

    def list_tools(self) -> object:
        return {"tools": []}

    def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        self.calls.append((name, arguments))
        return {"structured_content": self.payload, "is_error": self.is_error}


class _AsyncMcp(_SyncMcp):
    async def list_tools(self) -> object:  # type: ignore[override]
        return {"tools": []}

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:  # type: ignore[override]
        return super().call_tool(name, arguments)


def _rest(handler: Callable[[httpx.Request], httpx.Response]) -> ZentureClient:
    return ZentureClient(
        api_key=API_KEY,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )


def _rest_async(handler: Callable[[httpx.Request], httpx.Response]) -> AsyncZentureClient:
    return AsyncZentureClient(
        api_key=API_KEY,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )


class _Seen:
    def __init__(self, status: int, payload: object) -> None:
        self.status, self.payload = status, payload
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.payload)


def test_rest_and_mcp_read_the_same_closed_standards_model() -> None:
    seen = _Seen(200, LIST)
    rest = _rest(seen).get_standards()
    transport = _SyncMcp(LIST)
    mcp = McpClient(transport).get_standards()

    assert isinstance(rest, AgentStandards)
    assert isinstance(rest.standards[0], AgentStandard)
    assert rest == mcp
    request = seen.requests[0]
    assert (request.method, request.url.path, request.url.query, request.content) == (
        "GET",
        "/v1/standards",
        b"",
        b"",
    )
    assert transport.calls == [("get_standards", {})]


def test_async_clients_read_the_same_model() -> None:
    async def scenario() -> tuple[AgentStandards, AgentStandards]:
        async with _rest_async(_Seen(200, LIST)) as rest:
            return await rest.get_standards(), await AsyncMcpClient(_AsyncMcp(LIST)).get_standards()

    rest, mcp = asyncio.run(scenario())
    assert rest == mcp == _rest(_Seen(200, LIST)).get_standards()


def test_rest_and_mcp_define_send_the_same_body_and_return_the_same_model() -> None:
    seen = _Seen(201, STANDARD)
    rest = _rest(seen).define_standard(**DEFINE, idempotency_key=KEY)
    transport = _SyncMcp(STANDARD)
    mcp = McpClient(transport).define_standard(**DEFINE)

    assert rest == mcp
    assert isinstance(rest, AgentStandard)
    request = seen.requests[0]
    assert (request.method, request.url.path) == ("POST", "/v1/standards")
    assert request.headers["Idempotency-Key"] == KEY
    body = json.loads(request.content)
    assert body == {**DEFINE, "owner": "user"}
    assert transport.calls == [("define_standard", body)]


def test_rest_and_mcp_edit_send_the_same_change_and_return_the_same_model() -> None:
    edited = {**STANDARD, "version": 2, "active": False}
    seen = _Seen(200, edited)
    rest = _rest(seen).edit_standard(
        STANDARD_ID, expected_version=1, active=False, idempotency_key=KEY
    )
    transport = _SyncMcp(edited)
    mcp = McpClient(transport).edit_standard(STANDARD_ID, expected_version=1, active=False)

    assert rest == mcp
    assert rest.version == 2
    request = seen.requests[0]
    assert (request.method, request.url.path) == ("PATCH", f"/v1/standards/{STANDARD_ID}")
    assert request.headers["Idempotency-Key"] == KEY
    assert json.loads(request.content) == {"expected_version": 1, "active": False}
    assert transport.calls == [
        ("edit_standard", {"standard_id": STANDARD_ID, "expected_version": 1, "active": False})
    ]


def test_async_define_and_edit_match_the_sync_wire() -> None:
    seen = _Seen(200, STANDARD)
    transport = _AsyncMcp(STANDARD)

    async def scenario() -> list[AgentStandard]:
        async with _rest_async(seen) as rest:
            return [
                await rest.define_standard(**DEFINE, owner="org", idempotency_key=KEY),
                await rest.edit_standard(
                    STANDARD_ID, expected_version=1, restore_version=1, idempotency_key=KEY
                ),
                await AsyncMcpClient(transport).define_standard(**DEFINE, owner="org"),
                await AsyncMcpClient(transport).edit_standard(
                    STANDARD_ID, expected_version=1, restore_version=1
                ),
            ]

    results = asyncio.run(scenario())
    assert results[0] == results[2]
    assert results[1] == results[3]
    assert json.loads(seen.requests[0].content)["owner"] == "org"
    assert json.loads(seen.requests[1].content) == {"expected_version": 1, "restore_version": 1}


@pytest.mark.parametrize(
    "payload",
    [
        {"standards": [{**STANDARD, "account_id": "x"}], "limit": 8},
        {"standards": [{**STANDARD, "owner": "team"}], "limit": 8},
        {"standards": [{**STANDARD, "version": 0}], "limit": 8},
        {"standards": [{**STANDARD, "standard_id": "nope"}], "limit": 8},
        {"standards": [], "limit": 9},
        {"standards": []},
    ],
)
def test_standards_parse_strictly_over_both_transports(payload: dict[str, Any]) -> None:
    with pytest.raises(ZentureResponseError):
        _rest(_Seen(200, payload)).get_standards()
    with pytest.raises(ZentureMCPProtocolError):
        McpClient(_SyncMcp(payload)).get_standards()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"text": "ab", "strength": "must"},
        {"text": "Cite a source", "strength": "never"},
        {"text": "Cite a source", "strength": "must", "task_types": ["poetry"]},
        {"text": "Cite a source", "strength": "must", "task_types": ["other", "other"]},
        {"text": "Cite a source", "strength": "must", "owner": STANDARD_ID},
    ],
)
def test_define_refuses_invalid_input_before_any_request(kwargs: dict[str, Any]) -> None:
    seen = _Seen(201, STANDARD)
    transport = _SyncMcp(STANDARD)

    with pytest.raises(ValidationError):
        _rest(seen).define_standard(**kwargs, idempotency_key=KEY)
    with pytest.raises(ValidationError):
        McpClient(transport).define_standard(**kwargs)
    assert seen.requests == []
    assert transport.calls == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"expected_version": 1},
        {"expected_version": 0, "active": True},
        {"expected_version": 1, "restore_version": 1, "text": "Cite a source"},
        {"expected_version": 1, "task_types": ["other", "other"]},
    ],
)
def test_edit_refuses_invalid_input_before_any_request(kwargs: dict[str, Any]) -> None:
    seen = _Seen(200, STANDARD)
    transport = _SyncMcp(STANDARD)

    with pytest.raises(ValidationError):
        _rest(seen).edit_standard(STANDARD_ID, **kwargs, idempotency_key=KEY)
    with pytest.raises(ValidationError):
        McpClient(transport).edit_standard(STANDARD_ID, **kwargs)
    with pytest.raises(ValueError, match="standard_id"):
        _rest(seen).edit_standard(
            "not-a-uuid", expected_version=1, active=True, idempotency_key=KEY
        )
    assert seen.requests == []
    assert transport.calls == []


def test_no_method_takes_an_account_user_or_organisation_id() -> None:
    forbidden = {"owner_id", "account_id", "user_id", "org_id", "organisation_id", "tenant_id"}
    for client in (ZentureClient, AsyncZentureClient, McpClient, AsyncMcpClient):
        for name in ("get_standards", "define_standard", "edit_standard"):
            assert not forbidden & set(inspect.signature(getattr(client, name)).parameters), (
                client,
                name,
            )
    assert list(inspect.signature(ZentureClient.get_standards).parameters) == ["self"]
    assert list(inspect.signature(McpClient.get_standards).parameters) == ["self"]


def test_rest_writes_require_a_saved_idempotency_key() -> None:
    for client in (ZentureClient, AsyncZentureClient):
        assert (
            inspect.signature(client.define_standard).parameters["idempotency_key"].default
            is inspect.Parameter.empty
        )
        assert (
            inspect.signature(client.edit_standard).parameters["idempotency_key"].default
            is inspect.Parameter.empty
        )


@pytest.mark.parametrize(
    ("status", "code", "error"),
    [
        (404, "standard_not_found", ZentureAPIError),
        (403, "standard_forbidden", ZentureAPIError),
        (409, "standard_version_conflict", ZentureAPIError),
        (409, "standard_duplicate", ZentureAPIError),
        (409, "standard_limit", ZentureAPIError),
        (422, "standard_invalid", ZentureAPIError),
        (422, "standard_not_checkable", ZentureAPIError),
        (404, "standards_disabled", ZentureAPIError),
        (503, "standards_unavailable", ZentureAPIError),
        (400, "missing_idempotency_key", ZentureMissingIdempotencyKeyError),
        (422, "validation_failed", ZentureValidationError),
    ],
)
def test_rest_errors_keep_their_closed_code(
    status: int, code: str, error: type[ZentureAPIError]
) -> None:
    envelope = {"error": {"code": code, "message": "x"}, "request_id": "req_" + "0" * 32}

    with pytest.raises(error) as raised:
        _rest(_Seen(status, envelope)).edit_standard(
            STANDARD_ID, expected_version=1, active=True, idempotency_key=KEY
        )

    assert raised.value.error_code == code
    assert raised.value.status_code == status


def test_mcp_tool_errors_use_the_mcp_error_type() -> None:
    failure = {
        "error": {
            "code": "standard_version_conflict",
            "http_status": 409,
            "retryable": False,
            "next_action": "check_request",
        }
    }

    with pytest.raises(ZentureMCPError) as raised:
        McpClient(_SyncMcp(failure, is_error=True)).edit_standard(
            STANDARD_ID, expected_version=1, active=True
        )

    assert raised.value.status_code == 409
