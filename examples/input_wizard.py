"""Run the input wizard helper.

Prints the operation ID and status by default. The optimized prompt is printed only with --show-prompt.
"""

from __future__ import annotations

import argparse

from zenture import ZentureClient
from zenture.idempotency import idempotency_key


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the zenture input wizard example.")
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="also print the optimized prompt text (default: operation ID and status only)",
    )
    args = parser.parse_args([] if argv is None else argv)
    key = idempotency_key("example", "input-wizard", "v1")
    with ZentureClient.from_env() as client:
        result = client.input_wizard.run(
            prompt="Improve this prompt for an internal support assistant.",
            idempotency_key=key,
            timeout=120.0,
        )
        print(result.operation_id, result.status)
        if args.show_prompt and result.result and result.result.optimized_prompt:
            print(result.result.optimized_prompt)


if __name__ == "__main__":
    main()
