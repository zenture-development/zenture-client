"""Learning governance (D-195..D-198): the Run helpers carry `learning_context` and `standards`; the Run read names context, essence scope and note."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest
from pydantic import ValidationError
from test_run_reference_file import (
    ANSWER,
    API_KEY,
    _proposal,  # pyright: ignore[reportPrivateUsage] -- shared Run fixture
    _run,  # pyright: ignore[reportPrivateUsage] -- shared Run fixture
)

from zenture import AsyncZentureClient, ZentureClient
from zenture._contract import PublicRunResponse


def _sync(prepared: list[dict[str, object]]) -> ZentureClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/runs/prepare":
            prepared.append(json.loads(request.content))
            return httpx.Response(200, json=_proposal())
        return httpx.Response(202, json=_run())

    return ZentureClient(
        api_key=API_KEY,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
    )


def test_prepare_and_run_send_the_context_and_the_standards_set_only_when_given() -> None:
    prepared: list[dict[str, object]] = []
    client = _sync(prepared)
    try:
        client.runs.prepare(task="Check.", artifact=ANSWER, idempotency_key="k")
        client.runs.prepare(
            task="Check.",
            artifact=ANSWER,
            idempotency_key="k",
            learning_context="organization",
            standards="organization",
        )
        client.runs.run(
            task="Check.",
            artifact=ANSWER,
            idempotency_key="k",
            learning_context="organization",
            standards="organization",
        )
    finally:
        client.close()
    assert "learning_context" not in prepared[0]
    assert "standards" not in prepared[0]
    assert (prepared[1]["learning_context"], prepared[1]["standards"]) == (
        "organization",
        "organization",
    )
    assert prepared[2] == prepared[1]


@pytest.mark.parametrize(
    ("field", "value"), [("learning_context", "everyone"), ("standards", "personal")]
)
def test_an_unknown_value_fails_locally_before_any_request(field: str, value: str) -> None:
    prepared: list[dict[str, object]] = []
    client = _sync(prepared)
    unchecked: dict[str, Any] = {field: value}
    try:
        with pytest.raises((ValidationError, ValueError)):
            client.runs.prepare(task="Check.", artifact=ANSWER, idempotency_key="k", **unchecked)
    finally:
        client.close()
    assert prepared == []


def test_async_run_sends_the_same_fields() -> None:
    prepared: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/runs/prepare":
            prepared.append(json.loads(request.content))
            return httpx.Response(200, json=_proposal())
        return httpx.Response(202, json=_run())

    async def scenario() -> None:
        client = AsyncZentureClient(
            api_key=API_KEY,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            max_retries=0,
        )
        try:
            await client.runs.run(
                task="Check.",
                artifact=ANSWER,
                idempotency_key="k",
                learning_context="private",
                standards="organization_and_personal",
            )
        finally:
            await client.aclose()

    asyncio.run(scenario())
    assert (prepared[0]["learning_context"], prepared[0]["standards"]) == (
        "private",
        "organization_and_personal",
    )


def test_the_run_read_names_context_scope_and_note_and_a_null_scope_stays_null() -> None:
    run = PublicRunResponse.model_validate(
        {
            **_run(),
            "learning_context": "private",
            "essence_scope": None,
            "note": "learning_context_unavailable",
        }
    )
    assert (run.learning_context, run.essence_scope, run.note) == (
        "private",
        None,
        "learning_context_unavailable",
    )
    org = PublicRunResponse.model_validate(
        {**_run(), "learning_context": "organization", "essence_scope": "organization"}
    )
    assert (org.learning_context, org.essence_scope, org.note) == (
        "organization",
        "organization",
        None,
    )
    plain = PublicRunResponse.model_validate(_run())
    assert (plain.learning_context, plain.essence_scope, plain.note) == (None, None, None)
    with pytest.raises(ValidationError):
        PublicRunResponse.model_validate({**_run(), "note": "free text"})
    with pytest.raises(ValidationError):
        PublicRunResponse.model_validate({**_run(), "learning_context": "everyone"})
