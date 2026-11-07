"""Small Telegram notification service for Railway; no third-party packages."""

import hmac
import html
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
NOTIFY_SECRET = os.environ.get("NOTIFY_SECRET", "").strip()
PORT = int(os.environ.get("PORT", "8080"))
MAX_BODY = 16_384
LOG = logging.getLogger("notifier")


def telegram(method, payload):
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        f"https://api.telegram.org/bot{TOKEN}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=40) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError("Telegram API returned an error")
    return result["result"]


def send(chat_id, text):
    telegram("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})


def safe(value, limit=500):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return html.escape(str(value).strip()[:limit])


def format_notification(payload):
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    fields = [
        ("Имя", payload.get("name")),
        ("Телефон", payload.get("phone")),
        ("Email", payload.get("email")),
        ("Проект", payload.get("project")),
        ("Кампания", payload.get("campaign")),
        ("Форма", payload.get("form")),
        ("Источник", payload.get("source")),
        ("Комментарий", payload.get("message")),
    ]
    lines = ["<b>📩 Новая заявка</b>"]
    lines.extend(f"<b>{label}:</b> {safe(value)}" for label, value in fields if value is not None and str(value).strip())
    extra = payload.get("fields")
    if isinstance(extra, dict):
        lines.extend(f"<b>{safe(key, 80)}:</b> {safe(value)}" for key, value in list(extra.items())[:20])
    if len(lines) == 1:
        raise ValueError("At least one lead field is required")
    while len("\n".join(lines)) > 3900:
        lines.pop()
    return "\n".join(lines)


def poll_telegram():
    offset = None
    while True:
        try:
            payload = {"timeout": 25, "allowed_updates": ["message"]}
            if offset is not None:
                payload["offset"] = offset
            for update in telegram("getUpdates", payload):
                offset = update["update_id"] + 1
                message = update.get("message", {})
                chat = message.get("chat", {})
                chat_id = chat.get("id")
                command = message.get("text", "").split(" ")[0].split("@")[0].lower()
                if not chat_id:
                    continue
                if command in ("/start", "/chatid"):
                    send(chat_id, f"Бот работает ✅\nID этого чата: <code>{chat_id}</code>\nУкажите его в Railway как TELEGRAM_CHAT_ID.")
                elif command == "/test":
                    send(chat_id, "Тестовое уведомление ✅")
        except (HTTPError, URLError, OSError, RuntimeError, ValueError, KeyError):
            LOG.warning("Telegram polling failed; retrying in 5 seconds")
            time.sleep(5)


class Handler(BaseHTTPRequestHandler):
    def respond(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.respond(200, {"ok": True, "telegram_configured": bool(TOKEN)})
        else:
            self.respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/notify":
            self.respond(404, {"error": "not found"})
            return
        auth = self.headers.get("Authorization", "")
        if not NOTIFY_SECRET or not hmac.compare_digest(auth, f"Bearer {NOTIFY_SECRET}"):
            self.respond(401, {"error": "unauthorized"})
            return
        if not TOKEN:
            self.respond(503, {"error": "TELEGRAM_BOT_TOKEN is not configured"})
            return
        if not CHAT_ID:
            self.respond(503, {"error": "TELEGRAM_CHAT_ID is not configured"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                self.respond(413, {"error": "invalid body size"})
                return
            payload = json.loads(self.rfile.read(length))
            text = format_notification(payload)
        except (ValueError, UnicodeDecodeError):
            self.respond(400, {"error": "invalid lead JSON"})
            return
        try:
            send(CHAT_ID, text)
        except (HTTPError, URLError, OSError, RuntimeError, ValueError):
            LOG.error("Telegram delivery failed")
            self.respond(502, {"error": "Telegram delivery failed"})
            return
        self.respond(200, {"ok": True})

    def log_message(self, format_string, *args):
        LOG.info("HTTP %s", format_string % args)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if TOKEN:
        threading.Thread(target=poll_telegram, daemon=True).start()
    else:
        LOG.warning("TELEGRAM_BOT_TOKEN is not configured; Telegram bot is inactive")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    LOG.info("Listening on port %s", PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
