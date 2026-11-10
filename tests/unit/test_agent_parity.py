"""D-190 parity over REST and MCP: form and preview, accept a preview, standard versions, hide a learning, and the edit criterion."""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import ValidationError
from test_standards import (
    KEY,
    STANDARD,
    STANDARD_ID,
    _AsyncMcp,
    _rest,
    _rest_async,
    _Seen,
    _SyncMcp,
)

from zenture._mcp import AsyncMcpClient, McpClient
from zenture.types import AgentStandard, Learnings, LearningVisibility, StandardVersions

READY = {
    "state": "ready",
    "criterion": "Every figure names its source",
    "task_types_suggested": ["facts_with_sources"],
}
WRITTEN = {**STANDARD, "form": "written", "preview": READY}
WRITTEN.pop("criterion")
VERSIONS = {
    "standard_id": STANDARD_ID,
    "versions": [
        {
            "version": 2,
            "strength": "must",
            "active": True,
            "source": "agent",
            "form": "checkable",
            "text": "Cite a source for every figure",
            "criterion": "Every figure names its source",
            "created_at": "2026-11-10T09:00:00Z",
        },
        {
            "version": 1,
            "strength": "should",
            "active": True,
            "source": "app",
            "form": "written",
            "text": "Cite a source",
            "created_at": "2026-11-09T09:00:00Z",
        },
    ],
}
HIDE = {"code": "calculation_error", "hidden": True}


def test_a_written_standard_carries_its_form_and_ready_preview_and_an_unknown_state_is_refused() -> (
    None
):
    standard = AgentStandard.model_validate(WRITTEN)
    assert standard.form == "written"
    assert standard.preview is not None
    assert (standard.preview.state, standard.preview.criterion) == (
        "ready",
        "Every figure names its source",
    )
    with pytest.raises(ValidationError):
        AgentStandard.model_validate({**WRITTEN, "preview": {"state": "maybe"}})
    with pytest.raises(ValidationError):
        AgentStandard.model_validate({k: v for k, v in WRITTEN.items() if k != "form"})


def test_edit_sends_the_criterion_over_rest_and_mcp_with_the_same_body() -> None:
    seen = _Seen(200, {**STANDARD, "version": 2})
    _rest(seen).edit_standard(
        STANDARD_ID,
        expected_version=1,
        criterion="Every figure names its source",
        idempotency_key=KEY,
    )
    transport = _SyncMcp({**STANDARD, "version": 2})
    McpClient(transport).edit_standard(
        STANDARD_ID, expected_version=1, criterion="Every figure names its source"
    )
    body = json.loads(seen.requests[0].content)
    assert body == {"expected_version": 1, "criterion": "Every figure names its source"}
    assert transport.calls == [("edit_standard", {"standard_id": STANDARD_ID, **body})]


def test_versions_are_read_by_route_and_tool_into_the_same_model() -> None:
    seen = _Seen(200, VERSIONS)
    rest = _rest(seen).get_standard_versions(STANDARD_ID)
    transport = _SyncMcp(VERSIONS)
    mcp = McpClient(transport).get_standard_versions(STANDARD_ID)
    assert isinstance(rest, StandardVersions)
    assert rest == mcp
    assert [v.version for v in rest.versions] == [2, 1]
    request = seen.requests[0]
    assert (request.method, request.url.path, request.content) == (
        "GET",
        f"/v1/standards/{STANDARD_ID}/versions",
        b"",
    )
    assert transport.calls == [("get_standard_versions", {"standard_id": STANDARD_ID})]
    with pytest.raises(ValueError, match="standard identifier"):
        _rest(seen).get_standard_versions("not-an-id")


def test_accepting_a_preview_posts_the_expected_version_with_the_saved_key() -> None:
    seen = _Seen(200, {**STANDARD, "version": 2})
    rest = _rest(seen).accept_standard_preview(STANDARD_ID, expected_version=1, idempotency_key=KEY)
    transport = _SyncMcp({**STANDARD, "version": 2})
    mcp = McpClient(transport).accept_standard_preview(STANDARD_ID, expected_version=1)
    request = seen.requests[0]
    assert rest == mcp
    assert (request.method, request.url.path) == (
        "POST",
        f"/v1/standards/{STANDARD_ID}/preview/accept",
    )
    assert request.headers["Idempotency-Key"] == KEY
    assert json.loads(request.content) == {"expected_version": 1}
    assert transport.calls == [
        ("accept_standard_preview", {"standard_id": STANDARD_ID, "expected_version": 1})
    ]
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        _rest(seen).accept_standard_preview(STANDARD_ID, expected_version=0, idempotency_key=KEY)


def test_hiding_a_learning_puts_a_closed_code_and_refuses_an_unknown_one_before_any_request() -> (
    None
):
    seen = _Seen(200, HIDE)
    rest = _rest(seen).set_learning_hidden("calculation_error", True, idempotency_key=KEY)
    transport = _SyncMcp(HIDE)
    mcp = McpClient(transport).set_learning_hidden("calculation_error", True)
    request = seen.requests[0]
    assert isinstance(rest, LearningVisibility)
    assert rest == mcp
    assert (request.method, request.url.path, json.loads(request.content)) == (
        "PUT",
        "/v1/learnings/visibility",
        HIDE,
    )
    assert request.headers["Idempotency-Key"] == KEY
    assert transport.calls == [("set_learning_hidden", HIDE)]
    refused = _Seen(200, HIDE)
    with pytest.raises(ValueError, match="Input should be"):
        _rest(refused).set_learning_hidden("made_up", True, idempotency_key=KEY)
    assert refused.requests == []


def test_learnings_list_the_codes_with_their_hidden_flag() -> None:
    parsed = Learnings.model_validate({"state": "cold_start", "learnings": [HIDE]})
    assert parsed.learnings is not None
    assert (parsed.learnings[0].code, parsed.learnings[0].hidden) == ("calculation_error", True)
    with pytest.raises(ValidationError):
        Learnings.model_validate(
            {"state": "cold_start", "learnings": [{"code": "made_up", "hidden": False}]}
        )


def test_async_clients_match_the_sync_wire() -> None:
    async def scenario() -> tuple[object, ...]:
        async with _rest_async(_Seen(200, VERSIONS)) as versions:
            first = await versions.get_standard_versions(STANDARD_ID)
        async with _rest_async(_Seen(200, HIDE)) as hide:
            second = await hide.set_learning_hidden("calculation_error", True, idempotency_key=KEY)
        mcp = AsyncMcpClient(_AsyncMcp({**STANDARD, "version": 2}))
        return first, second, await mcp.accept_standard_preview(STANDARD_ID, expected_version=1)

    versions, hidden, accepted = asyncio.run(scenario())
    assert isinstance(versions, StandardVersions)
    assert isinstance(hidden, LearningVisibility)
    assert isinstance(accepted, AgentStandard)
    assert accepted.version == 2
