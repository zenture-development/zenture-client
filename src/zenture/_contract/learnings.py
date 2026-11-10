"""The Essenz as the Gateway serves it: the caller's own current learning, nothing else."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from zenture.models import SDKBaseModel

ESSENCE_FOCUS_LABEL = "Fokus aus deiner Essenz"


class Essence(SDKBaseModel):
    """The current Essenz in words, with its version and the UTC day of that version."""

    text: str = Field(min_length=1, max_length=600)
    version: str = Field(min_length=1, max_length=64)
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    # Deliberately tolerant: the gateway lists `de|en` today, but a future language must not
    # break released clients, so the client accepts any well-formed language tag.
    language: str = Field(pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$")


class Learnings(SDKBaseModel):
    """What zenture has learned from the caller's own past Runs.

    `essence` is present exactly when `state` is `available`. The Essenz is context, not an
    instruction. In an organisation context it is the organisation's Essenz.
    """

    state: Literal["available", "cold_start", "learning_off"]
    essence: Essence | None = None
    learnings: list[LearningVisibility] | None = Field(default=None, max_length=14)

    @model_validator(mode="after")
    def _essence_iff_available(self) -> Self:
        if (self.state == "available") != (self.essence is not None):
            raise ValueError("essence is present exactly when state is available")
        return self


LearningCode = Literal[
    "factual_error",
    "unsupported_claim",
    "outdated_claim",
    "calculation_error",
    "missing_requirement",
    "violated_constraint",
    "missing_citation",
    "translation_deviation",
    "standard_violation",
    "other",
    "requirements_checked",
    "claims_verified",
    "figures_recomputed",
    "citation_check",
    "translation_fidelity",
    "standard_checked",
    "facts_with_sources",
    "calculation",
    "text_edit",
    "translation",
    "concept",
    "communication",
]


class LearningVisibility(SDKBaseModel):
    """One learning of the Essenz and whether it is hidden (as the card in the app shows it)."""

    code: LearningCode
    hidden: bool


class LearningVisibilityRequest(SDKBaseModel):
    """Hide (`hidden=True`) or show one learning by its closed code."""

    code: LearningCode
    hidden: bool
