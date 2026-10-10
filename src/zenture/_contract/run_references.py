"""Canonical public Run cursor and terminal-reference validation.

Filepath: src/zenture/_contract/run_references.py
Purpose: Keep REST, SSE and opt-in MCP Run reference validation identical.
Input: Opaque cursor or terminal reference values.
Output: Validated unchanged values, or a fail-closed ValueError.
Dependencies: Python standard library only.
Critical Logic: Opaque values are never normalized before forwarding.
"""

from __future__ import annotations

import re
from typing import cast

RUN_CURSOR_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{1,512}$")
RUN_TERMINAL_REF_PATTERN = re.compile(r"^[A-Za-z0-9._:/~-]{1,128}$")


def validate_run_cursor(value: object, *, field: str = "cursor") -> str:
    if not isinstance(value, str) or RUN_CURSOR_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} is invalid")
    return value


def validate_terminal_refs(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise ValueError("terminal_refs must be an array")
    refs = tuple(cast("list[object] | tuple[object, ...]", value))
    if len(refs) > 8 or any(
        not isinstance(item, str) or RUN_TERMINAL_REF_PATTERN.fullmatch(item) is None
        for item in refs
    ):
        raise ValueError("terminal_refs must contain safe references")
    return cast("tuple[str, ...]", refs)


__all__ = [
    "RUN_CURSOR_PATTERN",
    "RUN_TERMINAL_REF_PATTERN",
    "validate_run_cursor",
    "validate_terminal_refs",
]
