"""Shared response-model base, tuple coercion and safe-text check for Run result models."""

from __future__ import annotations

import re
import unicodedata
from typing import cast

from pydantic import ConfigDict

from zenture.models import SDKBaseModel


class RunResponseModel(SDKBaseModel):
    """Strict known fields with tolerant additive response members."""

    model_config = ConfigDict(extra="ignore", frozen=True, strict=True)


def coerce_tuple(value: object) -> object:
    if isinstance(value, list):
        return tuple(cast("list[object]", value))
    return value


_SAFE_RESULT_FORBIDDEN = re.compile(
    r"(?:https?://|www\.|```|`|system\s+prompt|developer\s+prompt|chain[- ]of[- ]thought|"
    r"prompt\s+injection|api[_ -]?key|access[_ -]?token|bearer\s+|secret|password|private\s+key)",
    re.IGNORECASE,
)


def safe_result_text(value: object, *, maximum: int, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text")
    normalized = " ".join(unicodedata.normalize("NFC", value).split())
    if not normalized or len(normalized) > maximum:
        raise ValueError(f"{field_name} bound invalid")
    if (
        _SAFE_RESULT_FORBIDDEN.search(normalized)
        or re.search(r"[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]", normalized)
        or "<" in normalized
        or ">" in normalized
    ):
        raise ValueError(f"{field_name} contains unsafe content")
    return normalized
