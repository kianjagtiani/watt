import functools

import uvicorn
from dotenv import load_dotenv

from assistant import agent, db, scheduler
from assistant.config import load_settings
from assistant.llm import GeminiProvider
from assistant.store import users
from assistant.webhook import create_app
from assistant.whatsapp import WhatsAppClient


def main():
    load_dotenv()
    settings = load_settings()
    required = {
        "WHATSAPP_TOKEN": settings.whatsapp_token,
        "WHATSAPP_PHONE_NUMBER_ID": settings.phone_number_id,
        "WEBHOOK_VERIFY_TOKEN": settings.verify_token,
        "GEMINI_API_KEY": settings.gemini_api_key,
        "ADMIN_PHONE": settings.admin_phone,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
    conn = db.connect(settings.db_path)
    if settings.admin_phone and not users.is_allowed(conn, settings.admin_phone):
        users.add_user(conn, settings.admin_phone, name="Admin", is_admin=True,
                       timezone_name=settings.default_tz)
    llm = GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    wa = WhatsAppClient(settings.whatsapp_token, settings.phone_number_id)
    handler = functools.partial(agent.handle_message, conn, settings, llm)

    def handle(phone, text, image):
        return handler(phone, text=text, image=image)

    app = create_app(settings, conn, wa, handle)
    scheduler.start(conn, settings, wa)
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
