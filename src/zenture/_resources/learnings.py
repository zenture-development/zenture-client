"""Learning read resource wrappers: the caller's own current Essenz."""

from __future__ import annotations

from typing import TYPE_CHECKING

from zenture._contract.learnings import LearningVisibilityRequest
from zenture._resources._utils import idempotency_headers, parse_response
from zenture.types import Learnings, LearningVisibility

if TYPE_CHECKING:
    from zenture._transport import AsyncTransport, SyncTransport


class LearningsResource:
    """Synchronous wrapper for the learnings read route."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def get(self) -> Learnings:
        """Fetch the Essenz of the token's own account."""

        return parse_response(Learnings, self._transport.request_json("GET", "/learnings"))

    def set_hidden(self, code: str, hidden: bool, *, idempotency_key: str) -> LearningVisibility:
        """Hide or show one learning of the token's own account."""

        payload = self._transport.request_json(
            "PUT",
            "/learnings/visibility",
            headers=idempotency_headers(idempotency_key),
            json=hide_body(code, hidden),
        )
        return parse_response(LearningVisibility, payload)


class AsyncLearningsResource:
    """Asynchronous wrapper for the learnings read route."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def get(self) -> Learnings:
        """Fetch the Essenz of the token's own account."""

        return parse_response(Learnings, await self._transport.request_json("GET", "/learnings"))

    async def set_hidden(
        self, code: str, hidden: bool, *, idempotency_key: str
    ) -> LearningVisibility:
        """Hide or show one learning of the token's own account."""

        payload = await self._transport.request_json(
            "PUT",
            "/learnings/visibility",
            headers=idempotency_headers(idempotency_key),
            json=hide_body(code, hidden),
        )
        return parse_response(LearningVisibility, payload)


def hide_body(code: str, hidden: bool) -> dict[str, object]:
    """Validate the closed code locally; the owner is always the token's account."""

    return LearningVisibilityRequest.model_validate({"code": code, "hidden": hidden}).model_dump(
        mode="json"
    )
