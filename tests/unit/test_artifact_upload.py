"""Two-step file upload: signed-upload issue, then a token-authenticated PUT, no bearer."""

from __future__ import annotations

import hashlib
import io
import json
from typing import TYPE_CHECKING
from uuid import UUID

import httpx
import pytest

from zenture import AsyncZentureClient, ZentureClient
from zenture.errors import (
    ZentureArtifactExtractFailedError,
    ZentureArtifactNotFoundError,
    ZentureArtifactNotReadyError,
    ZentureArtifactQuotaExceededError,
    ZentureArtifactTooLargeError,
    ZentureArtifactTypeUnsupportedError,
    ZentureResponseError,
    ZentureTransportError,
    error_from_response,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

API_KEY = f"zt_live_{UUID(int=0).hex}"
BASE = "https://api.zenture.app"
UPLOAD_PATH = "/v1/run-artifacts/uploads/upload_abcdefgh"
UPLOAD_URL = BASE + UPLOAD_PATH
# Synthetic one-time token; never a real credential.
TOKEN = "tok_SYNTHETIC_upload_token_0123456789"
CONTENT = b"%PDF-1.7\nbytes"
HASH = hashlib.sha256(CONTENT).hexdigest()


def _issued(upload_url: str = UPLOAD_URL) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "upload_id": "upload_abcdefgh",
            "upload_url": upload_url,
            "upload_token": TOKEN,
            "artifact_ref": "art_abcdefgh",
            "expires_at": "2026-11-06T10:10:00Z",
        },
    )


def _accepted() -> httpx.Response:
    return httpx.Response(
        202,
        json={
            "artifact_ref": "art_abcdefgh",
            "status": "pending",
            "retry_after_seconds": 3,
            "next_step": "start_run",
        },
    )


class Flow:
    """Records the two requests and answers like the Gateway."""

    def __init__(
        self,
        *,
        upload_url: str = UPLOAD_URL,
        put_response: Callable[[httpx.Request], httpx.Response] | None = None,
    ) -> None:
        self.upload_url = upload_url
        self.put_response = put_response or (lambda _request: _accepted())
        self.requests: list[httpx.Request] = []
        self.put_bodies: list[bytes] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "POST":
            return _issued(self.upload_url)
        self.put_bodies.append(request.read())
        return self.put_response(request)

    async def ahandle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "POST":
            return _issued(self.upload_url)
        self.put_bodies.append(await request.aread())
        return self.put_response(request)


def _sync(flow: Flow, **kwargs: object) -> ZentureClient:
    return ZentureClient(
        api_key=API_KEY,
        http_client=httpx.Client(transport=httpx.MockTransport(flow.handle)),
        **kwargs,  # type: ignore[arg-type]
    )


def _async(flow: Flow, **kwargs: object) -> AsyncZentureClient:
    return AsyncZentureClient(
        api_key=API_KEY,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(flow.ahandle)),
        **kwargs,  # type: ignore[arg-type]
    )


def _args(content: object = CONTENT, **extra: object) -> dict[str, object]:
    return {
        "file_name": "answer.pdf",
        "mime_type": "application/pdf",
        "content": content,
        "content_hash": HASH,
        "idempotency_key": "artifact-1",
        **extra,
    }


def test_sync_attach_issues_then_puts_with_token_and_no_bearer() -> None:
    flow = Flow()
    client = _sync(flow)

    accepted = client.runs.attach_artifact(**_args())  # type: ignore[arg-type]

    issue, put = flow.requests
    assert (issue.method, issue.url.path) == ("POST", "/v1/run-artifacts/signed-upload")
    assert issue.headers["authorization"] == f"Bearer {API_KEY}"
    assert issue.headers["idempotency-key"] == "artifact-1"
    assert json.loads(issue.content) == {
        "file_name": "answer.pdf",
        "mime_type": "application/pdf",
        "byte_size": len(CONTENT),
        "content_hash": HASH,
    }
    assert (put.method, str(put.url)) == ("PUT", UPLOAD_URL)
    assert put.headers["x-upload-token"] == TOKEN
    assert put.headers["content-type"] == "application/pdf"
    assert "authorization" not in put.headers
    assert "idempotency-key" not in put.headers
    assert TOKEN not in str(put.url)
    assert flow.put_bodies == [CONTENT]
    assert accepted.artifact_ref == "art_abcdefgh"
    assert accepted.status == "pending"
    assert accepted.retry_after_seconds == 3
    assert accepted.next_step == "start_run"
    assert TOKEN not in repr(accepted)
    client.close()


