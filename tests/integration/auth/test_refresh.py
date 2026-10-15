"""Scenario 6: crash-safe refresh rotation under a per-binding cross-process lock."""

from __future__ import annotations

import dataclasses
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from auth_harness import Environment, browser_opener, runtime_for

from zenture._auth.discovery import discover
from zenture._auth.errors import AuthorizationRequired, AuthUnavailable
from zenture._auth.http import new_client
from zenture._auth.lock import binding_lock
from zenture._auth.login import LoginFlow
from zenture._auth.model import CLIENT_ID, Target
from zenture._auth.session import SessionCore
from zenture._auth.store import RecordKey

if TYPE_CHECKING:
    from file_store import FileStore

WORKER = Path(__file__).with_name("refresh_worker.py")


def _login(env: Environment, store: FileStore, lock_dir: Path) -> None:
    opener, _ = browser_opener()
    LoginFlow(runtime_for(store, lock_dir, opener)).login(endpoint=env.endpoint)


def _core(
    env: Environment, store: FileStore, lock_dir: Path, *, token_endpoint: str | None = None
) -> SessionCore:
    with new_client() as client:
        discovery = discover(client, Target.from_endpoint(env.endpoint))
    if token_endpoint is not None:
        discovery = dataclasses.replace(discovery, token_endpoint=token_endpoint)
    return SessionCore(
        discovery=discovery,
        store=store,
        lock=lambda identity: binding_lock(identity, directory=lock_dir, wait_seconds=5),
        http=lambda: new_client(httpx.Timeout(1.0, connect=1.0)),
    )


def _identity(env: Environment) -> RecordKey:
    return RecordKey(env.issuer.issuer, env.mcp.resource, CLIENT_ID)


def _record(env: Environment, store: FileStore) -> Any:
    return store.load(_identity(env))


@pytest.fixture
def ready(env: Environment, file_store: FileStore, lock_dir: Path) -> FileStore:
    _login(env, file_store, lock_dir)
    return file_store


def test_rotation_replaces_the_refresh_token_and_yields_an_accepted_access_token(
    env: Environment, ready: FileStore, lock_dir: Path
) -> None:
    before = _record(env, ready)
    core = _core(env, ready, lock_dir)

    access = core.refresh()

    after = _record(env, ready)
    assert after.state == "ready"
    assert after.refresh_token != before.refresh_token
    assert env.issuer.refresh_requests == [before.refresh_token]
    assert env.issuer.accepts(access)
    assert after.binding == before.binding


def test_rotating_record_is_dropped_and_no_refresh_is_sent(
    env: Environment, ready: FileStore, lock_dir: Path
) -> None:
    record = _record(env, ready)
    ready.save(record.with_state("rotating", "r1"))
    core = _core(env, ready, lock_dir)

    with pytest.raises(AuthorizationRequired):
        core.refresh()

    assert env.issuer.refresh_requests == []
    assert _record(env, ready) is None


def test_rotating_marker_write_failure_sends_nothing_and_keeps_the_record(
    env: Environment, ready: FileStore, lock_dir: Path
) -> None:
    before = _record(env, ready)
    ready.fail_next()
    core = _core(env, ready, lock_dir)

    with pytest.raises(AuthUnavailable):
        core.refresh()

    assert env.issuer.refresh_requests == []
    assert _record(env, ready) == before


def test_connect_error_before_send_restores_ready_and_reports_unavailable(
    env: Environment, ready: FileStore, lock_dir: Path
) -> None:
    before = _record(env, ready)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        dead_port = probe.getsockname()[1]
    core = _core(env, ready, lock_dir, token_endpoint=f"http://127.0.0.1:{dead_port}/token")

    with pytest.raises(AuthUnavailable):
        core.refresh()

    assert _record(env, ready) == before
    assert env.issuer.refresh_requests == []
    # the same refresh token is still usable afterwards
    assert _core(env, ready, lock_dir).refresh()
    assert env.issuer.reuse_events == 0


@pytest.mark.parametrize("behavior", ["hang", "drop", "server_error"])
def test_outcome_unknown_after_send_stays_rotating_and_is_never_replayed(
    env: Environment, ready: FileStore, lock_dir: Path, behavior: str
) -> None:
    sent_token = _record(env, ready).refresh_token
    env.issuer.refresh_behaviors = [behavior]
    core = _core(env, ready, lock_dir)

    with pytest.raises(AuthorizationRequired):
        core.refresh()

    assert _record(env, ready).state == "rotating"
    env.issuer.refresh_hold.set()
    with pytest.raises(AuthorizationRequired):
        _core(env, ready, lock_dir).refresh()

    assert env.issuer.refresh_requests == [sent_token]
    assert _record(env, ready) is None
    assert env.issuer.reuse_events == 0


def test_invalid_grant_deletes_the_record(
    env: Environment, ready: FileStore, lock_dir: Path
) -> None:
    env.issuer.refresh_behaviors = ["invalid_grant"]

    with pytest.raises(AuthorizationRequired):
        _core(env, ready, lock_dir).refresh()

    assert _record(env, ready) is None


def test_changed_binding_after_refresh_is_dropped(
    env: Environment, ready: FileStore, lock_dir: Path
) -> None:
    env.issuer.refresh_behaviors = ["changed_generation"]

    with pytest.raises(AuthorizationRequired):
        _core(env, ready, lock_dir).refresh()

    assert _record(env, ready) is None


