"""Optional reference_file on the Run helpers and the MCP client; reference_file_attached on Runs."""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError

from zenture import AsyncZentureClient, ZentureClient
from zenture._contract import PublicRunListItem, PublicRunResponse
from zenture._contract.safe_result_findings import SafeResultLocation
from zenture._mcp import McpClient

# Deterministic synthetic fixture for MockTransport-only tests; no real credentials/network.
API_KEY = f"zt_live_{UUID(int=0).hex}"
REFERENCE = "art_fedcba0987654321"
ANSWER = {"type": "text", "value": "The answer."}
FILE_ANSWER = {"type": "zenture_ref", "value": "art_abcdefgh"}
RUN_ID = "run_33333333333343338333333333333333"


def _run() -> dict[str, object]:
    return {
        "run_id": RUN_ID,
        "generation": 1,
        "family": "knowledge",
        "work_type": "answer",
        "input_kind": "text",
        "profile": "standard",
        "status": "queued",
        "created_at": "2026-09-10T12:00:00Z",
        "updated_at": "2026-09-10T12:00:00Z",
        "queue": {"queue_reason": "queue:admitted", "jobs_ahead": 0},
        "cancellation_requested": False,
    }


def _proposal() -> dict[str, object]:
    return {
        "proposal_id": "33333333-3333-4333-8333-333333333333",
        "proposal_version": 1,
        "expires_at": "2026-08-30T12:30:00Z",
        "inferred_work_type": "answer",
        "task_contract_summary": {
            "work_type": "answer",
            "summary_ref": "snapshot:task-summary-v1",
            "requirement_count": 1,
        },
        "planned_checks": [],
        "unavailable_checks": [],
        "expected_duration_seconds": 30,
        "estimated_credits": "12",
        "maximum_credits": "24",
        "start_admissible": True,
        "proposal_hash": "b" * 64,
    }


def _sync(prepared: list[dict[str, object]]) -> ZentureClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/runs/prepare":
            prepared.append(json.loads(request.content))
            return httpx.Response(200, json=_proposal())
        return httpx.Response(202, json=_run())

    return ZentureClient(
        api_key=API_KEY,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )


def test_prepare_and_run_send_the_reference_file_as_a_zenture_ref_only_when_given() -> None:
    prepared: list[dict[str, object]] = []
    client = _sync(prepared)
    try:
        client.runs.prepare(task="Check.", artifact=ANSWER, idempotency_key="k")
        client.runs.prepare(
            task="Check.", artifact=ANSWER, idempotency_key="k", reference_file=REFERENCE
        )
        client.runs.run(
            task="Check.", artifact=ANSWER, idempotency_key="k", reference_file=REFERENCE
        )
    finally:
        client.close()
    assert "reference_file" not in prepared[0]
    assert prepared[1]["reference_file"] == {"type": "zenture_ref", "value": REFERENCE}
    assert prepared[2] == prepared[1]


@pytest.mark.parametrize("bad", ["", "run_1234567890", "../" + REFERENCE, "art_", REFERENCE + "/x"])
def test_a_malformed_reference_file_fails_locally_before_any_request(bad: str) -> None:
    prepared: list[dict[str, object]] = []
    client = _sync(prepared)
    try:
        with pytest.raises(ValidationError):
            client.runs.prepare(
                task="Check.", artifact=ANSWER, idempotency_key="k", reference_file=bad
            )
    finally:
        client.close()
    assert prepared == []


def test_a_reference_file_next_to_a_file_answer_fails_locally() -> None:
    prepared: list[dict[str, object]] = []
    client = _sync(prepared)
    try:
        with pytest.raises(ValidationError):
            client.runs.prepare(
                task="Check.", artifact=FILE_ANSWER, idempotency_key="k", reference_file=REFERENCE
            )
    finally:
        client.close()
    assert prepared == []


def test_async_prepare_and_run_send_the_reference_file() -> None:
    prepared: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/runs/prepare":
            prepared.append(json.loads(request.content))
            return httpx.Response(200, json=_proposal())
        return httpx.Response(202, json=_run())

    async def scenario() -> None:
        client = AsyncZentureClient(
            api_key=API_KEY,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            max_retries=0,
        )
        try:
            await client.runs.run(
                task="Check.", artifact=ANSWER, idempotency_key="k", reference_file=REFERENCE
            )
        finally:
            await client.aclose()

    asyncio.run(scenario())
    assert prepared[0]["reference_file"] == {"type": "zenture_ref", "value": REFERENCE}


def test_runs_and_list_items_carry_reference_file_attached_defaulting_to_false() -> None:
    assert PublicRunResponse.model_validate(_run()).reference_file_attached is False
    assert (
        PublicRunResponse.model_validate(
            {**_run(), "reference_file_attached": True}
        ).reference_file_attached
        is True
    )
    item = {
        "run_id": _run()["run_id"],
        "status": "queued",
        "profile": "standard",
        "created_at": "2026-09-10T12:00:00Z",
        "updated_at": "2026-09-10T12:00:00Z",
    }
    assert PublicRunListItem.model_validate(item).reference_file_attached is False
    assert (
        PublicRunListItem.model_validate(
            {**item, "reference_file_attached": True}
        ).reference_file_attached
        is True
    )


def test_a_reference_file_location_parses_with_its_file_facts() -> None:
    location = SafeResultLocation.model_validate(
        {
            "source": "reference_file",
            "start": 4,
            "end": 9,
            "status": "shown",
            "excerpt": "Total",
            "page": 2,
            "sheet": "Sheet1",
            "cell": "B7",
            "from_image": False,
        }
    )
    assert location.source == "reference_file"
    assert location.cell == "B7"
    with pytest.raises(ValidationError):
        SafeResultLocation.model_validate(
            {"source": "elsewhere", "start": 0, "end": 1, "status": "withheld"}
        )


class _Transport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def list_tools(self) -> object:
        from zenture._mcp import PRODUCT_TOOL_NAMES

        return {"tools": [{"name": name} for name in PRODUCT_TOOL_NAMES]}

    def call_tool(self, name: str, arguments: Any) -> object:
        self.calls.append((name, dict(arguments)))
        payload = {**_run(), "idempotency_key": arguments["idempotency_key"]}
        return type("R", (), {"structured_content": payload, "is_error": False})()


def test_the_mcp_client_passes_the_reference_file_as_an_art_ref_only_when_given() -> None:
    transport = _Transport()
    client = McpClient(cast("Any", transport))
    client.run(task="Check.", artifact=ANSWER)
    client.run(task="Check.", artifact=ANSWER, reference_file=REFERENCE)
    assert "reference_file" not in transport.calls[0][1]
    assert transport.calls[1][1]["reference_file"] == REFERENCE
    with pytest.raises(ValidationError):
        client.run(task="Check.", artifact=FILE_ANSWER, reference_file=REFERENCE)
    assert len(transport.calls) == 2
