"""Runtime configuration models and environment-backed settings."""

import functools
import glob
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, Field, SecretStr, model_validator
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
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=env_files,
        extra="allow",
        hide_input_in_errors=True,
    )

    mongo_uri: SecretStr
    discord_key: SecretStr
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    destination_secret_key: SecretStr
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
    legacy_channel_alerts_enabled: bool = True
    max_requests_per_minute: float = 15.0
    worker_startup_stagger_seconds: float = 2.0
    log_level: str = "INFO"
    selenium_page_load_timeout_seconds: float = 25.0
    selenium_script_timeout_seconds: float = 20.0
    webhook_timeout_seconds: float = 10.0
    webhook_max_attempts: int = 3
    webhook_retry_backoff_seconds: float = 1.0
    driver_restart_after_searches: int = 150
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_cors_origins: list[str] = ["http://localhost:3000"]
    api_environment: Literal["development", "test", "production"] = "development"
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_token_lifetime_seconds: int = Field(default=3600, ge=60, le=86400)
    jwt_issuer: str = Field(default="mercari-bot-api", min_length=1, max_length=128)
    jwt_audience: str = Field(default="mercari-bot-dashboard", min_length=1, max_length=128)
    auth_cookie_name: str = Field(default="mercari_session", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    auth_cookie_secure: bool = False
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    marketplace_db_name: str | None = None
    listings_collection_name: str | None = None
    alerts_collection_name: str | None = None
    users_collection_name: str | None = None
    watchlists_collection_name: str | None = None
    destinations_collection_name: str | None = None
    keyword_registry_collection_name: str | None = None
    preset_keywords_collection_name: str | None = None
    mercari_db_name: str | None = None
    mercari_collection_name: str | None = None

    @model_validator(mode="after")
    def validate_authentication_settings(self) -> "Settings":
        """Reject authentication settings that would make session cookies unsafe."""
        if "*" in self.api_cors_origins:
            raise ValueError("API_CORS_ORIGINS cannot use a wildcard when credentials are enabled")
        if self.api_environment == "production" and not self.auth_cookie_secure:
            raise ValueError("AUTH_COOKIE_SECURE must be enabled in production")
        if self.auth_cookie_samesite == "none" and not self.auth_cookie_secure:
            raise ValueError("SameSite=None authentication cookies must be Secure")
        return self

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

    @property
    def mongo_destinations_collection_name(self) -> str:
        """Return the destinations collection name."""
        return self.destinations_collection_name or "destinations"

    @property
    def mongo_keyword_registry_collection_name(self) -> str:
        """Return the keyword registry collection name."""
        return self.keyword_registry_collection_name or "keyword_registry"

    @property
    def mongo_preset_keywords_collection_name(self) -> str:
        """Return the preset keyword catalog collection name."""
        return self.preset_keywords_collection_name or "preset_keywords"


settings = Settings()


@functools.cache
def get_legacy_app_config() -> AppConfig:
    """Load the legacy JSON keyword config on first use."""
    return AppConfig.from_json()
