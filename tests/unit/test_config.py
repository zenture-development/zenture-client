"""Configuration model behavior."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from zenture.config import ZentureConfig, load_config_from_env
from zenture.redaction import REDACTED

LIVE_CONFIG_KEY = "zt_" + "live_" + "config_123"
TEST_CONFIG_KEY = "zt_" + "test_" + "config_123"
TEST_CONFIG_ENV_KEY = "zt_" + "test_" + "config_env"
NON_PROD_OVERRIDE_ENV = "ZENTURE_SDK_ALLOW_NON_PROD_BASE_URL"
INT_API_BASE_URL = "https://api-int.zenture.app"


def _assert_validation_error_does_not_disclose_api_key(
    exc_info: pytest.ExceptionInfo[ValidationError],
    api_key: str,
) -> None:
    error = exc_info.value
    rendered_error = "\n".join(
        (
            str(error),
            repr(error),
            repr(error.errors()),
            error.json(),
        )
    )

    assert api_key not in rendered_error
    assert api_key[:12] not in rendered_error


def test_config_is_frozen_pydantic_model_and_redacts_api_key() -> None:
    config = ZentureConfig(api_key=LIVE_CONFIG_KEY)

    assert isinstance(config, BaseModel)
    assert config.base_url == "https://api.zenture.app"
    assert config.api_base_url == "https://api.zenture.app/v1"
    assert config.connect_timeout == 5.0
    assert config.read_timeout == 30.0
    assert config.write_timeout == 30.0
    assert config.pool_timeout == 30.0
    assert config.max_retries == 2
    assert config.initial_retry_backoff == 0.5
    assert config.max_retry_backoff == 8.0
    assert LIVE_CONFIG_KEY not in repr(config)
    assert REDACTED in repr(config)
    with pytest.raises(ValidationError):
        config.base_url = "http://localhost:8000"


def test_config_accepts_timeout_and_retry_overrides() -> None:
    config = ZentureConfig(
        api_key=LIVE_CONFIG_KEY,
        connect_timeout=1.0,
        read_timeout=2.0,
        write_timeout=3.0,
        pool_timeout=4.0,
        max_retries=4,
        initial_retry_backoff=0.2,
        max_retry_backoff=1.0,
    )

    assert config.connect_timeout == 1.0
    assert config.read_timeout == 2.0
    assert config.write_timeout == 3.0
    assert config.pool_timeout == 4.0
    assert config.max_retries == 4


def test_config_rejects_invalid_timeout_and_retry_policy() -> None:
    with pytest.raises(ValidationError):
        ZentureConfig(api_key=LIVE_CONFIG_KEY, connect_timeout=0.0)
    with pytest.raises(ValidationError):
        ZentureConfig(api_key=LIVE_CONFIG_KEY, max_retries=-1)
    with pytest.raises(ValidationError):
        ZentureConfig(
            api_key=LIVE_CONFIG_KEY,
            initial_retry_backoff=2.0,
            max_retry_backoff=1.0,
        )


def test_config_rejects_api_key_with_surrounding_whitespace() -> None:
    with pytest.raises(ValidationError):
        ZentureConfig(api_key=f" {TEST_CONFIG_KEY} ")


def test_live_token_defaults_to_production_and_rejects_non_production_origins() -> None:
    config = ZentureConfig(api_key=LIVE_CONFIG_KEY)

    assert config.base_url == "https://api.zenture.app"
    assert config.api_base_url == "https://api.zenture.app/v1"

    with pytest.raises(ValidationError, match="Live API tokens"):
        ZentureConfig(api_key=LIVE_CONFIG_KEY, base_url="https://api-example.zenture.app")

    with pytest.raises(ValidationError, match="Live API tokens"):
        ZentureConfig(api_key=LIVE_CONFIG_KEY, base_url="http://localhost:8000")


def test_test_token_requires_explicit_non_production_origin() -> None:
    with pytest.raises(ValidationError, match="Test API tokens require"):
        ZentureConfig(api_key=TEST_CONFIG_KEY)

    with pytest.raises(ValidationError, match="Test API tokens cannot"):
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url="https://api.zenture.app")


def test_config_validation_errors_do_not_disclose_api_key_fragments() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url=INT_API_BASE_URL)

    _assert_validation_error_does_not_disclose_api_key(exc_info, TEST_CONFIG_KEY)


def test_field_validation_errors_do_not_disclose_api_key_fragments() -> None:
    invalid_api_key = f" {TEST_CONFIG_KEY} "

    with pytest.raises(ValidationError) as exc_info:
        ZentureConfig(api_key=invalid_api_key)

    _assert_validation_error_does_not_disclose_api_key(exc_info, TEST_CONFIG_KEY)


def test_test_token_accepts_local_non_production_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError):
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url="http://localhost:8000")

    monkeypatch.setenv(NON_PROD_OVERRIDE_ENV, "1")
    local = ZentureConfig(
        api_key=TEST_CONFIG_KEY,
        base_url="http://localhost:8000",
    )

    assert local.api_base_url == "http://localhost:8000/v1"

    with pytest.raises(ValidationError):
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url="https://www.zenture.app")


def test_test_token_accepts_int_origin_only_with_non_production_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError):
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url=INT_API_BASE_URL)

    monkeypatch.setenv(NON_PROD_OVERRIDE_ENV, "1")
    config = ZentureConfig(api_key=TEST_CONFIG_KEY, base_url=INT_API_BASE_URL)

    assert config.api_base_url == f"{INT_API_BASE_URL}/v1"


def test_live_token_rejects_int_origin_even_with_non_production_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(NON_PROD_OVERRIDE_ENV, "1")

    with pytest.raises(ValidationError, match="Live API tokens"):
        ZentureConfig(api_key=LIVE_CONFIG_KEY, base_url=INT_API_BASE_URL)


def test_config_rejects_unknown_api_token_prefix() -> None:
    with pytest.raises(ValidationError, match="api_key must start"):
        ZentureConfig(api_key="zt_preview_config_123")


def test_base_url_validation_errors_do_not_disclose_internal_origins() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url="https://evil.example")

    message = str(exc_info.value)
    assert "api-example" not in message
    assert "localhost:8000" not in message


def test_config_accepts_only_approved_non_production_and_local_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(NON_PROD_OVERRIDE_ENV, "1")
    config = ZentureConfig(api_key=TEST_CONFIG_KEY, base_url="http://localhost:8000")

    assert config.base_url == "http://localhost:8000"

    int_config = ZentureConfig(api_key=TEST_CONFIG_KEY, base_url=INT_API_BASE_URL)

    assert int_config.base_url == INT_API_BASE_URL

    with pytest.raises(ValidationError):
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url="https://api.zenture.app/v1")

    with pytest.raises(ValidationError):
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url="https://api-example.zenture.app/")

    with pytest.raises(ValidationError):
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url="https://evil.example")

    with pytest.raises(ValidationError):
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url="https://api-unknown.zenture.app")


def test_config_rejects_base_url_credentials_even_for_local_debugging() -> None:
    with pytest.raises(ValidationError):
        ZentureConfig(
            api_key=TEST_CONFIG_KEY,
            base_url="http://user:password@localhost:8000",
        )


def test_config_allows_local_http_only_for_local_debugging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError):
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url="http://localhost:8000")

    monkeypatch.setenv(NON_PROD_OVERRIDE_ENV, "1")
    assert (
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url="http://localhost:8000").api_base_url
        == "http://localhost:8000/v1"
    )

    with pytest.raises(ValidationError):
        ZentureConfig(api_key=TEST_CONFIG_KEY, base_url="http://example.com")


def test_load_config_from_env_reads_api_key_and_optional_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZENTURE_API_KEY", TEST_CONFIG_ENV_KEY)
    monkeypatch.setenv("ZENTURE_BASE_URL", INT_API_BASE_URL)
    monkeypatch.setenv(NON_PROD_OVERRIDE_ENV, "1")

    config = load_config_from_env()

    assert config.api_key_value == TEST_CONFIG_ENV_KEY
    assert config.base_url == INT_API_BASE_URL


def test_load_config_from_env_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZENTURE_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ZENTURE_API_KEY"):
        load_config_from_env()
