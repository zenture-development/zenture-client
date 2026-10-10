"""Configuration for zenture SDK runtime primitives."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Self, cast
from urllib.parse import urlsplit, urlunsplit

from pydantic import (
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    field_validator,
    model_validator,
)

from zenture.models import SDKBaseModel
from zenture.redaction import REDACTED

if TYPE_CHECKING:
    from pydantic_core import InitErrorDetails

DEFAULT_BASE_URL = "https://api.zenture.app"
API_VERSION_PATH = "/v1"
DEFAULT_CONNECT_TIMEOUT = 5.0
DEFAULT_READ_TIMEOUT = 30.0
DEFAULT_WRITE_TIMEOUT = 30.0
DEFAULT_POOL_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_INITIAL_RETRY_BACKOFF = 0.5
DEFAULT_MAX_RETRY_BACKOFF = 8.0
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_APPROVED_NON_PRODUCTION_ORIGINS = frozenset({"https://api-int.zenture.app"})
_ALLOW_NON_PRODUCTION_BASE_URL_ENV = "ZENTURE_SDK_ALLOW_NON_PROD_BASE_URL"
_LIVE_TOKEN_PREFIX = "zt_live_"
_TEST_TOKEN_PREFIX = "zt_test_"


def _redact_validation_error(error: ValidationError) -> ValidationError:
    """Remove validated input values from a config validation error."""

    line_errors = [
        cast("InitErrorDetails", {**line_error, "input": REDACTED})
        for line_error in error.errors(include_context=True)
    ]
    return ValidationError.from_exception_data(error.title, line_errors)


class ZentureConfig(SDKBaseModel):
    """Validated SDK configuration."""

    model_config = ConfigDict(hide_input_in_errors=True)

    api_key: str = Field(repr=False)
    base_url: str = DEFAULT_BASE_URL
    connect_timeout: float = Field(default=DEFAULT_CONNECT_TIMEOUT, gt=0)
    read_timeout: float = Field(default=DEFAULT_READ_TIMEOUT, gt=0)
    write_timeout: float = Field(default=DEFAULT_WRITE_TIMEOUT, gt=0)
    pool_timeout: float = Field(default=DEFAULT_POOL_TIMEOUT, gt=0)
    max_retries: int = Field(default=DEFAULT_MAX_RETRIES, ge=0, le=10)
    initial_retry_backoff: float = Field(default=DEFAULT_INITIAL_RETRY_BACKOFF, ge=0)
    max_retry_backoff: float = Field(default=DEFAULT_MAX_RETRY_BACKOFF, ge=0)

    def __init__(self, **data: Any) -> None:
        sanitized_error: ValidationError | None = None
        try:
            super().__init__(**data)
        except ValidationError as error:
            sanitized_error = _redact_validation_error(error)

        if sanitized_error is not None:
            raise sanitized_error

    @field_validator("api_key", mode="before")
    @classmethod
    def _validate_api_key(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("api_key must not be empty.")
        if value != value.strip():
            raise ValueError("api_key must not include surrounding whitespace.")
        if not value.startswith((_LIVE_TOKEN_PREFIX, _TEST_TOKEN_PREFIX)):
            raise ValueError("api_key must start with zt_live_ or zt_test_.")
        return value

    @field_validator("base_url", mode="before")
    @classmethod
    def _validate_base_url(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("base_url must not be empty.")

        parsed = urlsplit(value.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("base_url must use http or https.")
        if not parsed.netloc:
            raise ValueError("base_url must include a host.")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("base_url must not include credentials.")
        if parsed.query or parsed.fragment:
            raise ValueError("base_url must not include query strings or fragments.")

        hostname = parsed.hostname or ""
        is_local = hostname in _LOCAL_HOSTS
        if parsed.scheme == "http" and not is_local:
            raise ValueError("http base_url is allowed only for local debugging.")

        path = parsed.path.rstrip("/")
        if path:
            raise ValueError("base_url must be an origin without a path.")

        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "", "", ""))

    @model_validator(mode="after")
    def _validate_environment_and_retry_policy(self) -> Self:
        base_url_was_provided = "base_url" in self.model_fields_set
        is_live_token = self.api_key.startswith(_LIVE_TOKEN_PREFIX)
        is_test_token = self.api_key.startswith(_TEST_TOKEN_PREFIX)

        if is_live_token and self.base_url != DEFAULT_BASE_URL:
            raise ValueError("Live API tokens can only be used with the production zenture API.")

        if is_test_token:
            if not base_url_was_provided:
                raise ValueError("Test API tokens require an approved non-production API base URL.")
            if self.base_url == DEFAULT_BASE_URL:
                raise ValueError("Test API tokens cannot be used with the production zenture API.")
            if not _is_approved_non_production_origin(self.base_url):
                raise ValueError(
                    "base_url must be an approved non-production zenture API origin "
                    "or a local debugging origin."
                )

        if self.max_retry_backoff < self.initial_retry_backoff:
            raise ValueError(
                "max_retry_backoff must be greater than or equal to initial_retry_backoff."
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def api_base_url(self) -> str:
        """Versioned public API base URL."""

        return f"{self.base_url}{API_VERSION_PATH}"

    @property
    def api_key_value(self) -> str:
        """Raw API key for Authorization headers."""

        return self.api_key

    def __repr__(self) -> str:
        return f"ZentureConfig(api_key='{REDACTED}', base_url={self.base_url!r})"

    def __str__(self) -> str:
        return repr(self)

    @classmethod
    def from_env(cls) -> ZentureConfig:
        """Load config from supported environment variables."""

        return load_config_from_env()


def load_config_from_env() -> ZentureConfig:
    """Load SDK config from environment variables."""

    api_key = os.environ.get("ZENTURE_API_KEY")
    if api_key is None or not api_key.strip():
        raise RuntimeError("ZENTURE_API_KEY is required.")

    base_url = os.environ.get("ZENTURE_BASE_URL", DEFAULT_BASE_URL)
    return ZentureConfig(api_key=api_key, base_url=base_url)


def _is_approved_non_production_origin(base_url: str) -> bool:
    if os.environ.get(_ALLOW_NON_PRODUCTION_BASE_URL_ENV) != "1":
        return False

    parsed = urlsplit(base_url)
    hostname = parsed.hostname or ""
    if hostname in _LOCAL_HOSTS:
        return True
    return base_url in _APPROVED_NON_PRODUCTION_ORIGINS
