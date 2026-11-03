import json
import os
import re
import urllib.parse
import urllib.request

import psycopg


def env(name, default=None):
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


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


def telegram(method, payload):
    token = env("BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode({
        key: json.dumps(value) if isinstance(value, (dict, list)) else value
        for key, value in payload.items()
    }).encode()
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.loads(response.read().decode())
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram API error"))
    return result.get("result")


def send_message(chat_id, text):
    return telegram("sendMessage", {"chat_id": chat_id, "text": text})


def is_admin(user_id):
    return str(user_id) == env("ADMIN_ID")


def add_subscriber(user):
    with db_connect() as conn:
        conn.execute("""
            INSERT INTO subscribers (user_id, username, first_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name
        """, (user["id"], user.get("username"), user.get("first_name")))


def remove_subscriber(user_id):
    with db_connect() as conn:
        conn.execute("DELETE FROM subscribers WHERE user_id = %s", (user_id,))


def subscriber_count():
    with db_connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]


def subscriber_ids(limit=100):
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT user_id FROM subscribers ORDER BY joined_at LIMIT %s", (limit,)
        ).fetchall()
    return [row[0] for row in rows]


def handle_update(update):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat = message.get("chat", {})
    user = message.get("from", {})
    chat_id = chat.get("id")
    user_id = user.get("id")
    text = message.get("text", "") or message.get("caption", "")

    if chat.get("type") != "private" or not user_id:
        return

    admin = is_admin(user_id)

    if text.startswith("/start"):
        add_subscriber(user)
        send_message(chat_id, "Welcome! You are subscribed. Send /stop to unsubscribe.")
        return

    if text.startswith("/stop"):
        remove_subscriber(user_id)
        send_message(chat_id, "You have been unsubscribed.")
        return

    if text.startswith("/help"):
        help_text = (
            "Available commands:\\n/start - Subscribe to updates\\n"
            "/stop - Unsubscribe\\n/help - Show help"
        )
        if admin:
            help_text += (
                "\\n\\nAdmin commands:\\n/stats - Subscriber count\\n"
                "/broadcast MESSAGE - Send text to subscribers\\n"
                "/post MESSAGE - Post text to the channel"
            )
        send_message(chat_id, help_text)
        return

    if text.startswith("/stats"):
        if admin:
            send_message(chat_id, f"Subscribers: {subscriber_count()}")
        return

    if text.startswith("/broadcast"):
        if not admin:
            return
        body = text.partition(" ")[2].strip()
        if not body:
            send_message(chat_id, "Usage: /broadcast Your message")
            return
        ids = subscriber_ids(100)
        sent = failed = 0
        for subscriber_id in ids:
            try:
                send_message(subscriber_id, body)
                sent += 1
            except Exception:
                failed += 1
        total = subscriber_count()
        remaining = max(total - len(ids), 0)
        send_message(
            chat_id,
            f"Broadcast done. Sent: {sent}, failed: {failed}, remaining for next batch: {remaining}",
        )
        return

    if text.startswith("/post"):
        if not admin:
            return
        body = text.partition(" ")[2].strip()
        if not body:
            send_message(chat_id, "Usage: /post Your channel message")
            return
        telegram("sendMessage", {"chat_id": env("CHANNEL_ID"), "text": body})
        send_message(chat_id, "Posted to channel.")
        return

    if admin and any(k in message for k in ("photo", "video", "document", "animation", "audio", "voice")):
        telegram("copyMessage", {
            "chat_id": env("CHANNEL_ID"),
            "from_chat_id": chat_id,
            "message_id": message["message_id"],
        })
        send_message(chat_id, "Copied to channel.")
        return

    if not admin:
        send_message(
            chat_id,
            os.getenv(
                "AUTO_REPLY",
                "Thanks for contacting us! Our team will get back to you soon.",
            ),
        )


def json_response(handler, status, payload):
    body = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def safe_secret(value):
    return bool(value) and re.fullmatch(r"[A-Za-z0-9_-]{32,128}", value) is not None