@pytest.mark.asyncio
async def test_async_attach_issues_then_puts_with_token_and_no_bearer() -> None:
    flow = Flow()
    client = _async(flow)

    accepted = await client.runs.attach_artifact(**_args())  # type: ignore[arg-type]

    _issue, put = flow.requests
    assert (put.method, str(put.url)) == ("PUT", UPLOAD_URL)
    assert put.headers["x-upload-token"] == TOKEN
    assert put.headers["content-type"] == "application/pdf"
    assert "authorization" not in put.headers
    assert flow.put_bodies == [CONTENT]
    assert accepted.status == "pending"
    await client.aclose()


def test_sync_attach_streams_file_without_closing_caller_source() -> None:
    flow = Flow()
    client = _sync(flow)
    source = io.BytesIO(CONTENT)

    client.runs.attach_artifact(**_args(source, byte_size=len(CONTENT)))  # type: ignore[arg-type]

    assert flow.put_bodies == [CONTENT]
    assert flow.requests[1].headers["content-length"] == str(len(CONTENT))
    assert not source.closed
    client.close()


@pytest.mark.asyncio
async def test_async_attach_streams_async_iterable() -> None:
    flow = Flow()
    client = _async(flow)

    async def chunks() -> AsyncIterator[bytes]:
        yield CONTENT[:5]
        yield CONTENT[5:]

    await client.runs.attach_artifact(**_args(chunks(), byte_size=len(CONTENT)))  # type: ignore[arg-type]

    assert flow.put_bodies == [CONTENT]
    await client.aclose()


def test_sync_attach_rejects_stream_without_declared_size_before_any_request() -> None:
    flow = Flow()
    client = _sync(flow)

    with pytest.raises(ValueError, match="byte_size"):
        client.runs.attach_artifact(**_args(iter((CONTENT,))))  # type: ignore[arg-type]

    assert flow.requests == []
    client.close()


@pytest.mark.asyncio
async def test_async_attach_rejects_stream_without_declared_size_before_any_request() -> None:
    flow = Flow()
    client = _async(flow)

    async def chunks() -> AsyncIterator[bytes]:
        yield CONTENT

    with pytest.raises(ValueError, match="byte_size"):
        await client.runs.attach_artifact(**_args(chunks()))  # type: ignore[arg-type]

    assert flow.requests == []
    await client.aclose()


def test_sync_attach_rejects_stream_overrun_hash_mismatch_and_non_bytes_chunk() -> None:
    flow = Flow()
    client = _sync(flow)
    size = len(CONTENT)

    with pytest.raises(ValueError, match="exceeds declared byte_size"):
        client.runs.attach_artifact(
            **_args(iter((CONTENT, b"extra")), byte_size=size)  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="content_hash"):
        client.runs.attach_artifact(
            **{**_args(iter((b"x" * size,)), byte_size=size)}  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="chunks must be bytes"):
        client.runs.attach_artifact(
            **_args(iter((CONTENT[:-1], "s")), byte_size=size)  # type: ignore[arg-type]
        )
    client.close()


@pytest.mark.asyncio
async def test_async_attach_rejects_stream_overrun_hash_mismatch_and_non_bytes_chunk() -> None:
    flow = Flow()
    client = _async(flow)
    size = len(CONTENT)

    async def overrun() -> AsyncIterator[bytes]:
        yield CONTENT
        yield b"extra"

    async def wrong() -> AsyncIterator[bytes]:
        yield b"x" * size

    async def mixed() -> AsyncIterator[object]:
        yield CONTENT[:-1]
        yield "s"

    with pytest.raises(ValueError, match="exceeds declared byte_size"):
        await client.runs.attach_artifact(**_args(overrun(), byte_size=size))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="content_hash"):
        await client.runs.attach_artifact(**_args(wrong(), byte_size=size))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="chunks must be bytes"):
        await client.runs.attach_artifact(**_args(mixed(), byte_size=size))  # type: ignore[arg-type]
    await client.aclose()


