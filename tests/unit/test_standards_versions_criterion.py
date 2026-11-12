"""Standards carry their restorable versions and suggested criterion; edit restores or applies it (D-218/D-219)."""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import ValidationError
from test_standards import (
    KEY,
    STANDARD,
    STANDARD_ID,
    _AsyncMcp,  # pyright: ignore[reportPrivateUsage] -- shared standards test doubles
    _rest,  # pyright: ignore[reportPrivateUsage] -- shared standards test doubles
    _rest_async,  # pyright: ignore[reportPrivateUsage] -- shared standards test doubles
    _Seen,  # pyright: ignore[reportPrivateUsage] -- shared standards test doubles
    _SyncMcp,  # pyright: ignore[reportPrivateUsage] -- shared standards test doubles
)

from zenture import AsyncZentureClient, ZentureClient
from zenture._mcp import AsyncMcpClient, McpClient
from zenture.types import AgentStandard

WRITTEN = {
    **STANDARD,
    "version": 3,
    "form": "written",
    "restorable_versions": [1, 2],
    "suggested_criterion": "Every figure names its source",
}
WRITTEN.pop("criterion")
REMOVED_METHODS = ("get_learnings", "get_standard_versions", "accept_standard_preview")


def test_a_standard_exposes_version_restorable_versions_and_suggested_criterion() -> None:
    standard = AgentStandard.model_validate(WRITTEN)
    assert (standard.version, standard.restorable_versions) == (3, [1, 2])
    assert standard.suggested_criterion == "Every figure names its source"
    bare = AgentStandard.model_validate(STANDARD)
    assert (bare.restorable_versions, bare.suggested_criterion) == ([], None)
    with pytest.raises(ValidationError):
        AgentStandard.model_validate({**WRITTEN, "restorable_versions": list(range(1, 22))})
    with pytest.raises(ValidationError):
        AgentStandard.model_validate({**WRITTEN, "suggested_criterion": "x"})


def test_edit_restore_version_has_the_same_body_over_rest_and_mcp() -> None:
    seen = _Seen(200, {**STANDARD, "version": 4})
    rest = _rest(seen).edit_standard(
        STANDARD_ID, expected_version=3, restore_version=1, idempotency_key=KEY
    )
    transport = _SyncMcp({**STANDARD, "version": 4})
    mcp = McpClient(transport).edit_standard(STANDARD_ID, expected_version=3, restore_version=1)
    body = json.loads(seen.requests[0].content)
    assert rest == mcp
    assert body == {"expected_version": 3, "restore_version": 1}
    assert transport.calls == [("edit_standard", {"standard_id": STANDARD_ID, **body})]


def test_edit_use_suggested_criterion_has_the_same_body_over_rest_and_mcp() -> None:
    seen = _Seen(200, {**STANDARD, "version": 4})
    request_client = _rest(seen)
    rest = request_client.edit_standard(
        STANDARD_ID, expected_version=3, use_suggested_criterion=True, idempotency_key=KEY
    )
    transport = _SyncMcp({**STANDARD, "version": 4})
    mcp = McpClient(transport).edit_standard(
        STANDARD_ID, expected_version=3, use_suggested_criterion=True
    )
    request = seen.requests[0]
    body = json.loads(request.content)
    assert rest == mcp
    assert (request.method, request.url.path) == ("PATCH", f"/v1/standards/{STANDARD_ID}")
    assert request.headers["Idempotency-Key"] == KEY
    assert body == {"expected_version": 3, "use_suggested_criterion": True}
    assert transport.calls == [("edit_standard", {"standard_id": STANDARD_ID, **body})]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"restore_version": 1, "use_suggested_criterion": True},
        {"text": "Cite a source", "use_suggested_criterion": True},
        {"use_suggested_criterion": False},
    ],
)
def test_edit_refuses_mixed_or_false_modes_before_any_request(kwargs: dict[str, object]) -> None:
    seen = _Seen(200, STANDARD)
    with pytest.raises(ValueError, match=r"cannot be combined|True|at least one"):
        _rest(seen).edit_standard(STANDARD_ID, expected_version=1, idempotency_key=KEY, **kwargs)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"cannot be combined|True|at least one"):
        McpClient(_SyncMcp(STANDARD)).edit_standard(STANDARD_ID, expected_version=1, **kwargs)  # type: ignore[arg-type]
    assert seen.requests == []


def test_async_clients_send_the_suggested_criterion_like_the_sync_ones() -> None:
    async def scenario() -> tuple[object, object, _Seen, _AsyncMcp]:
        seen = _Seen(200, {**STANDARD, "version": 4})
        transport = _AsyncMcp({**STANDARD, "version": 4})
        async with _rest_async(seen) as client:
            first = await client.edit_standard(
                STANDARD_ID, expected_version=3, use_suggested_criterion=True, idempotency_key=KEY
            )
        second = await AsyncMcpClient(transport).edit_standard(
            STANDARD_ID, expected_version=3, use_suggested_criterion=True
        )
        return first, second, seen, transport

    first, second, seen, transport = asyncio.run(scenario())
    assert first == second
    assert json.loads(seen.requests[0].content) == {
        "expected_version": 3,
        "use_suggested_criterion": True,
    }
    assert transport.calls[0][1]["use_suggested_criterion"] is True


@pytest.mark.parametrize(
    "client_type", [ZentureClient, AsyncZentureClient, McpClient, AsyncMcpClient]
)
def test_the_removed_learning_and_version_calls_are_gone(client_type: type) -> None:
    for name in REMOVED_METHODS:
        assert not hasattr(client_type, name)
