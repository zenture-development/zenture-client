"""Retry decision policy for client transport and polling."""

from __future__ import annotations

from zenture.models import SDKBaseModel

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_RETRYABLE_ERROR_CODES = {
    "rate_limited",
    "dependency_unavailable",
    "capacity_unavailable",
    "internal_error",
}
_NON_RETRYABLE_ERROR_CODES = {
    "unauthorized",
    "forbidden",
    "validation_failed",
    "missing_idempotency_key",
    "idempotency_conflict",
    "operation_expired",
}


class RetryDecision(SDKBaseModel):
    """Result of applying the retry policy."""

    retry: bool
    reason: str


def should_retry(
    *,
    method: str,
    status_code: int | None,
    error_code: str | None,
    has_idempotency_key: bool,
    attempt: int,
    max_attempts: int,
) -> RetryDecision:
    """Return whether a request should be retried."""

    if attempt >= max_attempts:
        return RetryDecision(retry=False, reason="attempt_budget_exhausted")

    normalized_method = method.upper()
    if error_code in _NON_RETRYABLE_ERROR_CODES:
        return RetryDecision(retry=False, reason="non_retryable_error")

    is_retryable = status_code in _RETRYABLE_STATUS_CODES or error_code in _RETRYABLE_ERROR_CODES
    if not is_retryable:
        return RetryDecision(retry=False, reason="non_retryable_status")

    if normalized_method not in _SAFE_METHODS and not has_idempotency_key:
        return RetryDecision(retry=False, reason="missing_idempotency_key")

    return RetryDecision(retry=True, reason="retryable_status")
