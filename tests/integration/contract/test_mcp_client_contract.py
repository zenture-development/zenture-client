"""Packaging and import-boundary checks for the opt-in MCP client surface."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[3]


def test_mcp_transport_is_optional_and_not_a_default_runtime_dependency() -> None:
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'mcp = [\n  "mcp==2.0.0",\n]' in project
    assert '"mcp==2.0.0",\n]' not in project.split("[project.optional-dependencies]")[0]


def test_mcp_contract_docs_do_not_contain_credentials_or_private_routes() -> None:
    docs = (ROOT / "docs" / "mcp-client.md").read_text(encoding="utf-8")
    assert "zt_live_" not in docs
    assert "Authorization: Bearer" not in docs
    assert "/internal/" not in docs


def test_mcp_import_surface_is_explicit_and_internal_until_terminal_cutover() -> None:
    source = (ROOT / "src" / "zenture" / "_mcp" / "__init__.py").read_text(encoding="utf-8")
    exports = source.split("__all__ = ", 1)[1]
    assert json.loads(exports.replace("'", '"')) == [
        "PRODUCT_TOOL_NAMES",
        "AsyncMcpClient",
        "McpClient",
        "McpEndpoint",
        "McpRunRead",
    ]
