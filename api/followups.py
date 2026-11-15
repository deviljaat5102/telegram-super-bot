import hmac
import json
import os
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler

import psycopg


def env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def telegram_send(chat_id, text):
    token = env("BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=15) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram API error"))
    return result.get("result")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        expected = env("FOLLOWUP_CRON_SECRET")
        received = self.headers.get("Authorization", "")
        if not hmac.compare_digest(
            received.encode("utf-8"),
            f"Bearer {expected}".encode("utf-8"),
        ):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return

        first_text = os.getenv(
            "FOLLOWUP_1H_MESSAGE",
            "Just checking in 😊 Did you get a chance to review our message? Let us know if you need any help.",
        )
        second_text = os.getenv(
            "FOLLOWUP_1D_MESSAGE",
            "Hello again! We're following up on your enquiry. Are you still interested? We're happy to help.",
        )

        sent = failed = 0
        try:
            with psycopg.connect(env("DATABASE_URL"), connect_timeout=10) as conn:
                # Row locks prevent two overlapping scheduler calls from sending
                # the same follow-up at the same time.
                rows = conn.execute(
                    """
                    SELECT chat_id, first_message_at, next_stage
                    FROM followup_schedules
                    WHERE active = TRUE
                      AND (
                        (next_stage = 1 AND first_message_at <= NOW() - INTERVAL '1 hour')
                        OR
                        (next_stage = 2 AND first_message_at <= NOW() - INTERVAL '24 hours')
                      )
                    ORDER BY first_message_at
                    LIMIT 50
                    FOR UPDATE SKIP LOCKED
                    """
                ).fetchall()

                for chat_id, first_message_at, stage in rows:
                    message_text = first_text if stage == 1 else second_text
                    try:
                        telegram_send(chat_id, message_text)
                        if stage == 1:
                            conn.execute(
                                "UPDATE followup_schedules SET next_stage = 2 WHERE chat_id = %s",
                                (chat_id,),
                            )
                        else:
                            conn.execute(
                                "UPDATE followup_schedules SET active = FALSE WHERE chat_id = %s",
                                (chat_id,),
                            )
                        sent += 1
                    except Exception as exc:
                        print(f"Follow-up failed for chat {chat_id}: {exc}")
                        failed += 1

            body = json.dumps({
                "ok": True,
                "sent": sent,
                "failed": failed,
                "checked_at_utc": "database time",
            }).encode()
            self.send_response(200)
        except Exception as exc:
            print(f"Follow-up scheduler failed: {exc}")
            body = json.dumps({"ok": False, "error": str(exc)}).encode()
            self.send_response(500)

        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.do_GET()

    def log_message(self, format, *args):
        print(format % args)
