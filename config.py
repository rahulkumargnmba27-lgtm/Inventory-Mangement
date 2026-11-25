from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./kirana.db"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    jwt_secret_key: str = "kirana-quick-dev-secret-change-in-production-2026"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_recipient_phone: str = "919876543210"
    whatsapp_api_version: str = "v20.0"

    n8n_webhook_secret: str = "kirana-n8n-shared-secret"
    n8n_alert_webhook_url: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_webhook_secret: str = "kirana-telegram-secret"
    telegram_polling_enabled: bool = False

    store_name: str = "Gupta Brothers Kirana"
    store_location: str = "Indiranagar, Bengaluru"
    store_phone: str = "+91 98450 12345"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