def test_sync_attach_rejects_hash_mismatch_before_any_request() -> None:
    flow = Flow()
    client = _sync(flow)

    with pytest.raises(ValueError, match="content_hash"):
        client.runs.attach_artifact(**_args(b"other bytes"))  # type: ignore[arg-type]

    assert flow.requests == []
    client.close()


def test_sync_attach_stream_overrun_is_refused_while_sending() -> None:
    flow = Flow()
    client = _sync(flow)

    with pytest.raises((ValueError, ZentureTransportError)):
        client.runs.attach_artifact(
            **_args(io.BytesIO(CONTENT + b"x"), byte_size=len(CONTENT))  # type: ignore[arg-type]
        )
    client.close()


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://api.zenture.app/v1/run-artifacts/uploads/upload_abcdefgh",
        "https://evil.example/v1/run-artifacts/uploads/upload_abcdefgh",
        "https://api.zenture.app:8443/v1/run-artifacts/uploads/upload_abcdefgh",
        "https://api.zenture.app/v1/runs/uploads/upload_abcdefgh",
        "https://api.zenture.app/v1/run-artifacts/uploads/../signed-upload",
        "https://api.zenture.app/v1/run-artifacts/uploads/",
        "https://api.zenture.app/v1/run-artifacts/uploads/upload_abcdefgh?x=1",
        "https://user@api.zenture.app/v1/run-artifacts/uploads/upload_abcdefgh",
        "/v1/run-artifacts/uploads/upload_abcdefgh",
    ],
)
def test_sync_attach_refuses_foreign_upload_url_without_sending_bytes_or_token(
    bad_url: str,
) -> None:
    flow = Flow(upload_url=bad_url)
    client = _sync(flow)

    with pytest.raises(ZentureResponseError) as caught:
        client.runs.attach_artifact(**_args())  # type: ignore[arg-type]

    assert [r.method for r in flow.requests] == ["POST"]
    assert flow.put_bodies == []
    assert TOKEN not in str(caught.value) + repr(caught.value)
    client.close()


@pytest.mark.asyncio
async def test_async_attach_refuses_foreign_upload_url() -> None:
    flow = Flow(upload_url="https://evil.example/v1/run-artifacts/uploads/upload_abcdefgh")
    client = _async(flow)

    with pytest.raises(ZentureResponseError):
        await client.runs.attach_artifact(**_args())  # type: ignore[arg-type]

    assert [r.method for r in flow.requests] == ["POST"]
    await client.aclose()


def test_sync_attach_allows_loopback_http_on_the_client_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZENTURE_SDK_ALLOW_NON_PROD_BASE_URL", "1")
    url = "http://127.0.0.1:8080/v1/run-artifacts/uploads/upload_abcdefgh"
    flow = Flow(upload_url=url)
    client = ZentureClient(
        api_key="zt_test_" + UUID(int=0).hex,
        base_url="http://127.0.0.1:8080",
        http_client=httpx.Client(transport=httpx.MockTransport(flow.handle)),
    )

    client.runs.attach_artifact(**_args())  # type: ignore[arg-type]

    assert str(flow.requests[1].url) == url
    client.close()


def test_sync_attach_does_not_follow_redirect_on_put() -> None:
    flow = Flow(
        put_response=lambda _r: httpx.Response(
            307, headers={"location": "https://evil.example/collect"}
        )
    )
    client = ZentureClient(
        api_key=API_KEY,
        http_client=httpx.Client(transport=httpx.MockTransport(flow.handle), follow_redirects=True),
    )

    with pytest.raises(ZentureResponseError) as caught:
        client.runs.attach_artifact(**_args())  # type: ignore[arg-type]

    assert [r.method for r in flow.requests] == ["POST", "PUT"]
    assert TOKEN not in str(caught.value) + repr(caught.value)
    client.close()


