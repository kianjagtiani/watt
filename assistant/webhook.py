import logging

from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from assistant.store import users

log = logging.getLogger(__name__)

REFUSAL = ("Hi! I'm a private assistant and can't chat with new numbers. "
           "Ask my admin for access if you know them 🙂")
UNSUPPORTED = "I can only handle text and images for now!"


def create_app(settings, conn, wa, handler) -> FastAPI:
    app = FastAPI()

    @app.get("/webhook")
    def verify(request: Request):
        q = request.query_params
        if (q.get("hub.mode") == "subscribe"
                and q.get("hub.verify_token") == settings.verify_token):
            return PlainTextResponse(q.get("hub.challenge", ""))
        return Response(status_code=403)

    def _process(phone, text, image):
        reply = handler(phone, text, image)
        wa.send_text(phone, reply)

    @app.post("/webhook")
    def receive(body: dict, background: BackgroundTasks):
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                for msg in change.get("value", {}).get("messages", []):
                    try:
                        _route(msg, background)
                    except Exception:
                        log.exception("failed to route message")
        return {"status": "ok"}

    def _route(msg, background):
        cur = conn.execute(
            "INSERT OR IGNORE INTO processed (message_id) VALUES (?)",
            (msg["id"],))
        conn.commit()
        if cur.rowcount == 0:
            return  # already seen (webhook retry)
        phone = msg["from"]
        if not users.is_allowed(conn, phone):
            if users.mark_refused(conn, phone):
                wa.send_text(phone, REFUSAL)
            return
        if msg["type"] == "text":
            background.add_task(_process, phone, msg["text"]["body"], None)
        elif msg["type"] == "image":
            image = wa.download_media(msg["image"]["id"])
            background.add_task(_process, phone,
                                msg["image"].get("caption"), image)
        else:
            wa.send_text(phone, UNSUPPORTED)

    return app
