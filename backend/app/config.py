from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://karam:karam@localhost:5432/karam"
    jwt_secret: str = "dev-insecure-change-me"
    jwt_exp_hours: int = 12
    # Provider id from agents/providers registry (default: anthropic).
    llm_provider: str = "anthropic"
    # Model id for the active provider (Anthropic: claude-haiku-5-5).
    llm_model: str = "claude-haiku-5-5"
    llm_timeout_sec: int = 120
    anthropic_api_key: str = ""
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me"
    cors_origins: str = "http://localhost,http://localhost:5173"
    cookie_secure: bool = False
    upload_dir: str = "./uploads"
    excel_import_path: str = ""
    document_expiry_path: str = ""
    container_tracker_path: str = ""
    testing: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
