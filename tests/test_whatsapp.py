import json

import httpx

from assistant.whatsapp import WhatsAppClient


def _client(handler):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return WhatsAppClient("tok", "PNID", http=http)


def test_send_text():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["Authorization"]
        seen["json"] = json.loads(req.content)
        return httpx.Response(200, json={"messages": [{"id": "x"}]})

    _client(handler).send_text("1555", "hi")
    assert seen["url"].endswith("/PNID/messages")
    assert seen["auth"] == "Bearer tok"
    assert seen["json"]["type"] == "text"
    assert seen["json"]["text"]["body"] == "hi"


def test_send_template():
    seen = {}

    def handler(req):
        seen["json"] = json.loads(req.content)
        return httpx.Response(200, json={})

    _client(handler).send_template("1555", "task_reminder", ["cancel Prime"])
    t = seen["json"]["template"]
    assert t["name"] == "task_reminder"
    assert t["components"][0]["parameters"][0]["text"] == "cancel Prime"


def test_download_media_two_step():
    def handler(req):
        if "MEDIAID" in str(req.url):
            return httpx.Response(200, json={
                "url": "https://cdn.example/file", "mime_type": "image/png"})
        return httpx.Response(200, content=b"bytes!")

    data, mime = _client(handler).download_media("MEDIAID")
    assert (data, mime) == (b"bytes!", "image/png")
