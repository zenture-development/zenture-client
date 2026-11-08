"""A Run on an uploaded file returns file-sourced locations; the client must parse them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError
from test_safe_result_content_contract import _golden_payload

from zenture import ZentureClient
from zenture._contract.models import (
    ArtifactUploadAccepted,
    SafeResultContentAvailableV1,
    SignedUploadResponse,
)
from zenture._contract.safe_result_findings import SafeResultLocation
from zenture.errors import ZentureResponseError
from zenture.models import ForwardCompatibleErrorEnvelope

API_KEY = f"zt_live_{UUID(int=0).hex}"
MIRROR = Path(__file__).resolve().parents[2] / "openapi/zenture-public-api-v1.openapi.json"


def _payload(location: dict[str, object]) -> dict[str, Any]:
    payload = _golden_payload()
    content = cast(
        "dict[str, Any]", cast("dict[str, Any]", payload["safe_result_content"])["content"]
    )
    content["findings"][0]["locations"] = [location]
    return payload


def _get_run(payload: dict[str, Any]) -> Any:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = ZentureClient(
        api_key=API_KEY, http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    run = client.runs.get(payload["run_id"], view="full")
    client.close()
    return run


def _first_location(run: Any) -> Any:
    content = run.safe_result_content
    assert isinstance(content, SafeResultContentAvailableV1)
    return content.content.findings[0].locations[0]


@pytest.mark.parametrize(
    "extra",
    [
        {"page": 3},
        {"sheet": "Totals", "cell": "B12"},
        {"page": 2, "from_image": True},
        {},
    ],
)
def test_get_run_parses_a_file_sourced_location(extra: dict[str, object]) -> None:
    location = {
        "source": "file",
        "start": 10,
        "end": 25,
        "excerpt": "total 1,190 EUR",
        "status": "shown",
        **extra,
    }

    parsed = _first_location(_get_run(_payload(location)))

    assert parsed.source == "file"
    assert (parsed.start, parsed.end) == (10, 25)
    assert parsed.page == extra.get("page")
    assert parsed.sheet == extra.get("sheet")
    assert parsed.cell == extra.get("cell")
    assert parsed.from_image is extra.get("from_image")


def test_answer_location_still_parses_without_file_fields() -> None:
    parsed = _first_location(_get_run(_golden_payload()))

    assert parsed.source == "answer"
    assert (parsed.page, parsed.sheet, parsed.cell, parsed.from_image) == (None, None, None, None)


@pytest.mark.parametrize(
    "bad",
    [
        {"page": 0},
        {"page": 100001},
        {"cell": "b12"},
        {"cell": "A0"},
        {"cell": "AAAA1"},
        {"sheet": ""},
        {"sheet": "x" * 129},
        {"from_image": "yes"},
        {"source": "attachment"},
    ],
)
def test_file_location_fields_keep_the_gateway_constraints(bad: dict[str, object]) -> None:
    location = {"source": "file", "start": 1, "end": 5, "excerpt": "text", "status": "shown"}
    with pytest.raises(ZentureResponseError):
        _get_run(_payload({**location, **bad}))


def test_error_retry_after_seconds_follows_the_mirror_bounds() -> None:
    declared = json.loads(MIRROR.read_text())["components"]["schemas"]["PublicRunError"][
        "properties"
    ]["retry_after_seconds"]
    bounds = (declared["minimum"], declared["maximum"])
    assert bounds == (1, 3600)
    for value, valid in ((bounds[0], True), (bounds[1], True), (0, False), (3601, False)):
        payload = {"error": {"code": "artifact_not_ready", "message": "m"}, "request_id": "r"}
        cast("dict[str, Any]", payload["error"])["retry_after_seconds"] = value
        error = ForwardCompatibleErrorEnvelope
        if valid:
            assert error.model_validate(payload).error.retry_after_seconds == value
        else:
            with pytest.raises(ValidationError):
                error.model_validate(payload)


def test_sdk_models_are_pinned_to_the_mirror_for_the_upload_and_location_schemas() -> None:
    schemas = json.loads(MIRROR.read_text())["components"]["schemas"]
    pairs = {
        "SafeResultLocation": SafeResultLocation,
        "PublicSignedUploadResponse": SignedUploadResponse,
        "PublicUploadAcceptedResponse": ArtifactUploadAccepted,
    }
    for name, model in pairs.items():
        mirror = schemas[name]
        assert set(model.model_fields) == set(mirror["properties"]), name
        required = {n for n, f in model.model_fields.items() if f.is_required()}
        assert required == set(mirror["required"]), name

    cell = schemas["SafeResultLocation"]["properties"]["cell"]["pattern"]
    assert cell == r"^[A-Z]{1,3}[1-9][0-9]{0,6}$"
    assert schemas["SafeResultLocation"]["properties"]["source"]["enum"] == [
        "answer",
        "task",
        "file",
    ]


def test_file_location_text_is_documented_as_untrusted_in_the_model_and_the_openapi_mirror() -> None:
    """M1: excerpt and sheet quote the user's file; the SDK documents them as never to be followed as instructions."""
    spec = json.loads(
        (Path(__file__).resolve().parents[2] / "openapi" / "zenture-public-api-v1.openapi.json").read_text("utf-8")
    )
    mirrored = spec["components"]["schemas"]["SafeResultLocation"]["properties"]
    for member in ("excerpt", "sheet"):
        for description in (mirrored[member].get("description"), SafeResultLocation.model_fields[member].description):
            text = (description or "").lower()
            assert "verbatim" in text and "untrusted" in text and "never" in text and "instruction" in text
