"""Deliver listing alerts safely through Discord webhooks."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import aiohttp

from . import database
from .config import settings
from .destinations import DestinationRecord
from .discord_messages import build_listing_embed
from .listings import ListingRecord
from .logging_utils import ContextLoggerAdapter, get_logger, log_exception

webhook_logger = get_logger("webhook")


class WebhookDeliveryError(RuntimeError):
    """Raised when a Discord webhook delivery does not succeed."""

    def __init__(self, destination_id: str, reason: str, *, status: int | None = None) -> None:
        """Initialize an error containing no write-capable webhook secret."""
        self.destination_id = destination_id
        self.status = status
        status_text = f" (HTTP {status})" if status is not None else ""
        super().__init__(f"Webhook delivery failed for destination {destination_id}{status_text}: {reason}")


class WebhookPermanentError(WebhookDeliveryError):
    """Raised when a Discord webhook is missing or no longer authorized."""


class WebhookTransientError(WebhookDeliveryError):
    """Raised when bounded retries cannot recover webhook delivery."""


class _WebhookRateLimitError(WebhookTransientError):
    """Represent a retryable Discord rate limit response."""

    def __init__(self, destination_id: str, retry_after: float) -> None:
        super().__init__(destination_id, "rate limit retry budget exhausted", status=429)
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class DiscordWebhookSender:
    """Post listing embeds through Discord using a shared aiohttp session."""

    session: aiohttp.ClientSession
    timeout_seconds: float = settings.webhook_timeout_seconds
    max_attempts: int = settings.webhook_max_attempts
    retry_backoff_seconds: float = settings.webhook_retry_backoff_seconds
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    logger: ContextLoggerAdapter = webhook_logger

    async def __call__(self, destination: DestinationRecord, listing: ListingRecord) -> None:
        """Post one listing embed and stamp the destination after its first success."""
        destination_id = destination._id
        try:
            webhook_url = destination.webhook_url()
        except Exception:
            raise WebhookDeliveryError(destination_id, "webhook credentials could not be loaded") from None

        payload = {"embeds": [build_listing_embed(listing).to_dict()]}
        attempts = max(1, self.max_attempts)
        timeout = aiohttp.ClientTimeout(total=max(0.1, self.timeout_seconds))

        for attempt in range(1, attempts + 1):
            try:
                await self._post_once(
                    destination_id=destination_id,
                    webhook_url=webhook_url,
                    payload=payload,
                    timeout=timeout,
                )
            except _WebhookRateLimitError as exc:
                if attempt == attempts:
                    raise
                self.logger.warning(
                    "Discord webhook rate limited; retrying",
                    context={
                        "destination_id": destination_id,
                        "attempt": attempt,
                        "max_attempts": attempts,
                        "retry_after_seconds": exc.retry_after,
                    },
                )
                await self.sleep(exc.retry_after)
            except WebhookTransientError:
                if attempt == attempts:
                    raise
                backoff = max(0.0, self.retry_backoff_seconds) * attempt
                self.logger.warning(
                    "Transient Discord webhook failure; retrying",
                    context={
                        "destination_id": destination_id,
                        "attempt": attempt,
                        "max_attempts": attempts,
                        "retry_after_seconds": backoff,
                    },
                )
                await self.sleep(backoff)
            else:
                await self._stamp_verified(destination)
                return

    async def _post_once(
        self,
        *,
        destination_id: str,
        webhook_url: str,
        payload: dict[str, Any],
        timeout: aiohttp.ClientTimeout,
    ) -> None:
        try:
            async with self.session.post(
                webhook_url,
                json=payload,
                timeout=timeout,
                allow_redirects=False,
            ) as response:
                if 200 <= response.status < 300:
                    return
                if response.status == 429:
                    retry_after = await _read_retry_after(response, self.retry_backoff_seconds)
                    raise _WebhookRateLimitError(destination_id, retry_after)
                if response.status in {401, 403, 404}:
                    raise WebhookPermanentError(
                        destination_id,
                        "webhook is missing or unauthorized",
                        status=response.status,
                    )
                if response.status >= 500:
                    raise WebhookTransientError(
                        destination_id,
                        "Discord server error",
                        status=response.status,
                    )
                raise WebhookDeliveryError(
                    destination_id,
                    "Discord rejected the request",
                    status=response.status,
                )
        except WebhookDeliveryError:
            raise
        except (aiohttp.ClientError, TimeoutError):
            raise WebhookTransientError(destination_id, "HTTP transport error") from None

    async def _stamp_verified(self, destination: DestinationRecord) -> None:
        if destination.verified_at is not None:
            return
        try:
            await database.mark_destination_verified(destination._id, datetime.now(UTC))
        except Exception:
            safe_error = WebhookDeliveryError(
                destination._id,
                "destination verification stamp failed after a successful post",
            )
            log_exception(
                self.logger,
                "Webhook delivered but destination verification stamp failed",
                safe_error,
                destination_id=destination._id,
            )


async def _read_retry_after(response: aiohttp.ClientResponse, fallback: float) -> float:
    """Read a non-negative Discord retry delay without exposing response details."""
    retry_after: object | None = None
    try:
        body = await response.json(content_type=None)
        if isinstance(body, dict):
            retry_after = body.get("retry_after")
    except (aiohttp.ClientError, TypeError, ValueError):
        retry_after = None

    if retry_after is None:
        retry_after = response.headers.get("Retry-After")
    try:
        return max(0.0, float(retry_after))
    except (TypeError, ValueError):
        return max(0.0, fallback)
