"""Run status, stream, finding-category and billing enums equal the bundled public OpenAPI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast, get_args

from zenture._contract.models import (
    PublicRunEvent,
    RunStatus,
    TerminalBillingSummaryV1,
)
from zenture._contract.safe_result_findings import (
    SafeResultFinding,
    SafeResultFindingCategory,
)
from zenture._resources._run_wait import _TERMINAL_STREAM_STATUSES
from zenture._resources.runs import _TERMINAL_STATUSES

OPENAPI_PATH = (
    Path(__file__).resolve().parents[3] / "openapi" / "zenture-public-api-v1.openapi.json"
)


def _schemas() -> dict[str, Any]:
    data = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    return cast("dict[str, Any]", data["components"]["schemas"])


def _literal(model: Any, field: str) -> set[str]:
    return set(get_args(model.model_fields[field].annotation))


def test_run_status_enum_equals_the_public_run_response_status() -> None:
    schemas = _schemas()
    expected = set(schemas["PublicRunResponse"]["properties"]["status"]["enum"])
    assert {status.value for status in RunStatus} == expected
    assert {status.value for status in _TERMINAL_STATUSES} <= expected


def test_stream_event_statuses_equal_the_public_event_status_enum() -> None:
    expected = set(_schemas()["PublicRunEvent"]["properties"]["status"]["enum"])
    assert _literal(PublicRunEvent, "status") == expected
    assert expected >= _TERMINAL_STREAM_STATUSES


def test_finding_category_enum_equals_the_public_finding_category() -> None:
    expected = set(_schemas()["SafeResultFinding"]["properties"]["category"]["enum"])
    assert set(get_args(SafeResultFindingCategory)) == expected
    assert set(SafeResultFinding.model_fields) >= set(_schemas()["SafeResultFinding"]["properties"])


def test_billing_status_enum_equals_the_terminal_billing_summary_status() -> None:
    expected = set(_schemas()["TerminalBillingSummaryV1"]["properties"]["status"]["enum"])
    assert _literal(TerminalBillingSummaryV1, "status") == expected
