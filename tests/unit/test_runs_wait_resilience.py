"""runs.wait() honours the server poll hint and re-opens a broken stream from its cursor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
import pytest
from test_runs_wait_stream import API_KEY, RUN_PATH, STREAM_PATH, _event, _run, _sse
from test_runs_wait_stream_edges import START, _call, _Clock

from zenture import AsyncZentureClient, ZentureClient

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    fake = _Clock()
    fake.sleeps = []
    fake.install(monkeypatch)
    return fake


class _Server:
    """Serves Run reads from `reads` (status, retry_after) and stream opens from `streams`."""

    def __init__(
        self,
        reads: list[tuple[str, int | None]],
        streams: list[Callable[[], httpx.Response]] | None = None,
    ) -> None:
        self.reads, self.streams = reads, streams or []
        self.stream_requests: list[httpx.Request] = []
        self.get_count = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == STREAM_PATH:
            self.stream_requests.append(request)
            index = len(self.stream_requests) - 1
            if index >= len(self.streams):
                return httpx.Response(404, json={"error": {"code": "not_found"}})
            return self.streams[index]()
        assert request.url.path == RUN_PATH
        status, retry_after = self.reads[min(self.get_count, len(self.reads) - 1)]
        self.get_count += 1
        body: dict[str, Any] = _run(status)
        if retry_after is not None:
            body.update(retry_after_seconds=retry_after, result="pending")
        return httpx.Response(200, json=body)


def _clients(server: _Server) -> tuple[ZentureClient, AsyncZentureClient]:
    return (
        ZentureClient(
            api_key=API_KEY, http_client=httpx.Client(transport=httpx.MockTransport(server))
        ),
        AsyncZentureClient(
            api_key=API_KEY, http_client=httpx.AsyncClient(transport=httpx.MockTransport(server))
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(("hint", "expected"), [(5, 5.0), (60, 10.0), (1, 1.0)])
async def test_poll_hint_sets_the_next_poll_delay_within_one_to_ten_seconds(
    clock: _Clock, asynchronous: bool, hint: int, expected: float
) -> None:
    server = _Server([("running", hint), ("completed", None)])
    sync_client, async_client = _clients(server)

    result = await _call(
        async_client if asynchronous else sync_client,
        asynchronous,
        timeout=120.0,
        initial_interval=1.0,
        max_interval=8.0,
    )

    assert result.status.value == "completed"
    assert clock.sleeps == pytest.approx([expected])
    sync_client.close()
    await async_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_broken_stream_is_reopened_from_the_last_cursor_until_the_terminal_event(
    clock: _Clock, asynchronous: bool
) -> None:
    server = _Server(
        [("running", None), ("completed", None)],
        [
            lambda: _sse(_event(1, "running")),
            lambda: _sse(_event(2, "running")),
            lambda: _sse(_event(3, "completed")),
        ],
    )
    sync_client, async_client = _clients(server)

    result = await _call(
        async_client if asynchronous else sync_client,
        asynchronous,
        timeout=120.0,
        initial_interval=8.0,
        max_interval=8.0,
    )

    assert result.status.value == "completed"
    assert server.get_count == 2
    assert [r.headers.get("last-event-id") for r in server.stream_requests] == [
        None,
        "cursor_001",
        "cursor_002",
    ]
    assert len(clock.sleeps) == 2
    assert all(1.0 <= delay <= 8.0 for delay in clock.sleeps)
    assert clock.now - START < 8.0
    sync_client.close()
    await async_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_stream_that_worked_is_tried_again_in_the_next_window(
    clock: _Clock, asynchronous: bool
) -> None:
    def unavailable() -> httpx.Response:
        return httpx.Response(500, json={"error": {"code": "dependency_unavailable"}})

    server = _Server(
        [("running", None), ("running", None), ("completed", None)],
        [lambda: _sse(_event(1, "running")), unavailable, lambda: _sse(_event(2, "completed"))],
    )
    sync_client, async_client = _clients(server)

    result = await _call(
        async_client if asynchronous else sync_client,
        asynchronous,
        timeout=120.0,
        initial_interval=2.0,
        max_interval=8.0,
    )

    assert result.status.value == "completed"
    assert [r.headers.get("last-event-id") for r in server.stream_requests] == [
        None,
        "cursor_001",
        "cursor_001",
    ]
    sync_client.close()
    await async_client.aclose()
