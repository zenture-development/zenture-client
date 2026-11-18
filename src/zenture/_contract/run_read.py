"""The lean public Run read: verdict, findings, billing and the optional standards and learning parts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, field_validator

from zenture._contract.response_base import RunResponseModel, coerce_tuple

FindingRef = Annotated[str, Field(max_length=256, pattern=r"^finding:[A-Za-z0-9_./:-]{1,247}$")]

FindingCategory = Literal[
    "contradicted",
    "unsupported",
    "unverifiable",
    "calculation",
    "requirement",
    "constraint",
    "standard",
    "source_inconsistent",
]


class RunStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_DEPENDENCY = "waiting_for_dependency"
    PARTIALLY_COMPLETE = "partially_complete"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    CANCEL_REQUESTED = "cancel_requested"
    SUCCEEDED = "succeeded"
    BUDGET_EXHAUSTED = "budget_exhausted"


class PublicDecision(StrEnum):
    READY = "ready"
    REVISE = "revise"
    HUMAN_REVIEW = "human_review"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class PublicRunEvidence(RunResponseModel):
    """A web source (url and excerpt) or untrusted file text (excerpt only, flagged)."""

    url: str | None = Field(
        default=None, max_length=512, pattern="^https?://[^\\x00-\\x20\\x7f<>\"']+$"
    )
    excerpt: str | None = Field(default=None, min_length=1, max_length=200)
    untrusted_file_text: Literal[True] | None = None


class PublicRunFinding(RunResponseModel):
    ref: str = Field(max_length=256, pattern=r"^finding:[A-Za-z0-9_./:-]{1,247}$")
    proven: bool
    problem: str = Field(min_length=1, max_length=1000)
    category: FindingCategory | None = None
    location: str | None = Field(default=None, min_length=1, max_length=256)
    evidence: PublicRunEvidence | None = None
    fix: str | None = Field(default=None, min_length=1, max_length=512)


class PublicRunBilling(RunResponseModel):
    """Final Credits of the Run; `pending` while settlement follows (no amount yet)."""

    status: Literal["pending", "settled", "released", "unavailable"]
    amount: str | None = Field(default=None, pattern=r"^(0|[1-9][0-9]{0,11})\.[0-9]{2}$")
    unit: Literal["credits"] = "credits"


class PublicRunStandard(RunResponseModel):
    """A standard pinned to the Run: id and result, never the standard's text."""

    standard_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")
    result: Literal["met", "violated", "unverifiable", "n/a"]


class PublicRunLearning(RunResponseModel):
    essence: str = Field(min_length=1, max_length=600)


class PublicRunCriterion(RunResponseModel):
    ref: str = Field(max_length=300)
    status: Literal["satisfied", "not_satisfied", "uncertain", "unavailable"]
    reason: str = Field(min_length=1, max_length=128)
    hard_gate: bool
    explanation: str | None = Field(default=None, min_length=1, max_length=1000)


class PublicRunStatement(RunResponseModel):
    """One statement of the answer and its assessment (offsets only, never the text)."""

    ref: str = Field(max_length=128)
    assessment: Literal["supported", "contradicted", "unsupported", "unverifiable", "not_factual"]
    reason: str = Field(min_length=1, max_length=128)
    cited: bool
    start: int = Field(ge=0)
    end: int = Field(ge=1)


class PublicRunResolvedFinding(RunResponseModel):
    """A finding of the revised Run that no longer stands: its category and the quoted place it sat at."""

    category: FindingCategory | None = None
    location: str | None = Field(default=None, min_length=1, max_length=256)


class PublicRunChanges(RunResponseModel):
    """What a revision Run changed about the findings of the Run it revises; all three lists are always stated."""

    resolved: tuple[PublicRunResolvedFinding, ...] = Field(max_length=128)
    open: tuple[FindingRef, ...] = Field(max_length=128)
    new: tuple[FindingRef, ...] = Field(max_length=128)

    @field_validator("resolved", "open", "new", mode="before")
    @classmethod
    def _lists(cls, value: object) -> object:
        return coerce_tuple(value)


class PublicRunResponse(RunResponseModel):
    """Summary of a Run: terminal runs carry the verdict, non-terminal ones `next_action` and a hint."""

    run_id: str = Field(pattern=r"^run_[A-Za-z0-9_-]{3,128}$")
    status: RunStatus
    acceptance_decision: PublicDecision | None = None
    reason: str | None = Field(default=None, max_length=128)
    next_action: str | None = Field(default=None, max_length=256)
    hint: str | None = Field(default=None, min_length=1, max_length=1000)
    findings: tuple[PublicRunFinding, ...] | None = Field(default=None, max_length=128)
    billing: PublicRunBilling | None = None
    standards: tuple[PublicRunStandard, ...] | None = Field(default=None, max_length=16)
    learning: PublicRunLearning | None = None
    eta_seconds: int | None = Field(default=None, ge=0, le=86_400)
    criteria: tuple[PublicRunCriterion, ...] | None = Field(default=None, max_length=32)
    statements: tuple[PublicRunStatement, ...] | None = Field(default=None, max_length=61)
    changes: PublicRunChanges | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, value: object) -> object:
        return RunStatus(value) if isinstance(value, str) else value

    @field_validator("acceptance_decision", mode="before")
    @classmethod
    def _acceptance_decision(cls, value: object) -> object:
        return PublicDecision(value) if isinstance(value, str) else value

    @field_validator("findings", "standards", "criteria", "statements", mode="before")
    @classmethod
    def _collections(cls, value: object) -> object:
        return coerce_tuple(value)
