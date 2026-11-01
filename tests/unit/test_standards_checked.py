"""Run.standards_checked: which of your standards a Run was checked against, ids and codes only."""

from __future__ import annotations

import asyncio
import copy
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from zenture import AsyncZentureClient, ZentureClient
from zenture._contract import PublicRunResponse
from zenture._contract.standards_checked import StandardCheckResult, StandardsChecked

API_KEY = "zt_" + "live_" + "client_123"
RUN_ID = "run_33333333333343338333333333333333"
STANDARD_ID = "5b0f3c1e-8a52-4f6e-9d57-3a1e2f6c7b10"
CHECKED: dict[str, Any] = {
    "set_hash": "a" * 64,
    "results": [
        {
            "standard_id": STANDARD_ID,
            "version": 2,
            "strength": "must",
            "owner": "user",
            "result": "violated",
        },
        {
            "standard_id": "6c0f3c1e-8a52-4f6e-9d57-3a1e2f6c7b10",
            "version": 1,
            "strength": "should",
            "owner": "org",
            "result": "n/a",
        },
    ],
}


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


def _rest(payload: dict[str, object]) -> ZentureClient:
    return ZentureClient(
        api_key=API_KEY,
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=payload))
        ),
        max_retries=0,
    )


def test_standards_checked_maps_through_unchanged_over_sync_and_async_reads() -> None:
    payload = _run(standards_checked=CHECKED)

    sync_run = _rest(payload).runs.get(RUN_ID)

    async def scenario() -> PublicRunResponse:
        transport = httpx.MockTransport(lambda _r: httpx.Response(200, json=payload))
        async with AsyncZentureClient(
            api_key=API_KEY, http_client=httpx.AsyncClient(transport=transport), max_retries=0
        ) as client:
            return await client.runs.get(RUN_ID)

    async_run = asyncio.run(scenario())
    for run in (sync_run, async_run):
        assert isinstance(run.standards_checked, StandardsChecked)
        assert run.standards_checked.model_dump(mode="json") == CHECKED
        assert run.standards_checked.results[0].result == "violated"


def test_a_run_without_standards_keeps_the_old_shape() -> None:
    run = PublicRunResponse.model_validate(_run())

    assert run.standards_checked is None
    assert "standards_checked" not in run.model_dump(mode="json", exclude_none=True)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c["results"][0].update(result="partly"),
        lambda c: c["results"][0].update(strength="may"),
        lambda c: c["results"][0].update(owner="team"),
        lambda c: c["results"][0].update(text="the standard text"),
        lambda c: c.update(text="extra"),
        lambda c: c.update(set_hash="short"),
        lambda c: c.update(results=[]),
        lambda c: c.update(results=c["results"][:1] * 17),
    ],
)
def test_the_closed_models_reject_unknown_values_and_extra_keys(mutate: Any) -> None:
    checked = copy.deepcopy(CHECKED)
    mutate(checked)

    with pytest.raises(ValidationError):
        PublicRunResponse.model_validate(_run(standards_checked=checked))


def test_a_result_carries_no_text_field() -> None:
    assert set(StandardCheckResult.model_fields) == {
        "standard_id",
        "version",
        "strength",
        "owner",
        "result",
    }
    assert set(StandardsChecked.model_fields) == {"set_hash", "results"}
