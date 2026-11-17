"""The lean Run read: verdict, findings with evidence, billing, standards; strict bounds; REST read."""

from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from zenture import ZentureClient
from zenture._contract import PublicRunResponse

RUN_ID = "run_33333333333343338333333333333333"
STANDARD_ID = "11111111-1111-4111-8111-111111111111"


def _terminal() -> dict[str, object]:
    return {
        "run_id": RUN_ID,
        "status": "completed",
        "acceptance_decision": "revise",
        "reason": "figure_unsupported",
        "next_action": "revise_answer",
        "hint": "Source the revenue figure or remove it.",
        "findings": [
            {
                "ref": "finding:f1",
                "proven": True,
                "category": "unsupported",
                "location": "paragraph 2",
                "problem": "The figure 4.2 million has no source.",
                "evidence": {"url": "https://example.org/report", "excerpt": "revenue was 3.1 million"},
                "fix": "State 3.1 million or cite a source.",
            },
            {
                "ref": "finding:f2",
                "proven": False,
                "problem": "The file claim could not be confirmed.",
                "evidence": {"excerpt": "Total: 12", "untrusted_file_text": True},
            },
        ],
        "billing": {"status": "pending"},
        "standards": [{"standard_id": STANDARD_ID, "result": "violated"}],
        "learning": {"essence": "Name your sources."},
    }


def test_a_terminal_run_exposes_the_lean_verdict_fields() -> None:
    run = PublicRunResponse.model_validate(_terminal())

    assert run.acceptance_decision is not None
    assert run.acceptance_decision.value == "revise"
    assert (run.reason, run.next_action, run.hint) == (
        "figure_unsupported",
        "revise_answer",
        "Source the revenue figure or remove it.",
    )
    assert run.findings is not None
    web, file = run.findings
    assert (web.category, web.proven, web.fix) == ("unsupported", True, "State 3.1 million or cite a source.")
    assert web.evidence is not None
    assert web.evidence.url == "https://example.org/report"
    assert file.evidence is not None
    assert file.evidence.untrusted_file_text is True
    assert file.evidence.url is None
    assert run.billing is not None
    assert (run.billing.status, run.billing.amount) == ("pending", None)
    assert run.billing.unit == "credits"
    assert run.standards is not None
    assert run.standards[0].result == "violated"
    assert run.learning is not None
    assert run.learning.essence == "Name your sources."


def test_a_non_terminal_run_carries_only_status_next_action_hint_and_eta() -> None:
    run = PublicRunResponse.model_validate(
        {"run_id": RUN_ID, "status": "running", "next_action": "get_run", "hint": "Read again.", "eta_seconds": 40}
    )

    assert run.acceptance_decision is None
    assert run.findings is None
    assert run.billing is None
    assert (run.next_action, run.eta_seconds) == ("get_run", 40)


def test_the_full_view_adds_criteria_and_statements() -> None:
    run = PublicRunResponse.model_validate(
        {
            **_terminal(),
            "criteria": [{"ref": "c1", "status": "not_satisfied", "reason": "missing", "hard_gate": True}],
            "statements": [
                {"ref": "s1", "assessment": "unsupported", "reason": "no_source", "cited": False, "start": 0, "end": 9}
            ],
        }
    )

    assert run.criteria is not None
    assert run.criteria[0].hard_gate is True
    assert run.statements is not None
    assert (run.statements[0].start, run.statements[0].end) == (0, 9)


def test_a_revision_run_exposes_what_changed_about_its_predecessor_findings() -> None:
    run = PublicRunResponse.model_validate(
        {
            **_terminal(),
            "changes": {
                "resolved": [{"category": "calculation", "location": "table 1"}],
                "open": ["finding:f1"],
                "new": [],
            },
        }
    )

    assert run.changes is not None
    assert [(r.category, r.location) for r in run.changes.resolved] == [("calculation", "table 1")]
    assert (run.changes.open, run.changes.new) == (("finding:f1",), ())
    assert PublicRunResponse.model_validate(_terminal()).changes is None


@pytest.mark.parametrize(
    "patch",
    [
        {"acceptance_decision": "approved"},
        {"changes": {"resolved": [], "open": ["not-a-finding-ref" * 20], "new": []}},
        {"changes": {"resolved": [{"category": "task_requirement"}], "open": [], "new": []}},
        {"findings": [{"ref": "finding:f1", "proven": True, "problem": "x", "category": "other"}]},
        {"findings": [{"ref": "finding:f1", "proven": True, "problem": "x", "evidence": {"untrusted_file_text": False}}]},
        {"billing": {"status": "settled", "amount": "1,5"}},
        {"standards": [{"standard_id": STANDARD_ID, "result": "n/a"}]},
        {"status": "unknown"},
    ],
)
def test_values_outside_the_published_contract_are_rejected(patch: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PublicRunResponse.model_validate({**_terminal(), **patch})


def test_rest_get_returns_the_lean_run_read() -> None:
    client = ZentureClient(
        api_key="zt_" + "live_" + "client_123",
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=_terminal()))
        ),
        max_retries=0,
    )

    run = client.runs.get(RUN_ID, view="full")

    assert run.reason == "figure_unsupported"
    assert run.findings is not None
    assert run.findings[0].ref == "finding:f1"
