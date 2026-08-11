"""Secret-safe Discord webhook transport exceptions."""

from __future__ import annotations


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
