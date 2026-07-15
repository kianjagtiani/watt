import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    whatsapp_token: str
    phone_number_id: str
    verify_token: str
    gemini_api_key: str
    gemini_model: str
    reminder_template: str
    admin_phone: str
    db_path: str
    default_tz: str


def load_settings() -> Settings:
    e = os.environ.get
    return Settings(
        whatsapp_token=e("WHATSAPP_TOKEN", ""),
        phone_number_id=e("WHATSAPP_PHONE_NUMBER_ID", ""),
        verify_token=e("WEBHOOK_VERIFY_TOKEN", ""),
        gemini_api_key=e("GEMINI_API_KEY", ""),
        gemini_model=e("GEMINI_MODEL", "gemini-2.5-flash"),
        reminder_template=e("WHATSAPP_REMINDER_TEMPLATE", "task_reminder"),
        admin_phone=e("ADMIN_PHONE", ""),
        db_path=e("DB_PATH", "assistant.db"),
        default_tz=e("DEFAULT_TIMEZONE", "America/Los_Angeles"),
    )
