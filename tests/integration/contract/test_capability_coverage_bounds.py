"""The SDK reads a full view whose coverage lists the Backend's 256 status refs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

OPENAPI_PATH = (
    Path(__file__).resolve().parents[3] / "openapi" / "zenture-public-api-v1.openapi.json"
)
BACKEND_STATUS_REF_LIMIT = 256
BACKEND_LIMITATION_REF_LIMIT = 32


def _coverage_properties() -> dict[str, Any]:
    contract = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    schema = contract["components"]["schemas"]["PublicCapabilityCoverage"]
    return cast("dict[str, Any]", schema["properties"])


def test_coverage_accepts_one_status_ref_per_checked_subject_up_to_the_backend_bound() -> None:
    from zenture._contract import PublicCapabilityCoverage

    refs = [f"coverage:{index}" for index in range(BACKEND_STATUS_REF_LIMIT)]
    coverage = PublicCapabilityCoverage.model_validate(
        {"available_refs": refs, "unavailable_refs": refs}
    )

    assert len(coverage.unavailable_refs) == BACKEND_STATUS_REF_LIMIT
    assert len(coverage.available_refs) == BACKEND_STATUS_REF_LIMIT


def test_coverage_still_rejects_lists_beyond_the_backend_bounds() -> None:
    from zenture._contract import PublicCapabilityCoverage

    with pytest.raises(ValidationError):
        PublicCapabilityCoverage.model_validate(
            {"unavailable_refs": ["x"] * (BACKEND_STATUS_REF_LIMIT + 1)}
        )
    with pytest.raises(ValidationError):
        PublicCapabilityCoverage.model_validate(
            {"limitation_refs": ["x"] * (BACKEND_LIMITATION_REF_LIMIT + 1)}
        )


def test_openapi_copy_states_the_backend_bounds() -> None:
    properties = _coverage_properties()

    assert properties["available_refs"]["maxItems"] == BACKEND_STATUS_REF_LIMIT
    assert properties["unavailable_refs"]["maxItems"] == BACKEND_STATUS_REF_LIMIT
    assert properties["limitation_refs"]["maxItems"] == BACKEND_LIMITATION_REF_LIMIT
