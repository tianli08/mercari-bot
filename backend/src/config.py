"""Runtime configuration models and environment-backed settings."""

import base64
import functools
import glob
from pathlib import Path
from typing import ClassVar, Literal
from urllib.parse import urlsplit

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
        ".env.clerk",
        "channel_id.env",
    ]
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=env_files,
        extra="ignore",
        hide_input_in_errors=True,
    )

    mongo_uri: SecretStr
    discord_key: SecretStr
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    destination_secret_key: SecretStr
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
    clerk_secret_key: SecretStr | None = None
    clerk_publishable_key: str | None = None
    clerk_jwt_key: str | None = None
    clerk_authorized_parties: list[str] = ["http://localhost:3000"]
    # Keyword cap: read only through ``resolve_tenant_limits`` (see src/limits.py).
    max_keywords_per_user: int = Field(default=100, ge=1, le=10000)
    max_keywords_per_request: int = Field(default=50, ge=1, le=10000)
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
        """Reject browser origins that would weaken session validation."""
        for origins in (self.api_cors_origins, self.clerk_authorized_parties):
            if not origins or "*" in origins:
                raise ValueError("Authentication origins must be an explicit, non-empty allowlist")
            for origin in origins:
                parsed = urlsplit(origin)
                if (
                    parsed.scheme not in {"http", "https"}
                    or not parsed.netloc
                    or parsed.path
                    or parsed.query
                    or parsed.fragment
                    or parsed.username
                    or parsed.password
                    or (self.api_environment == "production" and parsed.scheme != "https")
                ):
                    raise ValueError("Authentication origins must be HTTP(S) origins; production requires HTTPS")
        return self

    @model_validator(mode="after")
    def validate_limit_settings(self) -> "Settings":
        """Reject request-shape bounds that the per-user keyword cap could never admit."""
        if self.max_keywords_per_request > self.max_keywords_per_user:
            raise ValueError("MAX_KEYWORDS_PER_REQUEST must be less than or equal to MAX_KEYWORDS_PER_USER")
        return self

    @property
    def clerk_issuer(self) -> str | None:
        """Derive the trusted issuer from the configured publishable key."""
        if not self.clerk_publishable_key:
            return None
        try:
            encoded = self.clerk_publishable_key.split("_", 2)[2]
            host = base64.b64decode(encoded + "=" * (-len(encoded) % 4), validate=True).decode().removesuffix("$")
            parsed = urlsplit(f"https://{host}")
            if not host or parsed.hostname != host or parsed.port or parsed.path or parsed.query or parsed.fragment:
                raise ValueError
        except (ValueError, IndexError, UnicodeError) as exc:
            raise ValueError("Invalid CLERK_PUBLISHABLE_KEY") from exc
        return f"https://{host}"

    def validate_clerk_configuration(self) -> None:
        """Fail API startup clearly while allowing the background worker to run independently."""
        if not self.clerk_secret_key or not self.clerk_secret_key.get_secret_value().strip():
            raise ValueError("CLERK_SECRET_KEY is required for the API")
        if not self.clerk_issuer:
            raise ValueError("CLERK_PUBLISHABLE_KEY is required for the API")

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
