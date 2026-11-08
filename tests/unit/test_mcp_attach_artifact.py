"""MCP attach_artifact mirrors the tool: an upload link, or a registered host-bytes file."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from test_mcp_client import ARTIFACT_REF, AsyncRecordingTransport, RecordingTransport

from zenture.mcp import AsyncMcpClient, McpClient

# Synthetic one-time token; never a real credential.
TOKEN = "tok_SYNTHETIC_upload_token_0123456789"
LINK = {
    "upload_url": "https://mcp.example.test/v1/run-artifacts/uploads/upload_abcdefgh",
    "upload_id": "upload_abcdefgh",
    "upload_token": TOKEN,
    "artifact_ref": ARTIFACT_REF,
    "expires_at": "2026-11-06T10:10:00Z",
    "next_steps": "PUT the bytes to upload_url with X-Upload-Token, then run with the artifact_ref.",
}
HOST = {
    "artifact_ref": ARTIFACT_REF,
    "content_hash": "a" * 64,
    "byte_size": 4,
    "content_type": "text/plain",
    "status": "pending",
    "retry_after_seconds": 3,
    "next_steps": "Start the run with the artifact_ref.",
}
ARGS: dict[str, Any] = {
    "file_name": "answer.txt",
    "mime_type": "text/plain",
    "byte_size": 4,
    "content_hash": "a" * 64,
}


def test_link_answer_is_parsed_and_hides_the_token() -> None:
    transport = RecordingTransport({"attach_artifact": LINK})
    result = McpClient(transport).attach_artifact(**ARGS)

    assert result.artifact_ref == ARTIFACT_REF
    assert result.upload_url == LINK["upload_url"]
    assert result.upload_id == "upload_abcdefgh"
    assert result.upload_token == TOKEN
    assert result.next_steps == LINK["next_steps"]
    assert TOKEN not in repr(result) + str(result)
    assert [name for name, _ in transport.calls] == ["attach_artifact"]


def test_host_bytes_answer_is_parsed() -> None:
    result = McpClient(RecordingTransport({"attach_artifact": HOST})).attach_artifact(**ARGS)

    assert result.artifact_ref == ARTIFACT_REF
    assert result.status == "pending"
    assert result.retry_after_seconds == 3
    assert result.content_hash == "a" * 64
    assert result.upload_token is None


@pytest.mark.asyncio
async def test_async_link_and_host_answers_are_parsed() -> None:
    link = await AsyncMcpClient(AsyncRecordingTransport({"attach_artifact": LINK})).attach_artifact(
        **ARGS
    )
    host = await AsyncMcpClient(AsyncRecordingTransport({"attach_artifact": HOST})).attach_artifact(
        **ARGS
    )

    assert link.upload_token == TOKEN
    assert TOKEN not in repr(link)
    assert host.status == "pending"


@pytest.mark.parametrize(
    "payload",
    [
        {k: v for k, v in LINK.items() if k != "upload_token"},
        {k: v for k, v in HOST.items() if k != "status"},
        {"artifact_ref": ARTIFACT_REF, "next_steps": "x"},
        {**LINK, "upload_token": "short"},
    ],
)
def test_incomplete_or_malformed_answers_are_refused(payload: dict[str, object]) -> None:
    with pytest.raises((ValidationError, Exception)) as caught:
        McpClient(RecordingTransport({"attach_artifact": payload})).attach_artifact(**ARGS)
    assert TOKEN not in str(caught.value)
