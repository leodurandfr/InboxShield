from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://inboxshield:changeme@localhost:5432/inboxshield"

    # Encryption key for IMAP credentials (Fernet)
    encryption_key: str = ""

    # Ollama (default LLM provider)
    ollama_base_url: str = "http://localhost:11434"

    # Cloud LLM API keys (optional)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    mistral_api_key: str = ""

    # App
    app_name: str = "InboxShield"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]


settings = AppSettings()
