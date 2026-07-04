from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Aurora HR"
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./aurora.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "development-only-change-me"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/oauth/google/callback"
    frontend_url: str = "http://localhost:3000"
    cookie_secure: bool = False
    openrouter_api_key: str = ""
    openrouter_model: str = "openrouter/auto"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    sender_mail_id: str = ""
    reliever_mail_id: str = "auto"
    ollama_host: str = "http://localhost:11434"
    ollama_model_id: str = "qwen2.5:3b"
    cors_origins: str = "http://localhost:3000"
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
