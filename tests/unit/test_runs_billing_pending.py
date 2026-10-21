"""A terminal Run may still have pending billing; the final Credits arrive by re-reading it."""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest
from test_runs_wait_stream import (
    API_KEY,
    RUN_ID,
    RUN_PATH,
    STREAM_PATH,
    _event,  # pyright: ignore[reportPrivateUsage] -- shared wait test helpers
    _run,  # pyright: ignore[reportPrivateUsage] -- shared wait test helpers
    _sse,  # pyright: ignore[reportPrivateUsage] -- shared wait test helpers
)

from zenture import AsyncZentureClient, ZentureClient
from zenture._contract.models import PublicRunEvent

_PENDING = {"schema_version": "run.terminal_billing_summary.v1", "status": "pending"}
_SETTLED = {
    "schema_version": "run.terminal_billing_summary.v1",
    "status": "settled",
    "final_credits": {"status": "available", "amount": "1.25", "unit": "credits"},
}


class _Server:
    """Serves a terminal Run: billing pending on the first reads, settled afterwards."""

    def __init__(self, pending_reads: int) -> None:
        self.pending_reads = pending_reads
        self.reads = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == STREAM_PATH:
            return _sse(_event(1, "running"), _event(2, "completed"), _billing_event(3))
        assert request.url.path == RUN_PATH
        pending = self.reads < self.pending_reads
        self.reads += 1
        return httpx.Response(
            200, json={**_run("completed"), "billing_summary": _PENDING if pending else _SETTLED}
        )


def _billing_event(sequence: int) -> bytes:
    payload = {
        "type": "run.event",
        "event_id": f"event_{sequence:03d}",
        "run_id": RUN_ID,
        "sequence": sequence,
        "status": "completed",
        "message_key": "run.billing.settled",
        "event_cursor": f"cursor_{sequence:03d}",
    }
    return f"event: run.event\ndata: {json.dumps(payload)}\n\n".encode()


def _sync(server: _Server) -> ZentureClient:
    return ZentureClient(
        api_key=API_KEY, http_client=httpx.Client(transport=httpx.MockTransport(server))
    )


def test_terminal_run_with_pending_billing_is_valid_and_carries_no_credits() -> None:
    client = _sync(_Server(pending_reads=1))

    run = client.runs.get(RUN_ID)

    assert run.status.value == "completed"
    assert run.billing_summary is not None
    assert run.billing_summary.status == "pending"
    assert run.billing_summary.final_credits is None
    client.close()


def test_wait_returns_on_the_terminal_status_and_a_later_read_gives_the_final_credits() -> None:
    server = _Server(pending_reads=2)  # wait's own read and the first re-read are pending
    client = _sync(server)

    waited = client.runs.wait(RUN_ID, timeout=30.0)
    assert waited.billing_summary is not None
    assert waited.billing_summary.status == "pending"

    reread = client.runs.get(RUN_ID)
    assert reread.billing_summary is not None
    assert reread.billing_summary.status == "pending"
    settled = client.runs.get(RUN_ID)
    assert settled.billing_summary is not None
    assert settled.billing_summary.status == "settled"
    assert settled.billing_summary.final_credits is not None
    assert Decimal(settled.billing_summary.final_credits.amount) == Decimal("1.25")  # type: ignore[union-attr]
    client.close()


def test_billing_settled_event_after_the_terminal_event_is_a_valid_event() -> None:
    event = PublicRunEvent.model_validate(
        {
            "type": "run.event",
            "event_id": "event_003",
            "run_id": RUN_ID,
            "sequence": 3,
            "status": "completed",
            "message_key": "run.billing.settled",
            "event_cursor": "cursor_003",
        }
    )
    assert event.message_key == "run.billing.settled"
    assert event.status == "completed"


def test_iter_events_still_ends_at_the_terminal_event_before_the_billing_event() -> None:
    client = _sync(_Server(pending_reads=1))

    seen = [m.message_key for m in client.runs.iter_events(RUN_ID) if isinstance(m, PublicRunEvent)]

    assert seen == ["run.status.running", "run.status.completed"]
    client.close()


@pytest.mark.asyncio
async def test_async_wait_and_reread_follow_the_same_pattern() -> None:
    server = _Server(pending_reads=2)
    client = AsyncZentureClient(
        api_key=API_KEY, http_client=httpx.AsyncClient(transport=httpx.MockTransport(server))
    )

    waited = await client.runs.wait(RUN_ID, timeout=30.0)
    assert waited.billing_summary is not None
    assert waited.billing_summary.status == "pending"
    await client.runs.get(RUN_ID)
    settled = await client.runs.get(RUN_ID)
    assert settled.billing_summary is not None
    assert settled.billing_summary.status == "settled"
    await client.aclose()
