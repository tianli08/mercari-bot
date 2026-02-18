import glob
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class FilterConfig(BaseModel):
    name: str
    keywords: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    filters: list[FilterConfig] = Field(default_factory=list)

    DEFAULT_PATH: ClassVar[Path] = Path(__file__).parent.parent / "config" / "config.json"

    @classmethod
    def from_json(cls, path: str | Path | None = None) -> "AppConfig":
        config_path = Path(path) if path is not None else cls.DEFAULT_PATH
        data = config_path.read_text(encoding="utf-8")
        return cls.model_validate_json(data)


class Settings(BaseSettings):
    """Configuration settings for the program"""

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


settings = Settings()
app_config = AppConfig.from_json()
