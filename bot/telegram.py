"""Мінімальний клієнт Telegram Bot API без зовнішніх залежностей."""
import json
import os
import time
import urllib.error
import urllib.request
import uuid

API = os.environ.get("TELEGRAM_API", "https://api.telegram.org")


class TelegramError(Exception):
    def __init__(self, data):
        super().__init__(data.get("description", str(data)))
        self.data = data
        self.code = data.get("error_code")


def call(token: str, method: str, fields: dict = None, files: dict = None, _retry: bool = True):
    boundary = uuid.uuid4().hex
    body = bytearray()
    for k, v in (fields or {}).items():
        if v is None:
            continue
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n').encode()
        body += str(v).encode("utf-8") + b"\r\n"
    for k, (fname, data, ctype) in (files or {}).items():
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; '
                 f'filename="{fname}"\r\nContent-Type: {ctype}\r\n\r\n').encode()
        body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    url = f"{API}/bot{token}/{method}"
    if not fields and not files:                      # запит без параметрів — звичайний GET
        req = urllib.request.Request(url)
    else:
        req = urllib.request.Request(
            url, data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            data = {"ok": False, "description": f"HTTP {e.code}: {raw[:200]}", "error_code": e.code}
    if not data.get("ok"):
        retry_after = (data.get("parameters") or {}).get("retry_after")
        if data.get("error_code") == 429 and retry_after and _retry:
            time.sleep(min(int(retry_after), 30))
            return call(token, method, fields, files, _retry=False)
        raise TelegramError(data)
    return data["result"]


def send_photo(token, chat_id, jpg: bytes, caption: str) -> int:
    res = call(token, "sendPhoto",
               {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
               {"photo": ("schedule.jpg", jpg, "image/jpeg")})
    return res["message_id"]


def edit_photo(token, chat_id, message_id: int, jpg: bytes, caption: str):
    media = json.dumps({"type": "photo", "media": "attach://photo",
                        "caption": caption, "parse_mode": "HTML"}, ensure_ascii=False)
    return call(token, "editMessageMedia",
                {"chat_id": chat_id, "message_id": message_id, "media": media},
                {"photo": ("schedule.jpg", jpg, "image/jpeg")})


def send_text(token, chat_id, text: str, reply_to: int = None) -> int:
    res = call(token, "sendMessage", {
        "chat_id": chat_id, "text": text, "parse_mode": "HTML",
        "reply_parameters": json.dumps({"message_id": reply_to, "allow_sending_without_reply": True})
        if reply_to else None,
        "disable_web_page_preview": "true"})
    return res["message_id"]
