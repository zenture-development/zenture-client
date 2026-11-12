"""The optional learning fields of a Run read: parsed leniently, bounded, over REST and MCP labels."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from zenture import ZentureClient
from zenture._contract import PublicRunResponse

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

API_KEY = "zt_" + "live_" + "client_123"
FIXTURE = Path(__file__).parent / "fixtures" / "safe-result-content.full-verdict.valid.json"
RUN_ID = "run_33333333333343338333333333333333"


def _rest(handler: Callable[[httpx.Request], httpx.Response]) -> ZentureClient:
    return ZentureClient(
        api_key=API_KEY,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )


def _run(**extra: object) -> dict[str, object]:
    return {
        "run_id": RUN_ID,
        "generation": 1,
        "family": "knowledge",
        "work_type": "answer",
        "profile": "standard",
        "status": "completed",
        "created_at": "2026-10-30T12:00:00Z",
        "updated_at": "2026-10-30T12:00:01Z",
        **extra,
    }


def _content(finding_extra: Mapping[str, object]) -> dict[str, Any]:
    content: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    content["content"]["findings"][0].update(finding_extra)
    return content


def test_old_run_payloads_parse_with_the_learning_fields_absent() -> None:
    run = PublicRunResponse.model_validate(_run())

    assert run.learning_applied is None
    assert run.essence_version is None
    assert run.essence is None


def test_run_learning_fields_parse_and_stay_bounded() -> None:
    run = PublicRunResponse.model_validate(
        _run(learning_applied=True, essence_version="v7", essence="Name your sources.")
    )

    assert run.learning_applied is True
    assert run.essence_version == "v7"
    assert run.essence == "Name your sources."
    with pytest.raises(ValueError, match="essence_version"):
        PublicRunResponse.model_validate(_run(essence_version="v" * 65))
    with pytest.raises(ValueError, match="essence"):
        PublicRunResponse.model_validate(_run(essence="x" * 601))


@pytest.mark.parametrize("marker", [True, "Fokus aus deiner Essenz"])
def test_finding_essence_focus_parses_from_rest_flag_and_mcp_label(marker: object) -> None:
    run = PublicRunResponse.model_validate(
        _run(
            safe_result_content=_content({"essence_focus": marker}),
        )
    )
    unmarked = PublicRunResponse.model_validate(_run(safe_result_content=_content({})))

    assert run.safe_result_content is not None
    assert run.safe_result_content.status == "available"
    assert run.safe_result_content.content.findings[0].essence_focus is True
    assert unmarked.safe_result_content is not None
    assert unmarked.safe_result_content.status == "available"
    assert unmarked.safe_result_content.content.findings[0].essence_focus is False


def test_finding_essence_focus_null_means_not_focused() -> None:
    run = PublicRunResponse.model_validate(
        _run(safe_result_content=_content({"essence_focus": None}))
    )

    assert run.safe_result_content is not None
    assert run.safe_result_content.status == "available"
    assert run.safe_result_content.content.findings[0].essence_focus is False


def test_finding_essence_focus_rejects_other_values() -> None:
    with pytest.raises(ValueError, match="essence_focus"):
        PublicRunResponse.model_validate(
            _run(safe_result_content=_content({"essence_focus": "yes"}))
        )


def test_rest_run_read_exposes_learning_fields() -> None:
    payload = _run(learning_applied=True, essence_version="v7")
    client = _rest(lambda _request: httpx.Response(200, json=payload))

    run = client.runs.get(RUN_ID)

    assert run.learning_applied is True
    assert run.essence_version == "v7"
