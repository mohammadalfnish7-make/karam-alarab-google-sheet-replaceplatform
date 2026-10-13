from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://karam:karam@localhost:5432/karam"
    jwt_secret: str = "dev-insecure-change-me"
    jwt_exp_hours: int = 12
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me"
    cors_origins: str = "http://localhost,http://localhost:5173"
    cookie_secure: bool = False
    upload_dir: str = "./uploads"
    excel_import_path: str = ""
    testing: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
