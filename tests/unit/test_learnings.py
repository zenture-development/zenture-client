"""The learning surface: get_learnings over REST and MCP, and the optional learning Run fields."""

from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from zenture import AsyncZentureClient, ZentureClient
from zenture._contract import PublicRunResponse
from zenture._mcp import AsyncMcpClient, McpClient
from zenture.errors import (
    ZentureMCPError,
    ZentureMCPProtocolError,
    ZenturePermissionError,
    ZentureRateLimitError,
    ZentureResponseError,
)
from zenture.types import Essence, Learnings

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

API_KEY = "zt_" + "live_" + "client_123"
FIXTURE = Path(__file__).parent / "fixtures" / "safe-result-content.full-verdict.valid.json"
RUN_ID = "run_33333333333343338333333333333333"
ESSENCE = {
    "text": "You often state figures without naming their source.",
    "version": "v7",
    "day": "2026-10-30",
    "language": "en",
}
AVAILABLE = {"state": "available", "essence": ESSENCE}
COLD_START = {"state": "cold_start"}
LEARNING_OFF = {"state": "learning_off"}


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


def _serving(payload: object) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/learnings"
        assert request.url.query == b""
        assert request.content == b""
        return httpx.Response(200, json=payload)

    return handler


@pytest.mark.parametrize("payload", [AVAILABLE, COLD_START, LEARNING_OFF])
def test_rest_and_mcp_return_the_same_learnings_model(payload: dict[str, Any]) -> None:
    rest = _rest(_serving(payload)).get_learnings()
    mcp_transport = _SyncMcp(payload)
    mcp = McpClient(mcp_transport).get_learnings()

    assert isinstance(rest, Learnings)
    assert rest == mcp
    assert rest.state == payload["state"]
    assert mcp_transport.calls == [("get_learnings", {})]


@pytest.mark.parametrize("payload", [AVAILABLE, COLD_START, LEARNING_OFF])
def test_async_rest_and_mcp_return_the_same_learnings_model(payload: dict[str, Any]) -> None:
    async def scenario() -> tuple[Learnings, Learnings, _AsyncMcp]:
        transport = _AsyncMcp(payload)
        async with _rest_async(_serving(payload)) as rest:
            return (
                await rest.get_learnings(),
                await AsyncMcpClient(transport).get_learnings(),
                transport,
            )

    rest, mcp, transport = asyncio.run(scenario())

    assert rest == mcp == _rest(_serving(payload)).get_learnings()
    assert transport.calls == [("get_learnings", {})]


def test_available_learnings_expose_the_essence_and_others_none() -> None:
    available = _rest(_serving(AVAILABLE)).get_learnings()
    cold = _rest(_serving(COLD_START)).get_learnings()

    assert isinstance(available.essence, Essence)
    assert available.essence.text == ESSENCE["text"]
    assert available.essence.version == "v7"
    assert available.essence.day == "2026-10-30"
    assert available.essence.language == "en"
    assert cold.essence is None


@pytest.mark.parametrize(
    "payload",
    [
        {"state": "available"},
        {"state": "cold_start", "essence": ESSENCE},
        {"state": "learning_off", "essence": ESSENCE},
        {"state": "unknown"},
        {"state": "available", "essence": {**ESSENCE, "text": ""}},
        {"state": "available", "essence": {**ESSENCE, "text": "x" * 601}},
        {"state": "available", "essence": {**ESSENCE, "version": "v" * 65}},
        {"state": "available", "essence": {**ESSENCE, "day": "30.10.2026"}},
        {"state": "available", "essence": {**ESSENCE, "language": "english"}},
        {"state": "available", "essence": {**ESSENCE, "extra": "x"}},
        {**AVAILABLE, "owner": "someone"},
    ],
)
def test_learnings_parse_strictly_over_both_transports(payload: dict[str, Any]) -> None:
    with pytest.raises(ZentureResponseError):
        _rest(_serving(payload)).get_learnings()
    with pytest.raises(ZentureMCPProtocolError):
        McpClient(_SyncMcp(payload)).get_learnings()


def test_language_accepts_a_region_subtag() -> None:
    payload = {"state": "available", "essence": {**ESSENCE, "language": "pt-BR"}}

    assert _rest(_serving(payload)).get_learnings().essence is not None


def test_no_client_takes_an_owner_org_or_scope_argument() -> None:
    for method in (
        ZentureClient.get_learnings,
        AsyncZentureClient.get_learnings,
        McpClient.get_learnings,
        AsyncMcpClient.get_learnings,
    ):
        assert list(inspect.signature(method).parameters) == ["self"]


