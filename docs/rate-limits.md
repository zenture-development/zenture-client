# Rate Limits

The public API can return `429` when a caller exceeds a rate limit. The client maps
that response to `ZentureRateLimitError` when the response is not retried by the
transport layer.

When the API includes `Retry-After`, the transport retry policy honors it before
falling back to deterministic exponential backoff. Retry delays are capped by
the client retry configuration.

## Retry Policy

Retryable HTTP responses include `429`, `500`, `502`, `503`, and `504` when the
public error code is retryable. Mutating requests are retried only when an
`Idempotency-Key` is present.

By default, network exceptions from `httpx.HTTPError` are mapped to
`ZentureTransportError` and are not classified for retry by this phase.

## Caller Guidance

For `ZentureRateLimitError`, inspect `exc.retry_after` when present and schedule
the next attempt after that delay. For operation polling, prefer resuming with
`operations.get(operation_id)` instead of recreating work.

For manual operation polling, use the same cadence as the client helpers:
`1s -> 2s -> 4s -> 8s`, then keep polling every `8s` until terminal status or
your local timeout. Do not poll an operation faster than once per second, and
always stop after `succeeded`, `failed`, `cancelled`, or `expired`.
