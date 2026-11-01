"""Standards resource wrappers: read, define and edit the caller's own standards."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from zenture._contract.standards import (
    STANDARD_ID_PATTERN,
    AgentStandard,
    AgentStandards,
    DefineStandardRequest,
    EditStandardRequest,
)
from zenture._resources._utils import idempotency_headers, parse_response, path_segment

if TYPE_CHECKING:
    from collections.abc import Sequence

    from zenture._transport import AsyncTransport, SyncTransport


def define_body(**fields: Any) -> dict[str, Any]:
    present = {key: value for key, value in fields.items() if value is not None}
    return DefineStandardRequest.model_validate(present).model_dump(mode="json", exclude_none=True)


def edit_body(**fields: Any) -> dict[str, Any]:
    present = {key: value for key, value in fields.items() if value is not None}
    return EditStandardRequest.model_validate(present).model_dump(mode="json", exclude_none=True)


def standard_path(standard_id: str) -> str:
    """Validate the id locally; the id only ever travels as the path of the route."""

    if re.fullmatch(STANDARD_ID_PATTERN, standard_id) is None:
        raise ValueError("standard_id must be a standard identifier copied from get_standards")
    return f"/standards/{path_segment(standard_id)}"


class StandardsResource:
    """Synchronous wrapper for the standards routes."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def get(self) -> AgentStandards:
        return parse_response(AgentStandards, self._transport.request_json("GET", "/standards"))

    def define(
        self,
        *,
        text: str,
        strength: str,
        idempotency_key: str,
        criterion: str | None = None,
        task_types: Sequence[str] | None = None,
        owner: str = "user",
    ) -> AgentStandard:
        body = define_body(
            text=text,
            strength=strength,
            criterion=criterion,
            task_types=None if task_types is None else list(task_types),
            owner=owner,
        )
        payload = self._transport.request_json(
            "POST", "/standards", headers=idempotency_headers(idempotency_key), json=body
        )
        return parse_response(AgentStandard, payload)

    def edit(
        self,
        standard_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
        text: str | None = None,
        strength: str | None = None,
        task_types: Sequence[str] | None = None,
        active: bool | None = None,
        restore_version: int | None = None,
    ) -> AgentStandard:
        path = standard_path(standard_id)
        body = edit_body(
            expected_version=expected_version,
            text=text,
            strength=strength,
            task_types=None if task_types is None else list(task_types),
            active=active,
            restore_version=restore_version,
        )
        payload = self._transport.request_json(
            "PATCH", path, headers=idempotency_headers(idempotency_key), json=body
        )
        return parse_response(AgentStandard, payload)


class AsyncStandardsResource:
    """Asynchronous wrapper for the standards routes."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def get(self) -> AgentStandards:
        return parse_response(
            AgentStandards, await self._transport.request_json("GET", "/standards")
        )

    async def define(
        self,
        *,
        text: str,
        strength: str,
        idempotency_key: str,
        criterion: str | None = None,
        task_types: Sequence[str] | None = None,
        owner: str = "user",
    ) -> AgentStandard:
        body = define_body(
            text=text,
            strength=strength,
            criterion=criterion,
            task_types=None if task_types is None else list(task_types),
            owner=owner,
        )
        payload = await self._transport.request_json(
            "POST", "/standards", headers=idempotency_headers(idempotency_key), json=body
        )
        return parse_response(AgentStandard, payload)

    async def edit(
        self,
        standard_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
        text: str | None = None,
        strength: str | None = None,
        task_types: Sequence[str] | None = None,
        active: bool | None = None,
        restore_version: int | None = None,
    ) -> AgentStandard:
        path = standard_path(standard_id)
        body = edit_body(
            expected_version=expected_version,
            text=text,
            strength=strength,
            task_types=None if task_types is None else list(task_types),
            active=active,
            restore_version=restore_version,
        )
        payload = await self._transport.request_json(
            "PATCH", path, headers=idempotency_headers(idempotency_key), json=body
        )
        return parse_response(AgentStandard, payload)
