"""Run event stream reading shared by iter_events and runs.wait()."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, cast

import httpx

from zenture._contract import (
    PublicRunEvent,
    PublicRunHeartbeat,
    PublicRunStreamError,
    PublicRunStreamMessage,
)
from zenture._resources._utils import path_segment
from zenture.errors import (
    ZentureAPIError,
    ZenturePollingStoppedError,
    ZentureResponseError,
    ZentureTransportError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

MAX_STREAM_EVENT_BYTES = 512 * 1024
# With a stop predicate one stream is held for at most this long before stop is re-read.
_STOP_CHECK_INTERVAL = 1.0

_TERMINAL_STREAM_STATUSES = frozenset(
    {"completed", "failed", "cancelled", "expired", "budget_exhausted"}
)


def is_terminal_stream_message(message: PublicRunStreamMessage) -> bool:
    """Return whether a stream message proves the Run stream is terminal."""

    if isinstance(message, PublicRunEvent):
        return message.status in _TERMINAL_STREAM_STATUSES
    return isinstance(message, PublicRunStreamError) and message.terminal


def is_stream_read_timeout(error: Exception) -> bool:
    """Return whether transport wrapped an HTTPX sync read timeout."""

    return isinstance(error, ZentureTransportError) and isinstance(
        error.__cause__, httpx.ReadTimeout
    )


def parse_sse_events(
    lines: Iterator[str], *, expected_run_id: str
) -> Iterator[PublicRunStreamMessage]:
    data: list[str] = []
    event_type = ""
    event_bytes = 0
    for raw_line in lines:
        line = str(raw_line)
        event_bytes += len(line.encode("utf-8")) + 1
        if event_bytes > MAX_STREAM_EVENT_BYTES:
            raise ValueError("public Run event stream record is too large")
        if not line:
            if data:
                try:
                    payload = json.loads("\n".join(data))
                except (TypeError, ValueError):
                    raise ValueError("public Run event stream contained invalid JSON") from None
                yield _parse_stream_message(payload, event_type, expected_run_id=expected_run_id)
                data.clear()
                event_type = ""
            event_bytes = 0
            continue
        if line.startswith(":") or line.startswith("id:"):
            continue
        if line.startswith("event:"):
            event_type = line[6:].strip()
            continue
        if line.startswith("data:"):
            data.append(line[5:].lstrip())


def _parse_stream_message(
    payload: object, event_type: str, *, expected_run_id: str
) -> PublicRunStreamMessage:
    if not isinstance(payload, dict):
        raise ValueError("public Run event payload must be an object")
    mapping = cast("dict[str, object]", payload)
    message_type = mapping.get("type") or event_type
    if message_type == "run.event":
        message: PublicRunStreamMessage = PublicRunEvent.model_validate(mapping)
    elif message_type == "run.heartbeat":
        message = PublicRunHeartbeat.model_validate(mapping)
    elif message_type == "run.error":
        message = PublicRunStreamError.model_validate(mapping)
    else:
        raise ValueError("public Run event type is unsupported")
    if message.run_id != expected_run_id:
        raise ValueError("public Run event run_id did not match the requested Run")
    return message


async def parse_sse_events_async(
    lines: AsyncIterator[str], *, expected_run_id: str
) -> AsyncIterator[PublicRunStreamMessage]:
    data: list[str] = []
    event_type = ""
    event_bytes = 0
    async for raw_line in lines:
        line = str(raw_line)
        event_bytes += len(line.encode("utf-8")) + 1
        if event_bytes > MAX_STREAM_EVENT_BYTES:
            raise ValueError("public Run event stream record is too large")
        if not line:
            if data:
                try:
                    payload = json.loads("\n".join(data))
                except (TypeError, ValueError):
                    raise ValueError("public Run event stream contained invalid JSON") from None
                yield _parse_stream_message(payload, event_type, expected_run_id=expected_run_id)
                data.clear()
                event_type = ""
            event_bytes = 0
            continue
        if line.startswith(":") or line.startswith("id:"):
            continue
        if line.startswith("event:"):
            event_type = line[6:].strip()
            continue
        if line.startswith("data:"):
            data.append(line[5:].lstrip())


def _stream_request(run_id: str, cursor: str | None) -> tuple[str, dict[str, str]]:
    headers = {"Accept": "text/event-stream"}
    if cursor is not None:
        headers["Last-Event-ID"] = cursor
    return f"/runs/{path_segment(run_id)}/events/stream", headers


def listen_for_terminal(
    transport: Any,
    run_id: str,
    *,
    end: float,
    cursor: str | None,
    stop: Any,
    clock: Callable[[], float],
) -> tuple[bool, str | None]:
    """Hold the Run event stream until a terminal event or `end` (on `clock`).

    Returns (stream usable, resume cursor). False means the stream was unavailable
    or dropped early, so the caller polls for the rest of its window.
    """

    try:
        while True:
            if callable(stop) and stop():
                raise ZenturePollingStoppedError(operation_id=run_id)
            remaining = end - clock()
            if remaining <= 0:
                return True, cursor
            path, headers = _stream_request(run_id, cursor)
            read_timeout = min(remaining, _STOP_CHECK_INTERVAL) if callable(stop) else remaining
            try:
                with transport.stream("GET", path, headers=headers, timeout=read_timeout) as resp:
                    for message in parse_sse_events(resp.iter_lines(), expected_run_id=run_id):
                        cursor = getattr(message, "event_cursor", None) or cursor
                        if is_terminal_stream_message(message):
                            return True, cursor
                        if callable(stop) and stop():
                            raise ZenturePollingStoppedError(operation_id=run_id)
                        if clock() >= end:
                            return True, cursor
                return False, cursor
            except ZentureTransportError as exc:
                if not is_stream_read_timeout(exc):
                    raise
    except (ZentureAPIError, ZentureTransportError, ZentureResponseError, ValueError):
        return False, cursor


async def listen_for_terminal_async(
    transport: Any,
    run_id: str,
    *,
    end: float,
    cursor: str | None,
    stop: Any,
    clock: Callable[[], float],
) -> tuple[bool, str | None]:
    """Async variant of listen_for_terminal."""

    try:
        while True:
            if callable(stop) and stop():
                raise ZenturePollingStoppedError(operation_id=run_id)
            remaining = end - clock()
            if remaining <= 0:
                return True, cursor
            path, headers = _stream_request(run_id, cursor)
            chunk = min(remaining, _STOP_CHECK_INTERVAL) if callable(stop) else remaining
            try:
                async with asyncio.timeout(chunk):
                    async with transport.stream(
                        "GET", path, headers=headers, timeout=chunk
                    ) as resp:
                        async for message in parse_sse_events_async(
                            resp.aiter_lines(), expected_run_id=run_id
                        ):
                            cursor = getattr(message, "event_cursor", None) or cursor
                            if is_terminal_stream_message(message):
                                return True, cursor
                            if callable(stop) and stop():
                                raise ZenturePollingStoppedError(operation_id=run_id)
                return False, cursor
            except TimeoutError:
                continue
            except ZentureTransportError as exc:
                if not is_stream_read_timeout(exc):
                    raise
    except (ZentureAPIError, ZentureTransportError, ZentureResponseError, ValueError):
        return False, cursor
