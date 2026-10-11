"""Utilities for removing secrets from client-visible text and metadata."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

REDACTED = "<redacted>"

_TOKEN_PATTERN = re.compile(r"\bzt_(?:live|test)_[A-Za-z0-9_-]+\b")
_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-zenture-api-key",
}


def redact_text(value: str) -> str:
    """Return text with zenture token-shaped secrets removed."""

    return _TOKEN_PATTERN.sub(REDACTED, value)


def redact_headers(headers: Mapping[str, object]) -> dict[str, str]:
    """Return a copy of HTTP headers with sensitive values redacted."""

    redacted: dict[str, str] = {}
    for name, value in headers.items():
        if name.lower() in _SENSITIVE_HEADERS:
            redacted[name] = REDACTED
        else:
            redacted[name] = redact_text(str(value))
    return redacted
