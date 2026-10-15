"""Child process for cross-process refresh tests: one rotation, prints its outcome."""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from file_store import FileStore

from zenture._auth.discovery import discover
from zenture._auth.errors import AuthError
from zenture._auth.http import new_client
from zenture._auth.lock import binding_lock
from zenture._auth.model import Target
from zenture._auth.session import SessionCore

if TYPE_CHECKING:
    from zenture._auth.store import RecordKey, StoredRecord


class RendezvousStore(FileStore):
    """Hold each captured ready record until every no-lock worker has read it."""

    def __init__(self, path: Path, directory: Path, participants: int) -> None:
        super().__init__(path)
        self.directory = directory
        self.participants = participants

    def load(self, identity: RecordKey) -> StoredRecord | None:
        record = super().load(identity)
        if record is None or record.state != "ready":
            raise RuntimeError("rendezvous requires a ready record")
        # Empty markers contain process identities only, never captured authority.
        (self.directory / f"{os.getpid()}.ready").touch(exist_ok=False)
        deadline = time.monotonic() + 30
        while len(list(self.directory.glob("*.ready"))) != self.participants:
            if time.monotonic() >= deadline:
                raise TimeoutError("refresh read rendezvous timed out")
            time.sleep(0.01)
        return record


def main() -> None:
    config = json.loads(sys.argv[1])
    with new_client() as client:
        discovery = discover(client, Target.from_endpoint(config["endpoint"]))
    directory = Path(config["lock_dir"])

    def lock(identity: RecordKey) -> contextlib.AbstractContextManager[None]:
        if config.get("no_lock"):
            return contextlib.nullcontext()
        return binding_lock(identity, directory=directory, wait_seconds=60)

    store = FileStore(Path(config["store"]))
    if "rendezvous" in config:
        if not config.get("no_lock"):
            raise RuntimeError("read rendezvous requires the no-lock oracle")
        store = RendezvousStore(store.path, Path(config["rendezvous"]), config["participants"])
    core = SessionCore(discovery=discovery, store=store, lock=lock)
    while time.time() < config.get("start_at", 0):
        time.sleep(0.001)
    try:
        core.refresh()
    except AuthError as exc:
        print(type(exc).__name__, flush=True)
    else:
        print("ok", flush=True)


if __name__ == "__main__":
    main()
