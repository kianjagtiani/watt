import httpx


class WhatsAppClient:
    def __init__(self, token, phone_number_id,
                 base_url="https://graph.facebook.com/v23.0",
                 http: httpx.Client | None = None):
        self._base = base_url
        self._pnid = phone_number_id
        self._http = http or httpx.Client(timeout=30)
        self._headers = {"Authorization": f"Bearer {token}"}

    def _post_message(self, payload: dict) -> None:
        payload = {"messaging_product": "whatsapp", **payload}
        r = self._http.post(f"{self._base}/{self._pnid}/messages",
                            json=payload, headers=self._headers)
        r.raise_for_status()

    def send_text(self, to: str, body: str) -> None:
        self._post_message({"to": to, "type": "text", "text": {"body": body}})

    def send_template(self, to: str, name: str, params: list[str]) -> None:
        self._post_message({
            "to": to, "type": "template",
            "template": {
                "name": name,
                "language": {"code": "en_US"},
                "components": [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": p} for p in params],
                }],
            },
        })

    def download_media(self, media_id: str) -> tuple[bytes, str]:
        meta = self._http.get(f"{self._base}/{media_id}", headers=self._headers)
        meta.raise_for_status()
        info = meta.json()
        blob = self._http.get(info["url"], headers=self._headers)
        blob.raise_for_status()
        return blob.content, info["mime_type"]
