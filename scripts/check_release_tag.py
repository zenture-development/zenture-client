"""Validate that a release tag matches the client package version."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

VERSION_PATTERN = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)
TAG_PATTERN = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+[a-zA-Z0-9.-]*$")


def _read_sdk_version() -> str:
    version_file = Path("src/zenture/_version.py")
    match = VERSION_PATTERN.search(version_file.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"Could not read __version__ from {version_file}.")
    return match.group(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tag", help="Git tag, including the leading v.")
    args = parser.parse_args()

    tag = args.tag
    if TAG_PATTERN.fullmatch(tag) is None:
        raise SystemExit(f"Tag '{tag}' is not a supported release tag.")

    package_version = _read_sdk_version()
    tag_version = tag.removeprefix("v")
    if tag_version != package_version:
        raise SystemExit(
            f"Release tag version '{tag_version}' does not match package "
            f"version '{package_version}'."
        )

    print(f"Release tag {tag} matches package version {package_version}.")


if __name__ == "__main__":
    main()
