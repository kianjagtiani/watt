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
