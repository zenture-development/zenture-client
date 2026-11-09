"""Offline contract checks for the documented REST and MCP Run journeys.

Input: synthetic requests/responses. Output: observed public client behavior.
Dependencies: pytest and httpx. No credentials, login or external service use.
"""

from __future__ import annotations

import importlib.util
import re
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import httpx
import pytest

from zenture import ZentureClient
from zenture.errors import ZentureMCPError, ZenturePollingTimeoutError
from zenture.mcp import McpClient

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "run_guide_example"


def example(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / "examples" / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_payload(
    status: str = "completed", *, unavailable_reason: str = "projection_incomplete"
) -> dict[str, object]:
    return {
        "run_id": RUN_ID,
        "generation": 1,
        "work_type": "answer",
        "input_kind": "text",
        "profile": "standard",
        "status": status,
        "created_at": "2026-10-07T09:00:00Z",
        "updated_at": "2026-10-07T09:00:00Z",
        "acceptance_decision": "revise" if status == "completed" else None,
        "safe_result_content": {"status": "unavailable", "reason_code": unavailable_reason},
    }


def test_rest_example_starts_once_waits_and_reads_full_result() -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/prepare"):
            return httpx.Response(
                200,
                json={
                    "proposal_id": "33333333-3333-4333-8333-333333333333",
                    "proposal_version": 1,
                    "expires_at": "2026-10-07T10:00:00Z",
                    "inferred_work_type": "answer",
                    "task_contract_summary": {
                        "work_type": "answer",
                        "summary_ref": "snapshot:guide",
                        "requirement_count": 1,
                    },
                    "expected_duration_seconds": 30,
                    "start_admissible": True,
                    "proposal_hash": "a" * 64,
                },
            )
        return httpx.Response(
            200, json=run_payload("queued" if request.method == "POST" else "completed")
        )

    with ZentureClient(
        api_key="zt_" + "live_" + "00000000000000000000000000000000",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    ) as client:
        result = example("run_review").review_selected_text(
            client, task="Name two colours.", text="Blue.", saved_key="review_123"
        )
    assert result.acceptance_decision == "revise"
    assert result.safe_result_content.status == "unavailable"
    assert [r.url.path for r in requests if r.method == "POST"] == ["/v1/runs/prepare", "/v1/runs"]
    assert requests[0].headers["Idempotency-Key"] == "review_123:prepare"
    assert requests[1].headers["Idempotency-Key"] == "review_123:create"
    assert requests[-1].url.params["view"] == "full"


class McpPort:
    def __init__(
        self,
        *,
        ongoing: bool = False,
        fail_start: bool = False,
        unavailable_reason: str = "projection_incomplete",
    ) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.ongoing = ongoing
        self.fail_start = fail_start
        self.unavailable_reason = unavailable_reason

    def list_tools(self) -> object:
        return {
            "tools": [
                {"name": name}
                for name in ("run", "list_runs", "get_run", "cancel_run", "record_run_outcome")
            ]
        }

    def call_tool(self, name: str, arguments: Any) -> object:
        self.calls.append((name, dict(arguments)))
        if name == "run" and self.fail_start:
            raise TimeoutError("synthetic transport timeout")
        payload = run_payload(
            "queued" if name == "run" or self.ongoing else "completed",
            unavailable_reason=self.unavailable_reason,
        )
        if name == "run":
            payload["idempotency_key"] = arguments["idempotency_key"]
        return {"structuredContent": payload}


@pytest.mark.parametrize("reason", ["projection_incomplete", "result_content_expired"])
def test_mcp_example_unwraps_result_and_preserves_non_ready_decision(reason: str) -> None:
    port = McpPort(unavailable_reason=reason)
    result = example("mcp_run_review").review_selected_text(
        McpClient(port), task="Name two colours.", text="Blue.", saved_key="review_123"
    )
    assert result.run_id == RUN_ID
    assert result.acceptance_decision == "revise"
    assert result.safe_result_content.status == "unavailable"
    assert result.safe_result_content.reason_code == reason
    assert [name for name, _ in port.calls] == ["run", "get_run", "get_run"]
    assert port.calls[0][1]["idempotency_key"] == "review_123"
    assert port.calls[-1][1]["view"] == "full"


def test_mcp_example_timeout_retains_run_id_without_restart_or_cancel() -> None:
    port = McpPort(ongoing=True)
    with pytest.raises(ZenturePollingTimeoutError) as exc:
        example("mcp_run_review").review_selected_text(
            McpClient(port),
            task="Review.",
            text="Selected text.",
            saved_key="review_123",
            timeout=0.2,
        )
    assert exc.value.operation_id == RUN_ID
    names = [name for name, _ in port.calls]
    assert names[0] == "run"
    assert names.count("run") == 1
    assert "cancel_run" not in names


class SlowFullReadPort(McpPort):
    """Completes the summary at once; the full read finishes after the caller budget."""

    def call_tool(self, name: str, arguments: Any) -> object:
        if name == "get_run" and arguments.get("view") == "full":
            time.sleep(0.3)
        return super().call_tool(name, arguments)


def test_mcp_example_rejects_full_read_that_finishes_after_the_budget() -> None:
    port = SlowFullReadPort()
    with pytest.raises(ZenturePollingTimeoutError) as exc:
        example("mcp_run_review").review_selected_text(
            McpClient(port),
            task="Review.",
            text="Selected text.",
            saved_key="review_123",
            timeout=0.2,
        )
    assert exc.value.operation_id == RUN_ID
    assert [name for name, _ in port.calls] == ["run", "get_run", "get_run"]


def test_mcp_example_uncertain_start_propagates_original_key_without_retry() -> None:
    port = McpPort(fail_start=True)
    with pytest.raises(ZentureMCPError) as exc:
        example("mcp_run_review").review_selected_text(
            McpClient(port), task="Review.", text="Selected text.", saved_key="review_123"
        )
    assert exc.value.idempotency_key == "review_123"
    assert [name for name, _ in port.calls] == ["run"]


def _readme_quickstart_blocks() -> tuple[str, str]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    section = text.split("## Quickstart: your first Run", 1)[1].split("### A file Run", 1)[0]
    blocks = re.findall(r"```python\n(.*?)```", section, re.DOTALL)
    assert len(blocks) == 2
    return blocks[0], blocks[1]


def test_readme_rest_quickstart_runs_against_the_public_client(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/prepare"):
            return httpx.Response(
                200,
                json={
                    "proposal_id": "33333333-3333-4333-8333-333333333333",
                    "proposal_version": 1,
                    "expires_at": "2026-10-07T10:00:00Z",
                    "inferred_work_type": "answer",
                    "task_contract_summary": {
                        "work_type": "answer",
                        "summary_ref": "snapshot:guide",
                        "requirement_count": 1,
                    },
                    "expected_duration_seconds": 30,
                    "start_admissible": True,
                    "proposal_hash": "a" * 64,
                },
            )
        return httpx.Response(
            200, json=run_payload("queued" if request.method == "POST" else "completed")
        )

    monkeypatch.setenv("ZENTURE_API_KEY", "zt_" + "live_" + "0" * 32)
    original = ZentureClient.from_env

    def from_env_with_mock_transport(cls: type[ZentureClient]) -> ZentureClient:
        return original(http_client=httpx.Client(transport=httpx.MockTransport(respond)))

    monkeypatch.setattr(ZentureClient, "from_env", classmethod(from_env_with_mock_transport))
    exec(compile(_readme_quickstart_blocks()[0], "README-rest", "exec"), {})
    assert "completed revise" in capsys.readouterr().out
    assert [r.method + r.url.path for r in requests if r.method == "POST"] == [
        "POST/v1/runs/prepare",
        "POST/v1/runs",
    ]
    assert requests[-1].url.params["view"] == "full"


def test_readme_mcp_quickstart_runs_against_the_public_client(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    port = McpPort()

    def connect_to_fake_port(cls: type[McpClient]) -> nullcontext[McpClient]:
        return nullcontext(McpClient(port))

    monkeypatch.setattr(McpClient, "connect", classmethod(connect_to_fake_port))
    exec(compile(_readme_quickstart_blocks()[1], "README-mcp", "exec"), {})
    assert "completed revise" in capsys.readouterr().out
    assert port.calls[0][0] == "run"
    assert port.calls[0][1]["idempotency_key"] == "review_case_123"
    assert port.calls[-1][1]["view"] == "full"


def _readme_file_run_blocks() -> tuple[str, str]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    section = text.split("### A file Run and a source check", 1)[1].split("### Anatomy", 1)[0]
    blocks = re.findall(r"```python\n(.*?)```", section, re.DOTALL)
    assert len(blocks) == 2
    return blocks[0], blocks[1]


def test_readme_file_run_and_source_check_retry_until_the_file_is_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "report.pdf").write_bytes(b"%PDF-1.7\nbytes")
    monkeypatch.chdir(tmp_path)

    def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(time, "sleep", no_sleep)
    run_bodies: list[bytes] = []
    not_ready = {"left": 1}

    def respond(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/v1/run-artifacts/signed-upload":
            return httpx.Response(
                200,
                json={
                    "upload_id": "upload_abcdefgh",
                    "upload_url": "https://api.zenture.app/v1/run-artifacts/uploads/upload_abcdefgh",
                    "upload_token": "tok_SYNTHETIC_upload_token_0123456789",
                    "artifact_ref": "art_abcdefgh",
                    "expires_at": "2026-11-06T10:10:00Z",
                },
            )
        if request.method == "PUT":
            return httpx.Response(
                202,
                json={
                    "artifact_ref": "art_abcdefgh",
                    "status": "pending",
                    "retry_after_seconds": 3,
                    "next_step": "start_run",
                },
            )
        if path == "/v1/runs/prepare":
            if not_ready["left"]:
                not_ready["left"] -= 1
                return httpx.Response(
                    409,
                    json={
                        "error": {
                            "code": "artifact_not_ready",
                            "message": "Still being read.",
                            "retry_after_seconds": 3,
                        },
                        "request_id": "req_1",
                    },
                )
            run_bodies.append(request.read())
            return httpx.Response(
                200,
                json={
                    "proposal_id": "33333333-3333-4333-8333-333333333333",
                    "proposal_version": 1,
                    "expires_at": "2026-10-07T10:00:00Z",
                    "inferred_work_type": "answer",
                    "task_contract_summary": {
                        "work_type": "answer",
                        "summary_ref": "snapshot:guide",
                        "requirement_count": 1,
                    },
                    "expected_duration_seconds": 30,
                    "start_admissible": True,
                    "proposal_hash": "a" * 64,
                },
            )
        return httpx.Response(200, json=run_payload("queued"))

    monkeypatch.setenv("ZENTURE_API_KEY", "zt_" + "live_" + "0" * 32)
    original = ZentureClient.from_env

    def from_env_with_mock_transport(cls: type[ZentureClient]) -> ZentureClient:
        return original(http_client=httpx.Client(transport=httpx.MockTransport(respond)))

    monkeypatch.setattr(ZentureClient, "from_env", classmethod(from_env_with_mock_transport))
    namespace: dict[str, Any] = {}
    exec(compile(_readme_file_run_blocks()[0], "README-file-run", "exec"), namespace)
    assert not_ready["left"] == 0
    assert len(run_bodies) == 2
    assert b'"zenture_ref"' in run_bodies[0]
    assert b'"reference_file":{"type":"zenture_ref","value":"art_abcdefgh"}' in run_bodies[1]
    assert namespace["source_check"].run_id == RUN_ID


def test_readme_mcp_source_check_sends_reference_file() -> None:
    port = McpPort()
    namespace: dict[str, Any] = {
        "McpClient": type(
            "Connect", (), {"connect": staticmethod(lambda: nullcontext(McpClient(port)))}
        )
    }
    exec(compile(_readme_file_run_blocks()[1], "README-mcp-source", "exec"), namespace)
    assert port.calls[0][0] == "run"
    assert port.calls[0][1]["reference_file"] == "art_abcdefgh"
