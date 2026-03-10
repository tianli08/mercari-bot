"""Runtime configuration models and environment-backed settings."""

import glob
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class FilterConfig(BaseModel):
    """Static keyword group loaded from JSON."""

    name: str
    keywords: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    """Top-level application config loaded from disk."""

    filters: list[FilterConfig] = Field(default_factory=list)

    DEFAULT_PATH: ClassVar[Path] = Path(__file__).parent.parent / "config" / "config.json"

    @classmethod
    def from_json(cls, path: str | Path | None = None) -> "AppConfig":
        """Load application config from a JSON file."""
        config_path = Path(path) if path is not None else cls.DEFAULT_PATH
        data = config_path.read_text(encoding="utf-8")
        return cls.model_validate_json(data)


class Settings(BaseSettings):
    """Environment-backed runtime settings."""

    env_files: ClassVar[list[str]] = glob.glob("/etc/config/*.env") + [
        ".env",
        ".env.local",
    ]
    model_config = SettingsConfigDict(env_nested_delimiter="__", env_file=env_files, extra="allow")

    mongo_uri: SecretStr
    discord_key: SecretStr
    designer_webhook: str
    designer_channel_id: str
    saved_channel_id: str
    marketplace_db_name: str | None = None
    listings_collection_name: str | None = None
    alerts_collection_name: str | None = None
    mercari_db_name: str | None = None
    mercari_collection_name: str | None = None

    @property
    def mongo_database_name(self) -> str:
        """Return the configured MongoDB database name."""
        return self.marketplace_db_name or self.mercari_db_name or "marketplace_monitor"

    @property
    def mongo_listings_collection_name(self) -> str:
        """Return the primary listings collection name."""
        return self.listings_collection_name or self.mercari_collection_name or "marketplace_listings"

    @property
    def mongo_alerts_collection_name(self) -> str:
        """Return the alert delivery collection name."""
        return self.alerts_collection_name or "listing_alerts"


settings = Settings()
app_config = AppConfig.from_json()
