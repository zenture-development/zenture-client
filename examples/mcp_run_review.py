"""Review selected text through MCP without implicit login or automatic restart.

Input: connected MCP client, selected task/text, persisted operation key.
Output: typed full Run response or error retaining the original identity.
Dependencies: time and zenture. Importing this file makes no service calls.
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

from zenture.errors import ZenturePollingTimeoutError

if TYPE_CHECKING:
    from zenture.mcp import McpClient
    from zenture.types import PublicRunResponse


def review_selected_text(
    client: McpClient,
    *,
    task: str,
    text: str,
    saved_key: str,
    timeout: float = 120.0,
) -> PublicRunResponse:
    """Start once, observe the Run with wait_run, then read the full Run.

    Persist saved_key and the exact task/text before dispatch; starting may
    consume Credits. timeout is one caller budget that covers the wait and the
    final full read. A Run that completes but whose full read finishes after the
    budget raises ZenturePollingTimeoutError with the Run ID; it is not returned
    late. No failure triggers a replacement start, cancellation or login.
    Inspect acceptance_decision and safe_result_content availability rather than
    assuming completion is ready.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive and finite")
    client.require_product_tools()
    deadline = time.monotonic() + timeout
    started = client.run(
        task=task,
        artifact={"type": "text", "value": text},
        idempotency_key=saved_key,
    )
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ZenturePollingTimeoutError(operation_id=started.run_id, idempotency_key=saved_key)
    observed = client.wait_run(started.run_id, remaining)
    full = client.get_run(started.run_id, view="full").run
    if time.monotonic() >= deadline:
        raise ZenturePollingTimeoutError(
            operation_id=started.run_id,
            idempotency_key=saved_key,
            last_status=observed.run.status,
        )
    return full
