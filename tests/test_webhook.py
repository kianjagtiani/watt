from fastapi.testclient import TestClient

from assistant.config import Settings
from assistant.db import connect
from assistant.store import users
from assistant.webhook import create_app

SETTINGS = Settings("", "PNID", "sekrit", "", "gemini-2.5-flash",
                    "task_reminder", "1555", ":memory:", "America/Los_Angeles")


class FakeWA:
    def __init__(self):
        self.sent = []

    def send_text(self, to, body):
        self.sent.append((to, body))

    def download_media(self, media_id):
        return b"img", "image/jpeg"


def _payload(msg):
    return {"entry": [{"changes": [{"value": {"messages": [msg]}}]}]}


def _text_msg(mid="wamid.1", frm="1555", body="hello"):
    return {"id": mid, "from": frm, "type": "text", "text": {"body": body}}


def _setup():
    conn = connect(":memory:")
    users.add_user(conn, "1555", name="Kian", is_admin=True)
    wa = FakeWA()
    handled = []

    def handler(phone, text, image):
        handled.append((phone, text, image))
        return "reply!"

    app = create_app(SETTINGS, conn, wa, handler)
    return TestClient(app), wa, handled


def test_verify_handshake():
    client, _, _ = _setup()
    r = client.get("/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "sekrit",
        "hub.challenge": "42"})
    assert r.status_code == 200 and r.text == "42"
    r = client.get("/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "wrong",
        "hub.challenge": "42"})
    assert r.status_code == 403


def test_text_message_routed_and_replied():
    client, wa, handled = _setup()
    r = client.post("/webhook", json=_payload(_text_msg()))
    assert r.status_code == 200
    assert handled == [("1555", "hello", None)]
    assert wa.sent == [("1555", "reply!")]


def test_dedupe():
    client, wa, handled = _setup()
    client.post("/webhook", json=_payload(_text_msg(mid="wamid.same")))
    client.post("/webhook", json=_payload(_text_msg(mid="wamid.same")))
    assert len(handled) == 1


def test_unknown_sender_refused_once():
    client, wa, handled = _setup()
    client.post("/webhook", json=_payload(_text_msg(mid="a", frm="1999")))
    client.post("/webhook", json=_payload(_text_msg(mid="b", frm="1999")))
    assert handled == []
    assert len(wa.sent) == 1 and wa.sent[0][0] == "1999"


def test_image_message_downloads_media():
    client, wa, handled = _setup()
    msg = {"id": "wamid.img", "from": "1555", "type": "image",
           "image": {"id": "MEDIA1", "caption": "this job"}}
    client.post("/webhook", json=_payload(msg))
    assert handled == [("1555", "this job", (b"img", "image/jpeg"))]
