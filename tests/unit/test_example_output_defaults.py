"""Examples print identifiers and status by default; result content needs an opt-in flag."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
SECRET_RESULT = "SYNTHETIC_RESULT_CONTENT_9b1e"


def load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeEvaluations:
    def run(self, **kwargs: object) -> object:
        del kwargs
        return SimpleNamespace(
            operation_id="op_eval_1",
            status="succeeded",
            result=SimpleNamespace(evaluation_id="ev_1", score=SECRET_RESULT),
        )


class FakeWizard:
    def run(self, **kwargs: object) -> object:
        del kwargs
        return SimpleNamespace(
            operation_id="op_wizard_1",
            status="succeeded",
            result=SimpleNamespace(optimized_prompt=SECRET_RESULT),
        )


class FakeClient:
    def __init__(self, **services: object) -> None:
        self.__dict__.update(services)

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_external_evaluation_prints_identifiers_without_result_by_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = load("evaluate")
    module.evaluate_external_answer(FakeClient(evaluations=FakeEvaluations()))
    out = capsys.readouterr().out
    assert "op_eval_1" in out
    assert "succeeded" in out
    assert SECRET_RESULT not in out


def test_external_evaluation_shows_result_only_with_opt_in(
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = load("evaluate")
    module.evaluate_external_answer(FakeClient(evaluations=FakeEvaluations()), show_result=True)
    assert SECRET_RESULT in capsys.readouterr().out


def test_input_wizard_hides_optimized_prompt_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load("input_wizard")
    monkeypatch.setattr(
        module.ZentureClient,
        "from_env",
        staticmethod(lambda: FakeClient(input_wizard=FakeWizard())),
    )
    module.main([])
    out = capsys.readouterr().out
    assert "op_wizard_1" in out
    assert "succeeded" in out
    assert SECRET_RESULT not in out


def test_input_wizard_prints_optimized_prompt_only_with_opt_in(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load("input_wizard")
    monkeypatch.setattr(
        module.ZentureClient,
        "from_env",
        staticmethod(lambda: FakeClient(input_wizard=FakeWizard())),
    )
    module.main(["--show-prompt"])
    assert SECRET_RESULT in capsys.readouterr().out
