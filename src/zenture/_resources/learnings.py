"""Learning read resource wrappers: the caller's own current Essenz."""

from __future__ import annotations

from typing import TYPE_CHECKING

from zenture._resources._utils import parse_response
from zenture.types import Learnings

if TYPE_CHECKING:
    from zenture._transport import AsyncTransport, SyncTransport


class LearningsResource:
    """Synchronous wrapper for the learnings read route."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def get(self) -> Learnings:
        """Fetch the Essenz of the token's own account."""

        return parse_response(Learnings, self._transport.request_json("GET", "/learnings"))


class AsyncLearningsResource:
    """Asynchronous wrapper for the learnings read route."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def get(self) -> Learnings:
        """Fetch the Essenz of the token's own account."""

        return parse_response(Learnings, await self._transport.request_json("GET", "/learnings"))
