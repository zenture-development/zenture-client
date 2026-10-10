"""The end-to-end example reports a billed total only when every component is known."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "end_to_end_chat_evaluation.py"


def example() -> Any:
    spec = importlib.util.spec_from_file_location("end_to_end_chat_evaluation", EXAMPLE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def billed(amount: str) -> SimpleNamespace:
    return SimpleNamespace(amount=amount, unit="credits")


def test_unknown_component_is_not_counted_as_zero() -> None:
    module = example()
    chat = module._amount(None)
    assert chat is None

    total = module._total_billed({"chat": chat, "evaluation": module._amount(billed("1.50"))})

    assert total["amount"] is None
    assert total["status"] == "partial"
    assert total["includes"] == ["chat", "evaluation"]
    assert total["unknown_components"] == ["chat"]


def test_all_components_known_yields_labelled_complete_total() -> None:
    module = example()
    total = module._total_billed(
        {
            "chat": module._amount(billed("0.25")),
            "evaluation": module._amount(billed("1.50")),
        }
    )

    assert total == {
        "amount": "1.75",
        "unit": "credits",
        "status": "complete",
        "includes": ["chat", "evaluation"],
    }


@pytest.mark.parametrize("known", ["chat", "evaluation"])
def test_partial_total_never_reports_a_numeric_sum(known: str) -> None:
    module = example()
    components = {"chat": None, "evaluation": None}
    components[known] = module._amount(billed("2.00"))

    total = module._total_billed(components)

    assert total["amount"] is None
    assert total["status"] == "partial"
