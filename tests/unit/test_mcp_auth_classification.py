"""Authorization failures keep their classification through the MCP peers."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

import pytest

from zenture._auth.errors import AuthorizationRequired, PermissionDenied
from zenture.errors import ZentureMCPError
from zenture.mcp import AsyncMcpClient, McpClient

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

RUN_ID = "run_authclass"


class CountingPort:
    """Sync transport that raises the given failure on every call."""

    def __init__(self, failure: BaseException) -> None:
        self.failure = failure
        self.calls = 0

    def list_tools(self) -> object:
        self.calls += 1
        raise self.failure

    def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        del name, arguments
        self.calls += 1
        raise self.failure


class AsyncCountingPort(CountingPort):
    async def list_tools(self) -> object:
        return super().list_tools()

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> object:
        return super().call_tool(name, arguments)


def _group(failure: BaseException) -> BaseExceptionGroup[Any]:
    return BaseExceptionGroup("task group", [failure])


FAILURES: list[Callable[[], BaseException]] = [
    lambda: AuthorizationRequired("refresh_rejected"),
    lambda: PermissionDenied("permission_denied"),
    lambda: _group(AuthorizationRequired("unauthorized_after_refresh")),
    lambda: _group(_group(PermissionDenied("permission_denied"))),
]


@pytest.mark.parametrize("make_failure", FAILURES)
def test_sync_wait_run_surfaces_auth_failure_without_retry(
    make_failure: Callable[[], BaseException],
) -> None:
    port = CountingPort(make_failure())
    with pytest.raises((AuthorizationRequired, PermissionDenied)) as caught:
        McpClient(port).wait_run(RUN_ID, 5)
    assert isinstance(caught.value, (AuthorizationRequired, PermissionDenied))
    assert port.calls == 1


@pytest.mark.parametrize("make_failure", FAILURES)
def test_async_wait_run_surfaces_auth_failure_without_retry(
    make_failure: Callable[[], BaseException],
) -> None:
    port = AsyncCountingPort(make_failure())
    with pytest.raises((AuthorizationRequired, PermissionDenied)) as caught:
        asyncio.run(AsyncMcpClient(cast("Any", port)).wait_run(RUN_ID, 5))
    assert isinstance(caught.value, (AuthorizationRequired, PermissionDenied))
    assert port.calls == 1


@pytest.mark.parametrize("make_failure", FAILURES)
def test_sync_run_and_get_run_keep_auth_classification(
    make_failure: Callable[[], BaseException],
) -> None:
    port = CountingPort(make_failure())
    with pytest.raises((AuthorizationRequired, PermissionDenied)):
        McpClient(port).get_run(RUN_ID)
    assert port.calls == 1


@pytest.mark.parametrize("make_failure", FAILURES)
def test_sync_discovery_keeps_auth_classification(
    make_failure: Callable[[], BaseException],
) -> None:
    client = McpClient(CountingPort(make_failure()))
    with pytest.raises((AuthorizationRequired, PermissionDenied)):
        client.get_tool_catalog()
    with pytest.raises((AuthorizationRequired, PermissionDenied)):
        client.list_tools()


@pytest.mark.parametrize("make_failure", FAILURES)
def test_async_discovery_keeps_auth_classification(
    make_failure: Callable[[], BaseException],
) -> None:
    client = AsyncMcpClient(cast("Any", AsyncCountingPort(make_failure())))

    async def exercise() -> None:
        with pytest.raises((AuthorizationRequired, PermissionDenied)):
            await client.get_tool_catalog()
        with pytest.raises((AuthorizationRequired, PermissionDenied)):
            await client.list_tools()

    asyncio.run(exercise())


def test_unknown_transport_failure_is_still_wrapped_as_retryable_unavailable() -> None:
    port = CountingPort(RuntimeError("socket reset"))
    with pytest.raises(ZentureMCPError, match="mcp_transport_unavailable") as caught:
        McpClient(port).get_run(RUN_ID)
    assert caught.value.retryable is True
    assert port.calls == 1
