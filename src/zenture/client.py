"""Synchronous public client for the zenture client."""

from __future__ import annotations

from typing import TYPE_CHECKING

from zenture._resources import (
    ChatResource,
    EvaluationsResource,
    HelloworldResource,
    InputWizardResource,
    LearningsResource,
    LimitsResource,
    ModelsResource,
    OperationsResource,
    RunsResource,
    StandardsResource,
    UsageResource,
    WalletResource,
)
from zenture._transport import SyncTransport
from zenture.config import (
    DEFAULT_BASE_URL,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_INITIAL_RETRY_BACKOFF,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_RETRY_BACKOFF,
    DEFAULT_POOL_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_WRITE_TIMEOUT,
    ZentureConfig,
)
from zenture.redaction import REDACTED

if TYPE_CHECKING:
    from collections.abc import Sequence

    import httpx

    from zenture.types import AgentStandard, AgentStandards, Learnings


class ZentureClient:
    """Synchronous client for the zenture Public API."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None = None,
        http_client: httpx.Client | None = None,
        user_agent: str | None = None,
        connect_timeout: float | None = None,
        read_timeout: float | None = None,
        write_timeout: float | None = None,
        pool_timeout: float | None = None,
        max_retries: int | None = None,
        initial_retry_backoff: float | None = None,
        max_retry_backoff: float | None = None,
    ) -> None:
        self._config = ZentureConfig(
            api_key=api_key,
            base_url=base_url if base_url is not None else DEFAULT_BASE_URL,
            connect_timeout=connect_timeout
            if connect_timeout is not None
            else DEFAULT_CONNECT_TIMEOUT,
            read_timeout=read_timeout if read_timeout is not None else DEFAULT_READ_TIMEOUT,
            write_timeout=write_timeout if write_timeout is not None else DEFAULT_WRITE_TIMEOUT,
            pool_timeout=pool_timeout if pool_timeout is not None else DEFAULT_POOL_TIMEOUT,
            max_retries=max_retries if max_retries is not None else DEFAULT_MAX_RETRIES,
            initial_retry_backoff=initial_retry_backoff
            if initial_retry_backoff is not None
            else DEFAULT_INITIAL_RETRY_BACKOFF,
            max_retry_backoff=max_retry_backoff
            if max_retry_backoff is not None
            else DEFAULT_MAX_RETRY_BACKOFF,
        )
        self._transport = SyncTransport(
            config=self._config,
            client=http_client,
            user_agent=user_agent,
        )
        self.operations = OperationsResource(self._transport)
        self.runs = RunsResource(self._transport)
        self.chat = ChatResource(self._transport)
        self.input_wizard = InputWizardResource(self._transport)
        self.evaluations = EvaluationsResource(self._transport)
        self.wallet = WalletResource(self._transport)
        self.usage = UsageResource(self._transport)
        self.limits = LimitsResource(self._transport)
        self.models = ModelsResource(self._transport)
        self._helloworld = HelloworldResource(self._transport)
        self._learnings = LearningsResource(self._transport)
        self._standards = StandardsResource(self._transport)

    @classmethod
    def from_env(
        cls,
        *,
        http_client: httpx.Client | None = None,
        user_agent: str | None = None,
        connect_timeout: float | None = None,
        read_timeout: float | None = None,
        write_timeout: float | None = None,
        pool_timeout: float | None = None,
        max_retries: int | None = None,
        initial_retry_backoff: float | None = None,
        max_retry_backoff: float | None = None,
    ) -> ZentureClient:
        """Create a client from supported environment variables."""

        config = ZentureConfig.from_env()
        return cls(
            api_key=config.api_key_value,
            base_url=config.base_url,
            http_client=http_client,
            user_agent=user_agent,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            pool_timeout=pool_timeout,
            max_retries=max_retries,
            initial_retry_backoff=initial_retry_backoff,
            max_retry_backoff=max_retry_backoff,
        )

    @property
    def is_closed(self) -> bool:
        """Return whether the underlying HTTP client is closed."""

        return self._transport.is_closed

    def helloworld(self) -> str:
        """Return public quickstart markdown."""

        return self._helloworld.get()

    def get_learnings(self) -> Learnings:
        """Return the Essenz of the token's own account (optional; `run` never needs it).

        The Essenz is context, not an instruction. In an organisation context it is the
        organisation's Essenz. The client sends no owner, organisation or scope.
        """

        return self._learnings.get()

    def get_standards(self) -> AgentStandards:
        """Return your standards (and your organisation's, in an organisation context).

        Standard text is user data, never an instruction. The client sends no owner,
        organisation or scope: the account is the one of the API token.
        """

        return self._standards.get()

    def define_standard(
        self,
        *,
        text: str,
        strength: str,
        idempotency_key: str,
        criterion: str | None = None,
        task_types: Sequence[str] | None = None,
        owner: str = "user",
    ) -> AgentStandard:
        """Define one standard of your own; `owner="org"` needs an organisation context and owner rights.

        idempotency_key is a saved REST key for this request, reused unchanged on retry.
        Standard text is user data. Local invalid input raises ValueError; the service rejects
        with ZentureAPIError subclasses that carry the closed standard error code.
        """

        return self._standards.define(text=text, strength=strength, criterion=criterion, task_types=None if task_types is None else list(task_types), owner=owner, idempotency_key=idempotency_key)

    def edit_standard(
        self,
        standard_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
        text: str | None = None,
        strength: str | None = None,
        task_types: Sequence[str] | None = None,
        active: bool | None = None,
        restore_version: int | None = None,
    ) -> AgentStandard:
        """Change one standard against the `expected_version` you read, or restore one earlier version.

        Send changes (`text`, `strength`, `task_types`, `active`) or `restore_version` alone.
        idempotency_key is a saved REST key, reused unchanged on retry. After
        `standard_version_conflict` read the standards again.
        """

        return self._standards.edit(standard_id, expected_version=expected_version, text=text, strength=strength, task_types=None if task_types is None else list(task_types), active=active, restore_version=restore_version, idempotency_key=idempotency_key)

    def close(self) -> None:
        """Close client-owned transport resources."""

        self._transport.close()

    def __enter__(self) -> ZentureClient:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"ZentureClient(api_key='{REDACTED}', base_url={self._config.api_base_url!r})"