def test_rest_errors_use_the_existing_error_types() -> None:
    def forbidden(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403, json={"error": {"code": "forbidden", "message": "scope evaluation:read missing"}}
        )

    with pytest.raises(ZenturePermissionError):
        _rest(forbidden).get_learnings()


def test_rest_429_goes_through_retry_and_then_raises_rate_limited() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"error": {"code": "rate_limited", "message": "slow down"}},
            )
        return httpx.Response(200, json=AVAILABLE)

    client = ZentureClient(
        api_key=API_KEY, http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    assert client.get_learnings().state == "available"
    assert attempts == 2

    def always(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "7"},
            json={"error": {"code": "rate_limited", "message": "slow down"}},
        )

    with pytest.raises(ZentureRateLimitError) as exc_info:
        _rest(always).get_learnings()
    assert exc_info.value.retry_after == 7


def test_mcp_tool_errors_use_the_mcp_error_type() -> None:
    failure = {
        "error": {
            "code": "rate_limited",
            "http_status": 429,
            "retryable": True,
            "next_action": "retry_later",
            "retry_after_seconds": 5,
        }
    }

    with pytest.raises(ZentureMCPError) as exc_info:
        McpClient(_SyncMcp(failure, is_error=True)).get_learnings()
    assert exc_info.value.status_code == 429


def _run(**extra: object) -> dict[str, object]:
    return {
        "run_id": RUN_ID,
        "generation": 1,
        "family": "knowledge",
        "work_type": "answer",
        "profile": "standard",
        "status": "completed",
        "created_at": "2026-10-30T12:00:00Z",
        "updated_at": "2026-10-30T12:00:01Z",
        **extra,
    }


def _content(finding_extra: Mapping[str, object]) -> dict[str, Any]:
    content = json.loads(FIXTURE.read_text(encoding="utf-8"))
    content["content"]["findings"][0].update(finding_extra)
    return content


def test_old_run_payloads_parse_with_the_learning_fields_absent() -> None:
    run = PublicRunResponse.model_validate(_run())

    assert run.learning_applied is None
    assert run.essence_version is None
    assert run.essence is None


def test_run_learning_fields_parse_and_stay_bounded() -> None:
    run = PublicRunResponse.model_validate(
        _run(learning_applied=True, essence_version="v7", essence="Name your sources.")
    )

    assert run.learning_applied is True
    assert run.essence_version == "v7"
    assert run.essence == "Name your sources."
    with pytest.raises(ValueError, match="essence_version"):
        PublicRunResponse.model_validate(_run(essence_version="v" * 65))
    with pytest.raises(ValueError, match="essence"):
        PublicRunResponse.model_validate(_run(essence="x" * 601))


@pytest.mark.parametrize("marker", [True, "Fokus aus deiner Essenz"])
def test_finding_essence_focus_parses_from_rest_flag_and_mcp_label(marker: object) -> None:
    run = PublicRunResponse.model_validate(
        _run(
            safe_result_content=_content({"essence_focus": marker}),
        )
    )
    unmarked = PublicRunResponse.model_validate(_run(safe_result_content=_content({})))

    assert run.safe_result_content is not None
    assert run.safe_result_content.status == "available"
    assert run.safe_result_content.content.findings[0].essence_focus is True
    assert unmarked.safe_result_content is not None
    assert unmarked.safe_result_content.status == "available"
    assert unmarked.safe_result_content.content.findings[0].essence_focus is False


def test_finding_essence_focus_null_means_not_focused() -> None:
    run = PublicRunResponse.model_validate(
        _run(safe_result_content=_content({"essence_focus": None}))
    )

    assert run.safe_result_content is not None
    assert run.safe_result_content.status == "available"
    assert run.safe_result_content.content.findings[0].essence_focus is False


def test_finding_essence_focus_rejects_other_values() -> None:
    with pytest.raises(ValueError, match="essence_focus"):
        PublicRunResponse.model_validate(
            _run(safe_result_content=_content({"essence_focus": "yes"}))
        )


def test_rest_run_read_exposes_learning_fields() -> None:
    payload = _run(learning_applied=True, essence_version="v7")
    client = _rest(lambda _request: httpx.Response(200, json=payload))

    run = client.runs.get(RUN_ID)

    assert run.learning_applied is True
    assert run.essence_version == "v7"
