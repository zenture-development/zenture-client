"""Redaction behavior for client safety surfaces."""

from __future__ import annotations

from zenture.redaction import REDACTED, redact_headers, redact_text


def test_redact_text_replaces_public_api_token_patterns() -> None:
    token = "zt_" + "live_" + "abc123SECRET"

    redacted = redact_text(f"Authorization failed for {token}")

    assert token not in redacted
    assert redacted == f"Authorization failed for {REDACTED}"


def test_redact_headers_redacts_sensitive_header_values_case_insensitively() -> None:
    token = "zt_" + "live_" + "abc123SECRET"

    redacted = redact_headers(
        {
            "Authorization": f"Bearer {token}",
            "x-api-key": token,
            "Content-Type": "application/json",
        }
    )

    assert redacted == {
        "Authorization": REDACTED,
        "x-api-key": REDACTED,
        "Content-Type": "application/json",
    }


def test_redact_headers_redacts_token_patterns_in_other_safe_headers() -> None:
    token = "zt_" + "test_" + "abc123SECRET"

    redacted = redact_headers({"X-Request-Note": f"token={token}"})

    assert redacted["X-Request-Note"] == f"token={REDACTED}"
