"""runs.wait() pacing: server poll hint and bounded re-opening of a broken Run event stream."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from zenture._resources._run_wait import listen_for_terminal, listen_for_terminal_async

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

_MIN_POLL_HINT = 1.0
_MAX_POLL_HINT = 10.0
_STREAM_RECONNECT_JITTER_RATIO = 0.25
_MIN_STREAM_RECONNECT_INTERVAL = 1.0


def bounded_stream_retry_delay(
    *, interval: float, max_interval: float, remaining: float | None = None
) -> float:
    """Add bounded reconnect jitter without exceeding the active wait budget."""

    if interval <= 0.0:
        return 0.0
    jitter_limit = min(
        interval * _STREAM_RECONNECT_JITTER_RATIO,
        max(0.0, max_interval - interval),
    )
    delay = interval + random.uniform(0.0, jitter_limit)
    if remaining is not None:
        delay = min(delay, max(0.0, remaining))
    return delay


def poll_window(interval: float, retry_after_seconds: int | None) -> float:
    """Return the next poll delay: the server hint bounded to 1..10 s, else the backoff interval."""

    if retry_after_seconds is None:
        return interval
    return min(max(float(retry_after_seconds), _MIN_POLL_HINT), _MAX_POLL_HINT)


def listen_reopening(
    transport: Any,
    run_id: str,
    *,
    end: float,
    cursor: str | None,
    stop: Any,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
    max_interval: float,
) -> tuple[bool, str | None]:
    """Listen until a terminal event or `end`, re-opening a broken stream from its cursor.

    A stream that delivered events and then broke is re-opened after a bounded delay. One
    that fails without progress is left until the next window (the rest of this one is
    slept). False is returned only for a stream that never delivered an event.
    """

    while True:
        before = cursor
        usable, cursor = listen_for_terminal(
            transport, run_id, end=end, cursor=cursor, stop=stop, clock=clock
        )
        if usable:
            return True, cursor
        if cursor is None:
            return False, None
        remaining = max(0.0, end - clock())
        if cursor == before:
            sleep(remaining)
            return True, cursor
        sleep(_reconnect_delay(max_interval, remaining))
        if clock() >= end:
            return True, cursor


async def listen_reopening_async(
    transport: Any,
    run_id: str,
    *,
    end: float,
    cursor: str | None,
    stop: Any,
    clock: Callable[[], float],
    sleep: Callable[[float], Awaitable[None]],
    max_interval: float,
) -> tuple[bool, str | None]:
    """Async variant of listen_reopening."""

    while True:
        before = cursor
        usable, cursor = await listen_for_terminal_async(
            transport, run_id, end=end, cursor=cursor, stop=stop, clock=clock
        )
        if usable:
            return True, cursor
        if cursor is None:
            return False, None
        remaining = max(0.0, end - clock())
        if cursor == before:
            await sleep(remaining)
            return True, cursor
        await sleep(_reconnect_delay(max_interval, remaining))
        if clock() >= end:
            return True, cursor


def _reconnect_delay(max_interval: float, remaining: float) -> float:
    delay = bounded_stream_retry_delay(
        interval=_MIN_STREAM_RECONNECT_INTERVAL, max_interval=max_interval, remaining=remaining
    )
    return min(delay, remaining)


class StreamWindow:
    """Cursor and availability of the Run event stream across the poll windows of one wait."""

    def __init__(
        self,
        transport: Any,
        run_id: str,
        *,
        stop: Any,
        clock: Callable[[], float],
        sleep: Callable[[float], Any],
        max_interval: float,
    ) -> None:
        self._args = (transport, run_id)
        self._stop = stop
        self._clock = clock
        self._sleep = sleep
        self._max_interval = max_interval
        self.listening = True
        self.cursor: str | None = None

    def wait(self, end: float) -> None:
        """Hold the stream until a terminal event or `end`; poll-sleep when it is unavailable."""

        if self.listening:
            self.listening, self.cursor = listen_reopening(
                *self._args,
                end=end,
                cursor=self.cursor,
                stop=self._stop,
                clock=self._clock,
                sleep=self._sleep,
                max_interval=self._max_interval,
            )
        if not self.listening:
            self._sleep(max(0.0, end - self._clock()))

    async def wait_async(self, end: float) -> None:
        """Async variant of wait."""

        if self.listening:
            self.listening, self.cursor = await listen_reopening_async(
                *self._args,
                end=end,
                cursor=self.cursor,
                stop=self._stop,
                clock=self._clock,
                sleep=self._sleep,
                max_interval=self._max_interval,
            )
        if not self.listening:
            await self._sleep(max(0.0, end - self._clock()))
