from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MAILPULSE_",
        extra="ignore",
    )

    app_name: str = "MailPulse"
    version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
