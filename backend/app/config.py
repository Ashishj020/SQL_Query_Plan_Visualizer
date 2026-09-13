from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://planner:planner@127.0.0.1:5433/shop"
    statement_timeout_ms: int = 60_000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
