"""Actionable finding models of the composed safe Run result."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from zenture._contract.response_base import RunResponseModel, coerce_tuple, safe_result_text

SafeResultFindingCategory = Literal[
    "task_requirement",
    "task_constraint",
    "task_consistency",
    "arithmetic",
    "source_missing",
    "source_unavailable",
    "source_support_missing",
    "source_contradiction",
    "partial_verification",
    "prohibition_violated",
    "commitment_unsupported",
    "forecast_as_certain",
    "invented_figure",
    "internal_contradiction",
    "requirement_omitted",
]

_FINDING_TEXT_MAXIMUM = {
    "location": 256,
    "actual": 512,
    "expected": 512,
    "why": 512,
    "fix_instruction": 512,
    "what": 512,
}


SafeResultFindingSubjectKind = Literal["requirement", "claim", "constraint", "arithmetic", "defect"]
SafeResultDefectType = Literal[
    "prohibition_violated",
    "commitment_unsupported",
    "forecast_as_certain",
    "invented_figure",
    "internal_contradiction",
    "requirement_omitted",
]


class SafeResultLocation(RunResponseModel):
    """Where a finding sits in the frozen answer or task (code-point offsets, end exclusive)."""

    source: Literal["answer", "task"]
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    excerpt: str | None = Field(default=None, min_length=1, max_length=160)
    status: Literal["shown", "withheld"]

    @field_validator("excerpt")
    @classmethod
    def _safe_excerpt(cls, value: object) -> str | None:
        if value is None:
            return None
        return safe_result_text(value, maximum=160, field_name="excerpt")

    @model_validator(mode="after")
    def _shape(self) -> SafeResultLocation:
        if self.end <= self.start or (self.status == "shown") != (self.excerpt is not None):
            raise ValueError("finding location invalid")
        return self


class SafeResultFinding(RunResponseModel):
    finding_ref: str = Field(max_length=256, pattern=r"^finding:[A-Za-z0-9_./:-]{1,247}$")
    title: str = Field(min_length=1, max_length=256)
    summary: str = Field(min_length=1, max_length=2000)
    explanation: str = Field(min_length=1, max_length=4000)
    confidence: Literal["low", "medium", "high"]
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    subject_kind: SafeResultFindingSubjectKind | None = None
    category: SafeResultFindingCategory | None = None
    reason_code: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$"
    )
    defect_type: SafeResultDefectType | None = None
    profile: str | None = Field(default=None, min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    what: str | None = Field(default=None, min_length=1, max_length=512)
    locations: tuple[SafeResultLocation, ...] = Field(default_factory=tuple, max_length=3)
    location: str | None = Field(default=None, min_length=1, max_length=256)
    actual: str | None = Field(default=None, min_length=1, max_length=512)
    expected: str | None = Field(default=None, min_length=1, max_length=512)
    why: str | None = Field(default=None, min_length=1, max_length=512)
    fix_instruction: str | None = Field(default=None, min_length=1, max_length=512)

    @field_validator("location", "actual", "expected", "why", "fix_instruction", "what")
    @classmethod
    def _safe_finding_text(cls, value: object, info: Any) -> str | None:
        if value is None:
            return None
        return safe_result_text(
            value, maximum=_FINDING_TEXT_MAXIMUM[info.field_name], field_name=info.field_name
        )

    @field_validator("evidence_refs", "locations", mode="before")
    @classmethod
    def _refs(cls, value: object) -> object:
        return coerce_tuple(value)

    @field_validator("title", "summary", "explanation")
    @classmethod
    def _safe_text(cls, value: object, info: Any) -> str:
        return safe_result_text(
            value,
            maximum={"title": 256, "summary": 2000, "explanation": 4000}[info.field_name],
            field_name=info.field_name,
        )
