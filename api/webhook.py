import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

import psycopg


def env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def telegram(method, payload):
    token = env("BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API error: {detail}") from exc
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API returned an error: {result}")
    return result.get("result")


def db_connect():
    return psycopg.connect(env("DATABASE_URL"), connect_timeout=10)


def init_db():
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


def add_subscriber(user):
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO subscribers (user_id, username, first_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name
            """,
            (user["id"], user.get("username"), user.get("first_name")),
        )


def remove_subscriber(user_id):
    with db_connect() as conn:
        conn.execute("DELETE FROM subscribers WHERE user_id = %s", (user_id,))


def get_subscribers():
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT user_id FROM subscribers ORDER BY joined_at"
        ).fetchall()
    return [row[0] for row in rows]


def subscriber_count():
    with db_connect() as conn:
        row = conn.execute("SELECT COUNT(*) FROM subscribers").fetchone()
    return row[0]


def send_text(chat_id, text):
    return telegram("sendMessage", {"chat_id": chat_id, "text": text})


def handle_update(update):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat = message.get("chat") or {}
    user = message.get("from") or {}
    chat_id = chat.get("id")
    user_id = user.get("id")
    if not chat_id or not user_id or user.get("is_bot"):
        return

    text = (message.get("text") or "").strip()
    command = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
    args = text.split(maxsplit=1)[1].strip() if len(text.split(maxsplit=1)) > 1 else ""

    admin_id = int(env("ADMIN_ID"))
    is_admin = user_id == admin_id
    channel_id = env("CHANNEL_ID")
    auto_reply = os.getenv(
        "AUTO_REPLY",
        "Thanks for contacting us! Our team will get back to you soon.",
    )

    if command == "/start":
        add_subscriber(user)
        send_text(chat_id, "Welcome! You are subscribed. Send /stop to unsubscribe.")
        return

    if command == "/stop":
        remove_subscriber(user_id)
        send_text(chat_id, "You have been unsubscribed.")
        return

    if command == "/help":
        help_text = (
            "Available commands:\n"
            "/start - Subscribe to updates\n"
            "/stop - Unsubscribe\n"
            "/help - Show help"
        )
        if is_admin:
            help_text += (
                "\n\nAdmin commands:\n"
                "/stats - Subscriber count\n"
                "/broadcast MESSAGE - Send text to subscribers\n"
                "/post MESSAGE - Post text to the channel"
            )
        send_text(chat_id, help_text)
        return

    if command in ("/stats", "/broadcast", "/post") and not is_admin:
        send_text(chat_id, "This command is available to the bot admin only.")
        return

    if command == "/stats":
        send_text(chat_id, f"Subscribers: {subscriber_count()}")
        return

    if command == "/broadcast":
        if not args:
            send_text(chat_id, "Usage: /broadcast Your message")
            return
        subscribers = get_subscribers()
        sent = 0
        failed = 0
        # Keep each serverless invocation bounded; run another batch if needed.
        batch = subscribers[:100]
        for subscriber_id in batch:
            try:
                send_text(subscriber_id, args)
                sent += 1
            except Exception:
                failed += 1
        remaining = max(0, len(subscribers) - len(batch))
        send_text(
            chat_id,
            f"Broadcast batch complete. Sent: {sent}, failed: {failed}, remaining: {remaining}",
        )
        return

    if command == "/post":
        if not args:
            send_text(chat_id, "Usage: /post Your channel message")
            return
        send_text(channel_id, args)
        send_text(chat_id, "Posted to channel.")
        return

    # Admin can send a photo, video, document, or text directly to the bot
    # to copy that message into the configured channel.
    if chat.get("type") == "private" and is_admin:
        telegram(
            "copyMessage",
            {
                "chat_id": channel_id,
                "from_chat_id": chat_id,
                "message_id": message["message_id"],
            },
        )
        send_text(chat_id, "Copied to channel.")
        return

    if chat.get("type") == "private" and not is_admin:
        send_text(chat_id, auto_reply)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        expected = env("WEBHOOK_SECRET")
        received = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(received, expected):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("Invalid request size")
            update = json.loads(self.rfile.read(length).decode("utf-8"))
            init_db()
            handle_update(update)
            body = b'{"ok":true}'
            self.send_response(200)
        except Exception as exc:
            print(f"Webhook processing failed: {exc}")
            body = b'{"ok":false}'
            self.send_response(500)

        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Telegram webhook is running.")

    def log_message(self, format, *args):
        print(format % args)
