"""The standards a Run was checked against: ids and codes only, never the standards' texts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from zenture._contract.response_base import coerce_tuple
from zenture._contract.standards import STANDARD_ID_PATTERN, StandardOwner, StandardStrength
from zenture.models import SDKBaseModel


class StandardCheckResult(SDKBaseModel):
    """One bound standard and how the evaluation judged the Run against it."""

    standard_id: str = Field(pattern=STANDARD_ID_PATTERN)
    version: int = Field(ge=1)
    strength: StandardStrength
    owner: StandardOwner
    result: Literal["met", "violated", "unverifiable", "n/a", "not_applied"]


class StandardsChecked(SDKBaseModel):
    """Present on a terminal Run that was bound to standards; absent otherwise."""

    set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    results: tuple[StandardCheckResult, ...] = Field(min_length=1, max_length=16)

    @field_validator("results", mode="before")
    @classmethod
    def _results(cls, value: object) -> object:
        return coerce_tuple(value)
