import mimetypes
import pathlib

from dotenv import load_dotenv

from assistant import agent, db
from assistant.config import load_settings
from assistant.llm import GeminiProvider
from assistant.store import users


def main():
    load_dotenv()
    settings = load_settings()
    conn = db.connect(settings.db_path)
    phone = settings.admin_phone or "10000000000"
    if not users.is_allowed(conn, phone):
        users.add_user(conn, phone, name="You", is_admin=True,
                       timezone_name=settings.default_tz)
    llm = GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    print("Chat with your assistant (img:<path> [caption] to send an image, quit to exit)")
    while True:
        line = input("you> ").strip()
        if line in {"quit", "exit"}:
            break
        text, image = line, None
        if line.startswith("img:"):
            rest = line[4:].split(maxsplit=1)
            if not rest or not pathlib.Path(rest[0]).is_file():
                print("can't read that image path")
                continue
            path = pathlib.Path(rest[0])
            text = rest[1] if len(rest) > 1 else None
            mime = mimetypes.guess_type(path.name)[0] or "image/png"
            image = (path.read_bytes(), mime)
        print("bot>", agent.handle_message(conn, settings, llm, phone,
                                           text=text, image=image))


if __name__ == "__main__":
    main()
