"""Scan public client release files for private origins and token-shaped text."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PUBLIC_PATH_PREFIXES = (
    "README.md",
    "AGENTS.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "docs/",
    "examples/",
    ".github/ISSUE_TEMPLATE/",
    "openapi/",
)
FORBIDDEN_PUBLIC_PATTERNS = {
    "token prefix": re.compile(r"zt_(?:live|test)_"),
    "local host": re.compile(r"\blocalhost\b|\b127\.0\.0\.1\b|\[::1\]", re.IGNORECASE),
    "integration host": re.compile(r"\bapi-int\.zenture\.app\b", re.IGNORECASE),
    "non-production API host": re.compile(r"\bapi-[a-z0-9-]+\.zenture\.app\b", re.IGNORECASE),
}
FORBIDDEN_TOKEN_LITERALS = re.compile(r"\bzt_(?:live|test)_[A-Za-z0-9_-]+\b")


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _is_public_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def _read(path: str) -> str | None:
    file_path = ROOT / path
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def main() -> None:
    failures: list[str] = []

    for path in _tracked_files():
        text = _read(path)
        if text is None:
            continue

        if FORBIDDEN_TOKEN_LITERALS.search(text):
            failures.append(f"{path}: contains token-shaped literal")

        if not _is_public_path(path):
            continue

        for label, pattern in FORBIDDEN_PUBLIC_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{path}: contains forbidden public {label}")

    if failures:
        raise SystemExit("Release safety check failed:\n" + "\n".join(sorted(failures)))


if __name__ == "__main__":
    main()
