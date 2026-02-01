"""Configuration management for vibecheck."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # GitHub (for OAuth and API)
    github_client_id: str = ""
    github_client_secret: str = ""
    github_token: str = ""  # For fetching repo stats

    # App
    app_name: str = "vibecheck"
    app_url: str = "https://vibecheck.ito.com"
    debug: bool = False

    # API
    api_prefix: str = "/api/v1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
