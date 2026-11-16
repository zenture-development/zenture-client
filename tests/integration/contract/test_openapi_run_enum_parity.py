"""The client's Run read models equal the bundled public OpenAPI: field names, required fields and enums."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast, get_args

import pytest

from zenture._contract.models import PublicRunEvent
from zenture._contract.run_read import (
    PublicDecision,
    PublicRunBilling,
    PublicRunCriterion,
    PublicRunEvidence,
    PublicRunFinding,
    PublicRunLearning,
    PublicRunResponse,
    PublicRunStandard,
    PublicRunStatement,
    RunStatus,
)
from zenture._resources._run_wait import (
    _TERMINAL_STREAM_STATUSES,  # pyright: ignore[reportPrivateUsage] -- enum parity contract
)
from zenture._resources.runs import (
    _TERMINAL_STATUSES,  # pyright: ignore[reportPrivateUsage] -- enum parity contract
)

OPENAPI_PATH = (
    Path(__file__).resolve().parents[3] / "openapi" / "zenture-public-api-v1.openapi.json"
)
RUN_READ_MODELS: dict[str, Any] = {
    "PublicRunResponse": PublicRunResponse,
    "PublicRunFinding": PublicRunFinding,
    "PublicRunEvidence": PublicRunEvidence,
    "PublicRunBilling": PublicRunBilling,
    "PublicRunStandard": PublicRunStandard,
    "PublicRunLearning": PublicRunLearning,
    "PublicRunCriterion": PublicRunCriterion,
    "PublicRunStatement": PublicRunStatement,
}


def _schemas() -> dict[str, Any]:
    data = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    return cast("dict[str, Any]", data["components"]["schemas"])


def _schema_enums(node: Any) -> set[Any]:
    """All closed values (enum) of one schema property, nulls left out."""

    found: set[Any] = set()
    if isinstance(node, dict):
        mapping = cast("dict[str, Any]", node)
        found |= {value for value in mapping.get("enum", []) if value is not None}
        for value in mapping.values():
            found |= _schema_enums(value)
    elif isinstance(node, list):
        for item in cast("list[Any]", node):
            found |= _schema_enums(item)
    return found


def _model_enums(annotation: Any) -> set[Any]:
    """All closed values of one model field: Literal values and StrEnum members."""

    if hasattr(annotation, "__members__"):
        return {member.value for member in annotation}
    values: set[Any] = set()
    for option in get_args(annotation):
        if option is type(None):
            continue
        if hasattr(option, "__members__"):
            values |= {member.value for member in option}
        elif isinstance(option, (str, bool)):
            values.add(option)
        else:
            values |= _model_enums(option)
    return values


@pytest.mark.parametrize("name", sorted(RUN_READ_MODELS))
def test_run_read_model_fields_and_required_equal_the_openapi_schema(name: str) -> None:
    schema = _schemas()[name]
    model = RUN_READ_MODELS[name]
    assert set(model.model_fields) == set(schema["properties"])
    required = {field for field, info in model.model_fields.items() if info.is_required()}
    assert required == set(schema.get("required", []))


@pytest.mark.parametrize("name", sorted(RUN_READ_MODELS))
def test_run_read_model_enums_equal_the_openapi_schema(name: str) -> None:
    schemas = _schemas()
    schema = schemas[name]
    for field, info in RUN_READ_MODELS[name].model_fields.items():
        property_schema = schema["properties"][field]
        ref = property_schema.get("$ref") or next(
            (o["$ref"] for o in property_schema.get("anyOf", []) if "$ref" in o), None
        )
        if ref is not None:  # a named enum is compared as such; a named model has its own test
            target = schemas[ref.rsplit("/", 1)[1]]
            property_schema = target if "enum" in target else {}
        assert _model_enums(info.annotation) == _schema_enums(property_schema), f"{name}.{field}"


def test_run_status_enum_equals_the_public_run_status() -> None:
    expected = set(_schemas()["RunStatus"]["enum"])
    assert {status.value for status in RunStatus} == expected
    assert {status.value for status in _TERMINAL_STATUSES} <= expected


def test_decision_enum_equals_the_public_decision() -> None:
    assert {d.value for d in PublicDecision} == set(_schemas()["PublicDecision"]["enum"])


def test_stream_event_statuses_equal_the_public_event_status_enum() -> None:
    expected = set(_schemas()["PublicRunEvent"]["properties"]["status"]["enum"])
    assert set(get_args(PublicRunEvent.model_fields["status"].annotation)) == expected
    assert expected >= _TERMINAL_STREAM_STATUSES
