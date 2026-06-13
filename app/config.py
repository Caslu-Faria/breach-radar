"""Configurações da aplicação, carregadas de variáveis de ambiente / `.env`."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite://"
    hibp_api_url: str = "https://haveibeenpwned.com/api/v3/breaches"
    hibp_user_agent: str = "breach-radar-app (contato@example.com)"
    hibp_timeout_seconds: int = 10
    enable_scheduled_sync: bool = False
    sync_interval_minutes: int = 60


settings = Settings()
