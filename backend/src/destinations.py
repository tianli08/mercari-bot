"""Tenant destination models, webhook validation, and encryption helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

from .config import settings

_DISCORD_WEBHOOK_HOSTS = {
    "discord.com",
    "discordapp.com",
    "ptb.discord.com",
    "ptb.discordapp.com",
    "canary.discord.com",
    "canary.discordapp.com",
}
_DISCORD_WEBHOOK_PATH_RE = re.compile(r"/api(?:/v\d+)?/webhooks/(?P<webhook_id>\d+)/(?P<token>[A-Za-z0-9._-]+)")


class DestinationType(StrEnum):
    """Supported alert delivery destination kinds."""

    DISCORD_WEBHOOK = "discord_webhook"


class DestinationLabelExistsError(Exception):
    """Raised when a destination label already exists for the same owner."""


class DestinationNotFoundError(Exception):
    """Raised when a destination cannot be found for an update."""


class InvalidWebhookUrlError(Exception):
    """Raised when a Discord webhook URL fails validation."""


@dataclass(slots=True)
class DestinationRecord:
    """Tenant-owned alert destination data stored in MongoDB."""

    _id: str
    owner_id: str
    type: DestinationType
    webhook_url_encrypted: str
    label: str
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def new(
        cls,
        *,
        owner_id: str,
        webhook_url: str,
        label: str,
        type: DestinationType | str = DestinationType.DISCORD_WEBHOOK,
        created_at: datetime | None = None,
    ) -> "DestinationRecord":
        """Create a new destination record with normalized fields, encryption, and timestamps."""
        timestamp = created_at or datetime.now(UTC)
        normalized_url = validate_webhook_url(webhook_url)
        return cls(
            _id=uuid4().hex,
            owner_id=owner_id,
            type=DestinationType(type),
            webhook_url_encrypted=encrypt_webhook_url(normalized_url),
            label=normalize_label(label),
            verified_at=None,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def to_document(self) -> dict[str, Any]:
        """Serialize the destination for MongoDB storage."""
        return {
            "_id": self._id,
            "owner_id": self.owner_id,
            "type": self.type.value,
            "webhook_url_encrypted": self.webhook_url_encrypted,
            "label": self.label,
            "verified_at": self.verified_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def webhook_url(self) -> str:
        """Return the plaintext webhook URL.

        The return value is a write-capable secret and must never be logged, printed, or serialized.
        """
        return decrypt_webhook_url(self.webhook_url_encrypted)


def normalize_label(label: str) -> str:
    """Normalize a destination label and ensure it is non-empty."""
    normalized_label = label.strip()
    if not normalized_label:
        raise ValueError("destination label must be non-empty")
    return normalized_label


def validate_webhook_url(url: str) -> str:
    """Validate and normalize a Discord webhook URL."""
    normalized_url = url.strip()
    if not normalized_url:
        raise InvalidWebhookUrlError("webhook URL must be non-empty")

    parsed = urlparse(normalized_url)
    if parsed.scheme != "https":
        raise InvalidWebhookUrlError("webhook URL must use HTTPS")

    if parsed.hostname not in _DISCORD_WEBHOOK_HOSTS:
        raise InvalidWebhookUrlError("webhook URL host must be discord.com, discordapp.com, or a ptb/canary subdomain")

    try:
        port = parsed.port
    except ValueError as exc:
        raise InvalidWebhookUrlError("webhook URL port is invalid") from exc
    if port is not None or parsed.username is not None or parsed.password is not None:
        raise InvalidWebhookUrlError("webhook URL authority must contain only a Discord host")

    if parsed.query or parsed.fragment:
        raise InvalidWebhookUrlError("webhook URL must not include query parameters or fragments")

    if _DISCORD_WEBHOOK_PATH_RE.fullmatch(parsed.path) is None:
        raise InvalidWebhookUrlError("webhook URL path must match /api(/vN)/webhooks/<id>/<token>")

    return normalized_url


def encrypt_webhook_url(plaintext: str) -> str:
    """Encrypt a plaintext webhook URL for storage."""
    return _destination_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_webhook_url(ciphertext: str) -> str:
    """Decrypt a stored webhook URL ciphertext."""
    try:
        plaintext = _destination_fernet().decrypt(ciphertext.encode("utf-8"))
    except InvalidToken as exc:
        raise InvalidToken("destination webhook URL could not be decrypted") from exc
    return plaintext.decode("utf-8")


def _destination_fernet() -> Fernet:
    return Fernet(settings.destination_secret_key.get_secret_value().encode("utf-8"))
