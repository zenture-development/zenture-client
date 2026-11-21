"""The MCP peer sends `wait_seconds` itself, derived from its own read timeout.

A server default can change (the hosted server went 20 -> 40 -> 20), and a server wait that
outlives the client's read timeout turns into a retryable transport failure. The peer therefore
states the wait on every waiting call: never above the server maximum, always a margin below the
read timeout that applies to that call.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

import pytest

from zenture._mcp.wait import (
    DEFAULT_READ_TIMEOUT_SECONDS,
    SERVER_WAIT_MAX_SECONDS,
    WAIT_READ_MARGIN_SECONDS,
    server_wait_seconds,
)
from zenture.mcp import AsyncMcpClient, McpClient

RUN_ID = "run_waitseconds"
ARTIFACT = {"type": "text", "value": "selected answer"}


def _run(status: str = "completed") -> dict[str, object]:
    return {
        "run_id": RUN_ID,
        "generation": 1,
        "family": "knowledge",
        "work_type": "answer",
        "input_kind": "text",
        "profile": "standard",
        "status": status,
        "created_at": "2026-09-01T12:00:00Z",
        "updated_at": "2026-09-01T12:00:01Z",
        "artifact_refs": [],
    }


class TimedPort:
    """Records each call with the read timeout the transport was given (None: its own)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], float | None]] = []

    def list_tools(self) -> object:
        return {"tools": []}

    def _answer(self, name: str, arguments: Mapping[str, object], timeout: float | None) -> object:
        self.calls.append((name, dict(arguments), timeout))
        if name == "run":
            return {
                "structured_content": {
                    "run_id": RUN_ID,
                    "status": "queued",
                    "idempotency_key": arguments["idempotency_key"],
                }
            }
        if name == "list_runs":
            return {"structured_content": {"runs": [], "has_more": False}}
        return {"structured_content": _run()}

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, object],
        *,
        read_timeout_seconds: float | None = None,
    ) -> object:
        return _Result(self._answer(name, arguments, read_timeout_seconds))


class AsyncTimedPort(TimedPort):
    async def call_tool(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        name: str,
        arguments: Mapping[str, object],
        *,
        read_timeout_seconds: float | None = None,
    ) -> object:
        return _Result(self._answer(name, arguments, read_timeout_seconds))


class _Result:
    def __init__(self, answer: object) -> None:
        self.structured_content = cast("dict[str, object]", answer)["structured_content"]
        self.is_error = False


def _sync(port: TimedPort, **kwargs: Any) -> McpClient:
    return McpClient(cast("Any", port), **kwargs)


def _async(port: AsyncTimedPort, **kwargs: Any) -> AsyncMcpClient:
    return AsyncMcpClient(cast("Any", port), **kwargs)


@pytest.mark.parametrize(
    ("read_timeout", "expected"),
    [(DEFAULT_READ_TIMEOUT_SECONDS, 20), (60.0, 40), (300.0, SERVER_WAIT_MAX_SECONDS), (14.0, 4)],
)
def test_run_and_get_run_state_the_wait_the_read_timeout_allows(
    read_timeout: float, expected: int
) -> None:
    port = TimedPort()
    client = _sync(port, read_timeout=read_timeout)
    client.run(task="Check it.", artifact=ARTIFACT)
    client.get_run(RUN_ID)
    assert [call[1]["wait_seconds"] for call in port.calls] == [expected, expected]


def test_the_async_peer_states_the_same_wait() -> None:
    port = AsyncTimedPort()
    client = _async(port)
    asyncio.run(client.run(task="Check it.", artifact=ARTIFACT))
    asyncio.run(client.get_run(RUN_ID))
    assert [call[1]["wait_seconds"] for call in port.calls] == [20, 20]


def test_other_tools_carry_no_wait() -> None:
    port = TimedPort()
    client = _sync(port)
    client.list_runs()
    client.cancel_run(RUN_ID)
    assert all("wait_seconds" not in call[1] for call in port.calls)


@pytest.mark.parametrize("budget", [100.0, 30.0, 14.0, 5.0])
def test_a_bounded_wait_never_asks_the_server_to_outlive_the_per_call_read_timeout(
    budget: float,
) -> None:
    port = TimedPort()
    client = _sync(port)
    client.wait_run(RUN_ID, budget, stop_on=("queued", "running"))
    name, arguments, read_timeout = port.calls[0]
    assert name == "get_run"
    assert read_timeout is not None
    wait = cast("int", arguments["wait_seconds"])
    # the HTTP read timeout of the connection (30 s) bounds the call as well as the budget
    bound = min(read_timeout, DEFAULT_READ_TIMEOUT_SECONDS)
    assert 0 <= wait <= SERVER_WAIT_MAX_SECONDS
    assert wait == 0 or wait + WAIT_READ_MARGIN_SECONDS <= bound


def test_the_async_bounded_wait_states_the_same_wait() -> None:
    port = AsyncTimedPort()
    client = _async(port, read_timeout=100.0)
    asyncio.run(client.wait_run(RUN_ID, 100.0))
    assert port.calls[0][1]["wait_seconds"] == SERVER_WAIT_MAX_SECONDS


def test_a_long_budget_never_outruns_the_connection_read_timeout() -> None:
    port = AsyncTimedPort()
    asyncio.run(_async(port).wait_run(RUN_ID, 100.0))
    assert port.calls[0][1]["wait_seconds"] == 20


@pytest.mark.parametrize(
    "read_timeout", [0.5, 5.0, 9.99, 10.0, 10.5, 11.0, 25.0, 49.9, 50.0, 120.0, 300.0]
)
def test_the_derived_wait_is_capped_and_keeps_the_margin(read_timeout: float) -> None:
    wait = server_wait_seconds(read_timeout)
    assert isinstance(wait, int)
    assert 0 <= wait <= SERVER_WAIT_MAX_SECONDS
    assert wait == 0 or wait + WAIT_READ_MARGIN_SECONDS <= read_timeout
    # not needlessly short: one more second would break the cap or the margin
    assert wait == SERVER_WAIT_MAX_SECONDS or wait + 1 + WAIT_READ_MARGIN_SECONDS > read_timeout
