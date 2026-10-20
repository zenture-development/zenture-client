"""runs.wait() wakes on the Run event stream and polls only as a bounded fallback."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import UUID

import httpx
import pytest

from zenture import AsyncZentureClient, ZentureClient
from zenture.errors import ZenturePollingStoppedError, ZenturePollingTimeoutError

if TYPE_CHECKING:
    from collections.abc import Callable

API_KEY = f"zt_live_{UUID(int=0).hex}"
RUN_ID = "run_33333333333343338333333333333333"
RUN_PATH = f"/v1/runs/{RUN_ID}"
STREAM_PATH = f"{RUN_PATH}/events/stream"


def _run(status: str) -> dict[str, object]:
    return {
        "run_id": RUN_ID,
        "generation": 1,
        "family": "knowledge",
        "work_type": "answer",
        "profile": "standard",
        "status": status,
        "created_at": "2026-08-30T12:00:00Z",
        "updated_at": "2026-08-30T12:00:00Z",
        "queue": {"queue_reason": "queue:admitted", "jobs_ahead": 0},
        "cancellation_requested": False,
    }


def _event(sequence: int, status: str) -> bytes:
    payload = {
        "type": "run.event",
        "event_id": f"event_{sequence:03d}",
        "run_id": RUN_ID,
        "sequence": sequence,
        "status": status,
        "message_key": f"run.status.{status}",
        "event_cursor": f"cursor_{sequence:03d}",
    }
    return f"event: run.event\ndata: {json.dumps(payload)}\n\n".encode()


def _sse(*parts: bytes) -> httpx.Response:
    return httpx.Response(
        200, headers={"content-type": "text/event-stream"}, content=b"".join(parts)
    )


class _Script:
    """Serves Run reads from a status list and the stream from a callable."""

    def __init__(
        self, statuses: list[str], stream: Callable[[], httpx.Response] | None = None
    ) -> None:
        self.statuses = statuses
        self.stream = stream
        self.calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == STREAM_PATH:
            self.calls.append("stream")
            if self.stream is None:
                return httpx.Response(404, json={"error": {"code": "not_found"}})
            return self.stream()
        assert request.url.path == RUN_PATH
        reads = self.calls.count("get")
        self.calls.append("get")
        return httpx.Response(200, json=_run(self.statuses[min(reads, len(self.statuses) - 1)]))


def _no_sleep(monkeypatch: pytest.MonkeyPatch, module: str) -> list[float]:
    import importlib
    import time

    sleeps: list[float] = []
    runs_module = importlib.import_module(module)
    monkeypatch.setattr(
        runs_module,
        "time",
        SimpleNamespace(monotonic=time.monotonic, time=time.time, sleep=lambda s: sleeps.append(s)),
    )
    return sleeps


def _sync(script: _Script) -> ZentureClient:
    return ZentureClient(
        api_key=API_KEY, http_client=httpx.Client(transport=httpx.MockTransport(script))
    )


def _async(script: _Script) -> AsyncZentureClient:
    return AsyncZentureClient(
        api_key=API_KEY, http_client=httpx.AsyncClient(transport=httpx.MockTransport(script))
    )


def _terminal_stream() -> httpx.Response:
    return _sse(_event(1, "running"), _event(2, "completed"))


def test_sync_wait_wakes_on_terminal_event_without_sleeping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps = _no_sleep(monkeypatch, "zenture._resources.runs")
    script = _Script(["queued", "completed"], _terminal_stream)
    client = _sync(script)

    result = client.runs.wait(RUN_ID, timeout=30.0, initial_interval=8.0, max_interval=8.0)

    assert result.status.value == "completed"
    assert script.calls == ["get", "stream", "get"]
    assert sleeps == []
    client.close()


def test_sync_wait_polls_when_the_stream_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps = _no_sleep(monkeypatch, "zenture._resources.runs")
    script = _Script(["queued", "running", "completed"], stream=None)
    client = _sync(script)

    result = client.runs.wait(RUN_ID, timeout=30.0, initial_interval=1.0, max_interval=8.0)

    assert result.status.value == "completed"
    assert script.calls.count("stream") == 1
    assert script.calls.count("get") == 3
    assert sleeps == pytest.approx([1.0, 2.0], abs=0.05)
    client.close()


def test_sync_wait_reads_again_when_the_stream_ends_without_a_terminal_event() -> None:
    script = _Script(["queued", "completed"], lambda: _sse(_event(1, "running")))
    client = _sync(script)

    result = client.runs.wait(RUN_ID, timeout=30.0, initial_interval=0.05, max_interval=0.05)

    assert result.status.value == "completed"
    assert script.calls[0] == "get"
    assert script.calls[-1] == "get"
    client.close()


def test_sync_wait_honours_timeout_while_the_stream_stays_silent() -> None:
    script = _Script(["queued"], lambda: _sse(_event(1, "running")))
    client = _sync(script)

    with pytest.raises(ZenturePollingTimeoutError) as exc_info:
        client.runs.wait(RUN_ID, timeout=0.2, initial_interval=0.05, max_interval=0.05)

    assert exc_info.value.operation_id == RUN_ID
    assert exc_info.value.last_status == "queued"
    client.close()


def test_sync_wait_honours_stop_while_listening() -> None:
    script = _Script(["queued"], lambda: _sse(_event(1, "running")))
    client = _sync(script)
    stops = iter([False, False, False] + [True] * 1000)

    with pytest.raises(ZenturePollingStoppedError):
        client.runs.wait(RUN_ID, timeout=30.0, initial_interval=0.05, stop=lambda: next(stops))

    client.close()


@pytest.mark.asyncio
async def test_async_wait_wakes_on_terminal_event_without_sleeping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    slept: list[float] = []

    async def no_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    script = _Script(["queued", "completed"], _terminal_stream)
    client = _async(script)

    result = await client.runs.wait(RUN_ID, timeout=30.0, initial_interval=8.0, max_interval=8.0)

    assert result.status.value == "completed"
    assert script.calls == ["get", "stream", "get"]
    assert slept == []
    await client.aclose()


@pytest.mark.asyncio
async def test_async_wait_polls_when_the_stream_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    slept: list[float] = []

    async def no_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", no_sleep)
    script = _Script(["queued", "running", "completed"], stream=None)
    client = _async(script)

    result = await client.runs.wait(RUN_ID, timeout=30.0, initial_interval=1.0, max_interval=8.0)

    assert result.status.value == "completed"
    assert script.calls.count("stream") == 1
    assert slept == pytest.approx([1.0, 2.0], abs=0.05)
    await client.aclose()


@pytest.mark.asyncio
async def test_async_wait_honours_timeout_while_the_stream_stays_silent() -> None:
    script = _Script(["queued"], lambda: _sse(_event(1, "running")))
    client = _async(script)

    with pytest.raises(ZenturePollingTimeoutError) as exc_info:
        await client.runs.wait(RUN_ID, timeout=0.2, initial_interval=0.05, max_interval=0.05)

    assert exc_info.value.last_status == "queued"
    await client.aclose()