@pytest.mark.asyncio
async def test_async_attach_does_not_follow_redirect_on_put() -> None:
    flow = Flow(
        put_response=lambda _r: httpx.Response(302, headers={"location": "https://x.example/"})
    )
    client = AsyncZentureClient(
        api_key=API_KEY,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(flow.ahandle), follow_redirects=True
        ),
    )

    with pytest.raises(ZentureResponseError):
        await client.runs.attach_artifact(**_args())  # type: ignore[arg-type]

    assert [r.method for r in flow.requests] == ["POST", "PUT"]
    await client.aclose()


def test_sync_put_is_never_retried_because_the_token_is_single_use() -> None:
    attempts = 0

    def reset(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadError("connection reset")

    flow = Flow(put_response=reset)
    client = _sync(flow, max_retries=2, initial_retry_backoff=0.0, max_retry_backoff=0.0)

    with pytest.raises(ZentureTransportError) as caught:
        client.runs.attach_artifact(**_args())  # type: ignore[arg-type]

    assert attempts == 1
    assert TOKEN not in str(caught.value) + repr(caught.value)
    client.close()


def test_sync_rejected_token_raises_without_leaking_it() -> None:
    flow = Flow(
        put_response=lambda _r: httpx.Response(
            401,
            json={
                "error": {"code": "unauthorized", "message": "Unauthorized."},
                "request_id": "req_1",
            },
        )
    )
    client = _sync(flow)

    with pytest.raises(Exception) as caught:  # noqa: PT011
        client.runs.attach_artifact(**_args())  # type: ignore[arg-type]

    assert caught.value.__class__.__name__ == "ZentureAuthenticationError"
    assert TOKEN not in str(caught.value) + repr(caught.value)
    client.close()


def test_sync_quota_refusal_at_issue_maps_to_closed_error_without_retry() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            429,
            json={
                "error": {"code": "artifact_quota_exceeded", "message": "Quota used."},
                "request_id": "req_1",
            },
        )

    client = ZentureClient(
        api_key=API_KEY,
        max_retries=2,
        initial_retry_backoff=0.0,
        max_retry_backoff=0.0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ZentureArtifactQuotaExceededError):
        client.runs.attach_artifact(**_args())  # type: ignore[arg-type]
    assert attempts == 1
    client.close()


def test_signed_upload_and_old_bearer_route_are_gone() -> None:
    client = ZentureClient(api_key=API_KEY)
    assert not hasattr(client.runs, "signed_upload")
    with pytest.raises(TypeError):
        client.runs.attach_artifact(upload_id="upload_abcdefgh", **_args())  # type: ignore[arg-type]
    client.close()


@pytest.mark.parametrize(
    ("status", "code", "error_type"),
    [
        (409, "artifact_not_ready", ZentureArtifactNotReadyError),
        (422, "artifact_too_large", ZentureArtifactTooLargeError),
        (415, "artifact_type_unsupported", ZentureArtifactTypeUnsupportedError),
        (422, "artifact_extract_failed", ZentureArtifactExtractFailedError),
        (404, "artifact_not_found", ZentureArtifactNotFoundError),
        (429, "artifact_quota_exceeded", ZentureArtifactQuotaExceededError),
    ],
)
def test_closed_artifact_errors_map_to_typed_exceptions(
    status: int, code: str, error_type: type[Exception]
) -> None:
    error = error_from_response(
        status_code=status,
        payload={"error": {"code": code, "message": "m"}, "request_id": "req_1"},
        headers={},
    )
    assert type(error) is error_type
    assert error.error_code == code  # type: ignore[attr-defined]
    assert error.status_code == status  # type: ignore[attr-defined]


def test_artifact_not_ready_carries_retry_after_seconds() -> None:
    error = error_from_response(
        status_code=409,
        payload={
            "error": {
                "code": "artifact_not_ready",
                "message": "Still being read.",
                "retry_after_seconds": 7,
            },
            "request_id": "req_1",
        },
        headers={},
    )
    assert isinstance(error, ZentureArtifactNotReadyError)
    assert error.retry_after_seconds == 7
