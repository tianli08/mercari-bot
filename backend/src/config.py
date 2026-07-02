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
    channel_id: str | None = None
    channel_id_env: str | None = None


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
        "channel_id.env",
    ]
    model_config = SettingsConfigDict(env_nested_delimiter="__", env_file=env_files, extra="allow")

    mongo_uri: SecretStr
    discord_key: SecretStr
    designer_webhook: str
    designer_channel_id: str
    saved_channel_id: str
    mihara_channel_id: str | None = None
    carol_christian_poell_channel_id: str | None = None
    jean_paul_gaultier_channel_id: str | None = None
    the_soloist_channel_id: str | None = None
    fourteenth_addiction_channel_id: str | None = None
    rick_owens_channel_id: str | None = None
    ann_demeulemeester_channel_id: str | None = None
    attachment_channel_id: str | None = None
    boris_bidjan_saberi_channel_id: str | None = None
    dior_homme_channel_id: str | None = None
    isamu_katayama_backlash_channel_id: str | None = None
    julius_7_channel_id: str | None = None
    kapital_channel_id: str | None = None
    lad_musician_channel_id: str | None = None
    maison_margiela_channel_id: str | None = None
    number_nine_channel_id: str | None = None
    saint_laurent_paris_channel_id: str | None = None
    tornado_mart_channel_id: str | None = None
    undercover_channel_id: str | None = None
    a_and_g_rock_n_roll_couture_channel_id: str | None = None
    raf_simons_channel_id: str | None = None
    query_interval_min_seconds: float = 10.0
    query_interval_max_seconds: float = 20.0
    worker_pool_size: int = 2
    cycle_pause_seconds: float = 5.0
    send_initial_items: bool = False
    max_requests_per_minute: float = 15.0
    worker_startup_stagger_seconds: float = 2.0
    log_level: str = "INFO"
    selenium_page_load_timeout_seconds: float = 25.0
    selenium_script_timeout_seconds: float = 20.0
    driver_restart_after_searches: int = 150
    marketplace_db_name: str | None = None
    listings_collection_name: str | None = None
    alerts_collection_name: str | None = None
    users_collection_name: str | None = None
    watchlists_collection_name: str | None = None
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

    @property
    def mongo_users_collection_name(self) -> str:
        """Return the users collection name."""
        return self.users_collection_name or "users"

    @property
    def mongo_watchlists_collection_name(self) -> str:
        """Return the watchlists collection name."""
        return self.watchlists_collection_name or "watchlists"


settings = Settings()
app_config = AppConfig.from_json()
