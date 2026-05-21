"""Application settings loaded from environment variables.

Settings use the ``MAILPULSE_`` prefix and optional ``.env`` file. Access
via :func:`get_settings` for a cached singleton.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the MailPulse HTTP service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MAILPULSE_",
        extra="ignore",
    )

    app_name: str = "MailPulse"
    version: str = "1.0.0"
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings.

    Returns:
        Parsed settings from the environment and optional ``.env`` file.
    """
    return Settings()
