"""Standards over the hosted MCP tools: the same closed models and bodies as REST, without a caller key."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, ValidationError

from zenture._contract.standards import (
    AgentStandard,
    AgentStandards,
    DefineStandardRequest,
    EditStandardRequest,
)
from zenture._resources.standards import standard_path
from zenture.errors import ZentureMCPProtocolError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def _parse(model: type[Any], payload: Mapping[str, object]) -> Any:
    # Raised outside the handler so the Pydantic error (which echoes submitted values) is not chained.
    try:
        return cast("BaseModel", model.model_validate(payload))
    except ValidationError:
        contract_error = ZentureMCPProtocolError("invalid_result_contract")
    raise contract_error


def define_arguments(
    *, text: str, strength: str, criterion: str | None, task_types: Sequence[str] | None, owner: str
) -> dict[str, object]:
    fields = {"text": text, "strength": strength, "criterion": criterion, "owner": owner}
    present: dict[str, object] = {key: value for key, value in fields.items() if value is not None}
    if task_types is not None:
        present["task_types"] = list(task_types)
    request = DefineStandardRequest.model_validate(present)
    return cast("dict[str, object]", request.model_dump(mode="json", exclude_none=True))


def edit_arguments(
    standard_id: str,
    *,
    expected_version: int,
    text: str | None,
    criterion: str | None = None,
    strength: str | None,
    task_types: Sequence[str] | None,
    active: bool | None,
    restore_version: int | None,
    use_suggested_criterion: bool | None = None,
) -> dict[str, object]:
    standard_path(standard_id)
    fields = {
        "expected_version": expected_version,
        "text": text,
        "criterion": criterion,
        "strength": strength,
        "task_types": None if task_types is None else list(task_types),
        "active": active,
        "restore_version": restore_version,
        "use_suggested_criterion": use_suggested_criterion,
    }
    request = EditStandardRequest.model_validate({k: v for k, v in fields.items() if v is not None})
    body = request.model_dump(mode="json", exclude_none=True)
    return {"standard_id": standard_id, **body}


class StandardsMcpMixin:
    """`get_standards`, `define_standard` and `edit_standard`; the account is the OAuth session's."""

    if TYPE_CHECKING:

        def _call(self, name: str, arguments: Mapping[str, object]) -> dict[str, object]: ...

    def get_standards(self) -> AgentStandards:
        """Read your standards through the hosted `get_standards` tool (scope `mcp:run`). No arguments."""

        return cast("AgentStandards", _parse(AgentStandards, self._call("get_standards", {})))

    def define_standard(
        self,
        *,
        text: str,
        strength: str,
        criterion: str | None = None,
        task_types: Sequence[str] | None = None,
        owner: str = "user",
    ) -> AgentStandard:
        """Define one standard; `owner="org"` needs an organisation connection and owner rights."""

        arguments = define_arguments(
            text=text, strength=strength, criterion=criterion, task_types=task_types, owner=owner
        )
        return cast(
            "AgentStandard", _parse(AgentStandard, self._call("define_standard", arguments))
        )

    def edit_standard(
        self,
        standard_id: str,
        *,
        expected_version: int,
        text: str | None = None,
        criterion: str | None = None,
        strength: str | None = None,
        task_types: Sequence[str] | None = None,
        active: bool | None = None,
        restore_version: int | None = None,
        use_suggested_criterion: bool | None = None,
    ) -> AgentStandard:
        """Change one standard against the version you read: field edits, `restore_version` or `use_suggested_criterion`."""

        arguments = edit_arguments(
            standard_id,
            expected_version=expected_version,
            text=text,
            criterion=criterion,
            strength=strength,
            task_types=task_types,
            active=active,
            restore_version=restore_version,
            use_suggested_criterion=use_suggested_criterion,
        )
        return cast("AgentStandard", _parse(AgentStandard, self._call("edit_standard", arguments)))


class AsyncStandardsMcpMixin:
    """Async variant of `StandardsMcpMixin`."""

    if TYPE_CHECKING:

        async def _call(self, name: str, arguments: Mapping[str, object]) -> dict[str, object]: ...

    async def get_standards(self) -> AgentStandards:
        """Read your standards through the hosted `get_standards` tool (async)."""

        return cast("AgentStandards", _parse(AgentStandards, await self._call("get_standards", {})))

    async def define_standard(
        self,
        *,
        text: str,
        strength: str,
        criterion: str | None = None,
        task_types: Sequence[str] | None = None,
        owner: str = "user",
    ) -> AgentStandard:
        """Define one standard (async); `owner="org"` needs an organisation connection and owner rights."""

        arguments = define_arguments(
            text=text, strength=strength, criterion=criterion, task_types=task_types, owner=owner
        )
        return cast(
            "AgentStandard", _parse(AgentStandard, await self._call("define_standard", arguments))
        )

    async def edit_standard(
        self,
        standard_id: str,
        *,
        expected_version: int,
        text: str | None = None,
        criterion: str | None = None,
        strength: str | None = None,
        task_types: Sequence[str] | None = None,
        active: bool | None = None,
        restore_version: int | None = None,
        use_suggested_criterion: bool | None = None,
    ) -> AgentStandard:
        """Change one standard (async) against the version you read: field edits, `restore_version` or `use_suggested_criterion`."""

        arguments = edit_arguments(
            standard_id,
            expected_version=expected_version,
            text=text,
            criterion=criterion,
            strength=strength,
            task_types=task_types,
            active=active,
            restore_version=restore_version,
            use_suggested_criterion=use_suggested_criterion,
        )
        return cast(
            "AgentStandard", _parse(AgentStandard, await self._call("edit_standard", arguments))
        )