def test_failed_ready_write_after_success_deletes_best_effort(
    env: Environment, ready: FileStore, lock_dir: Path
) -> None:
    ready.fail_attempt_after(2)  # attempt 1 writes `rotating`, attempt 2 would write `ready`
    core = _core(env, ready, lock_dir)

    with pytest.raises(AuthorizationRequired):
        core.refresh()

    assert _record(env, ready) is None
    assert len(env.issuer.refresh_requests) == 1


def test_lock_wait_is_bounded_and_reports_unavailable(
    env: Environment, ready: FileStore, lock_dir: Path
) -> None:
    identity = _identity(env)
    core = _core(env, ready, lock_dir)
    core.lock = lambda key: binding_lock(key, directory=lock_dir, wait_seconds=0.3)

    with binding_lock(identity, directory=lock_dir, wait_seconds=1):
        started = time.monotonic()
        with pytest.raises(AuthUnavailable, match="lock_timeout"):
            core.refresh()

    assert time.monotonic() - started < 3
    assert env.issuer.refresh_requests == []
    assert _record(env, ready) is not None
    lock_files = list(lock_dir.iterdir())
    assert len(lock_files) == 1
    assert lock_files[0].read_bytes() == b""  # no secret in the lock file


def _spawn(
    env: Environment, store: FileStore, lock_dir: Path, **extra: Any
) -> subprocess.Popen[str]:
    config = {
        "start_at": time.time() + 4,
        "endpoint": env.endpoint,
        "store": str(store.path),
        "lock_dir": str(lock_dir),
        **extra,
    }
    return subprocess.Popen(
        [sys.executable, str(WORKER), json.dumps(config)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def _stop(processes: list[subprocess.Popen[str]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)


def _outcomes(processes: list[subprocess.Popen[str]], *, timeout: float = 120) -> list[str]:
    results: list[str] = []
    deadline = time.monotonic() + timeout
    try:
        for process in processes:
            out, _ = process.communicate(timeout=max(0.001, deadline - time.monotonic()))
            assert process.returncode == 0, "refresh worker crashed"
            outcome = out.strip()
            assert outcome in {"ok", "AuthorizationRequired", "AuthUnavailable"}, (
                "refresh worker did not report a recognized outcome"
            )
            results.append(outcome)
    finally:
        _stop(processes)
    return results


@pytest.mark.parametrize("script", ["raise SystemExit(1)", "pass"])
def test_worker_crash_or_missing_outcome_fails_the_harness(script: str) -> None:
    process = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True)

    with pytest.raises(AssertionError, match="refresh worker"):
        _outcomes([process])


def test_worker_timeout_fails_the_harness_and_cleans_up_all_children() -> None:
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]

    with pytest.raises(subprocess.TimeoutExpired):
        _outcomes(processes, timeout=0.05)

    assert all(process.poll() is not None for process in processes)


def test_concurrent_processes_rotate_serially_without_consumed_token_reuse(
    env: Environment, ready: FileStore, lock_dir: Path
) -> None:
    env.issuer.refresh_delay = 0.4
    initial = _record(env, ready).refresh_token

    processes = [_spawn(env, ready, lock_dir) for _ in range(3)]
    outcomes = _outcomes(processes)

    assert outcomes == ["ok", "ok", "ok"]
    assert len(env.issuer.refresh_requests) == 3
    assert len(set(env.issuer.refresh_requests)) == 3
    assert env.issuer.refresh_requests[0] == initial
    assert env.issuer.max_concurrent_refreshes == 1
    assert env.issuer.reuse_events == 0
    assert not env.issuer.grant_revoked()
    assert _record(env, ready).state == "ready"


def test_without_the_lock_the_same_scenario_reuses_a_consumed_token(
    env: Environment, ready: FileStore, lock_dir: Path, tmp_path: Path
) -> None:
    """Oracle check: the concurrency test above fails when the lock is removed."""

    initial = _record(env, ready).refresh_token
    participants = 4
    rendezvous = tmp_path / "refresh-reads"
    rendezvous.mkdir()
    processes = [
        _spawn(
            env,
            ready,
            lock_dir,
            no_lock=True,
            rendezvous=str(rendezvous),
            participants=participants,
        )
        for _ in range(participants)
    ]
    outcomes = _outcomes(processes)

    assert len(list(rendezvous.glob("*.ready"))) == participants
    assert all(marker.read_bytes() == b"" for marker in rendezvous.iterdir())
    assert len(outcomes) == participants
    assert outcomes.count("AuthorizationRequired") >= participants - 1
    assert len(env.issuer.refresh_requests) == participants
    assert all(request == initial for request in env.issuer.refresh_requests)
    assert env.issuer.reuse_events >= 1
    assert env.issuer.grant_revoked()


def test_killed_writer_after_send_leaves_a_journal_that_blocks_any_replay(
    env: Environment, ready: FileStore, lock_dir: Path
) -> None:
    sent_token = _record(env, ready).refresh_token
    env.issuer.refresh_behaviors = ["hang"]
    writer = _spawn(env, ready, lock_dir)
    try:
        assert env.issuer.refresh_seen.wait(60)
    finally:
        _stop([writer])
        env.issuer.refresh_hold.set()

    assert _record(env, ready).state == "rotating"
    survivor = _spawn(env, ready, lock_dir)

    assert _outcomes([survivor]) == ["AuthorizationRequired"]
    assert env.issuer.refresh_requests == [sent_token]
    assert env.issuer.reuse_events == 0
    assert _record(env, ready) is None
