"""runs.wait() stream edges: held streams, stream failures, cursor resume, API authority."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from test_runs_wait_stream import (
    API_KEY,
    RUN_ID,
    STREAM_PATH,
    _event,
    _run,
    _Script,
    _terminal_stream,
)

import zenture._resources.async_runs as async_runs_module
import zenture._resources.runs as runs_module
from zenture import AsyncZentureClient, ZentureClient
from zenture.errors import (
    ZentureAuthenticationError,
    ZenturePollingStoppedError,
    ZenturePollingTimeoutError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

START = 1_000.0


class _Clock:
    """Injected monotonic clock; a held stream spends its read timeout on it."""

    def __init__(self) -> None:
        self.now = START

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        namespace = SimpleNamespace(
            monotonic=lambda: self.now, time=lambda: self.now, sleep=self.sleep
        )
        monkeypatch.setattr(runs_module, "time", namespace)
        monkeypatch.setattr(async_runs_module, "time", namespace)

        async def asleep(seconds: float) -> None:
            self.sleep(seconds)

        monkeypatch.setattr(asyncio, "sleep", asleep)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    sleeps: list[float] = []  # noqa: RUF012 - reset per instance below


class _Held(httpx.SyncByteStream, httpx.AsyncByteStream):
    """Stream that emits `head`, then blocks until its read timeout elapses."""

    def __init__(self, clock: _Clock, timeout: float, head: bytes) -> None:
        self.clock, self.timeout, self.head = clock, timeout, head

    def _block(self) -> None:
        self.clock.now += self.timeout
        raise httpx.ReadTimeout("held stream timed out")

    def __iter__(self) -> Iterator[bytes]:
        if self.head:
            yield self.head
        self._block()

    async def __aiter__(self) -> AsyncIterator[bytes]:
        if self.head:
            yield self.head
        self._block()


def _held_handler(
    clock: _Clock, script: _Script, requests: list[httpx.Request], head: bytes = b""
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != STREAM_PATH:
            return script(request)
        requests.append(request)
        script.calls.append("stream")
        stream = _Held(
            clock, request.extensions["timeout"]["read"], head if len(requests) == 1 else b""
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=stream)

    return handler


def _clients(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[ZentureClient, AsyncZentureClient]:
    return (
        ZentureClient(
            api_key=API_KEY, http_client=httpx.Client(transport=httpx.MockTransport(handler))
        ),
        AsyncZentureClient(
            api_key=API_KEY, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
        ),
    )


async def _call(client: Any, asynchronous: bool, **kwargs: Any) -> Any:
    if asynchronous:
        return await client.runs.wait(RUN_ID, **kwargs)
    return client.runs.wait(RUN_ID, **kwargs)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    fake = _Clock()
    fake.sleeps = []
    fake.install(monkeypatch)
    return fake


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_held_stream_times_out_at_the_deadline_with_the_last_status(
    clock: _Clock, asynchronous: bool
) -> None:
    script = _Script(["queued"])
    requests: list[httpx.Request] = []
    sync_client, async_client = _clients(_held_handler(clock, script, requests))

    with pytest.raises(ZenturePollingTimeoutError) as exc_info:
        await _call(
            async_client if asynchronous else sync_client,
            asynchronous,
            timeout=5.0,
            initial_interval=2.0,
            max_interval=2.0,
        )

    assert exc_info.value.operation_id == RUN_ID
    assert exc_info.value.last_status == "queued"
    assert clock.now <= START + 5.0
    assert script.calls.count("get") == 3
    sync_client.close()
    await async_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_held_stream_stops_within_a_second_without_another_read(
    clock: _Clock, asynchronous: bool
) -> None:
    script = _Script(["queued", "completed"])
    requests: list[httpx.Request] = []
    sync_client, async_client = _clients(_held_handler(clock, script, requests))

    with pytest.raises(ZenturePollingStoppedError):
        await _call(
            async_client if asynchronous else sync_client,
            asynchronous,
            timeout=60.0,
            initial_interval=8.0,
            max_interval=8.0,
            stop=lambda: clock.now >= START + 0.5,
        )

    assert clock.now - START <= 1.0
    assert script.calls == ["get", "stream"]
    sync_client.close()
    await async_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_silent_held_stream_reopens_each_second_from_the_last_cursor(
    clock: _Clock, asynchronous: bool
) -> None:
    script = _Script(["queued", "completed"])
    requests: list[httpx.Request] = []
    handler = _held_handler(clock, script, requests, head=_event(1, "running"))
    sync_client, async_client = _clients(handler)

    result = await _call(
        async_client if asynchronous else sync_client,
        asynchronous,
        timeout=60.0,
        initial_interval=3.0,
        max_interval=3.0,
        stop=lambda: False,
    )

    assert result.status.value == "completed"
    assert [r.extensions["timeout"]["read"] for r in requests] == [1.0, 1.0, 1.0]
    assert [r.headers.get("last-event-id") for r in requests] == [
        None,
        "cursor_001",
        "cursor_001",
    ]
    sync_client.close()
    await async_client.aclose()


def _failing_stream(kind: str) -> Callable[[], httpx.Response]:
    if kind == "transport":

        def fail() -> httpx.Response:
            raise httpx.ConnectError("stream connection refused")

        return fail
    return lambda: httpx.Response(
        int(kind), json={"error": {"code": "dependency_unavailable", "message": "down"}}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("kind", ["500", "transport"])
async def test_a_failing_stream_is_tried_once_then_polling_backs_off(
    clock: _Clock, asynchronous: bool, kind: str
) -> None:
    script = _Script(["queued", "running", "completed"], _failing_stream(kind))
    sync_client, async_client = _clients(script)

    result = await _call(
        async_client if asynchronous else sync_client,
        asynchronous,
        timeout=60.0,
        initial_interval=1.0,
        max_interval=8.0,
    )

    assert result.status.value == "completed"
    assert script.calls.count("stream") == 1
    assert clock.sleeps == pytest.approx([1.0, 2.0])
    sync_client.close()
    await async_client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_an_unauthorized_stream_surfaces_the_auth_error_from_the_read(
    clock: _Clock, asynchronous: bool
) -> None:
    script = _Script(["queued"], lambda: httpx.Response(401, json=_unauthorized()))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != STREAM_PATH and script.calls.count("get") >= 1:
            return httpx.Response(401, json=_unauthorized())
        return script(request)

    sync_client, async_client = _clients(handler)

    with pytest.raises(ZentureAuthenticationError):
        await _call(
            async_client if asynchronous else sync_client,
            asynchronous,
            timeout=60.0,
            initial_interval=1.0,
            max_interval=8.0,
        )

    assert script.calls.count("stream") == 1
    sync_client.close()
    await async_client.aclose()


def _unauthorized() -> dict[str, Any]:
    return {
        "error": {"code": "unauthorized", "message": "invalid credentials"},
        "request_id": "req_00000000000000000000000000000000",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_a_terminal_event_never_overrides_the_api_run(
    clock: _Clock, asynchronous: bool
) -> None:
    script = _Script(["queued", "running", "completed"], _terminal_stream)
    sync_client, async_client = _clients(script)

    result = await _call(
        async_client if asynchronous else sync_client,
        asynchronous,
        timeout=60.0,
        initial_interval=1.0,
        max_interval=8.0,
    )

    assert result.model_dump() == _parsed(_run("completed"))
    assert script.calls == ["get", "stream", "get", "stream", "get"]
    sync_client.close()
    await async_client.aclose()


def _parsed(payload: dict[str, object]) -> dict[str, Any]:
    from zenture._contract import PublicRunResponse

    return PublicRunResponse.model_validate(payload).model_dump()
