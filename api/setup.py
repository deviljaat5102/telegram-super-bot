import hmac
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        expected_key = os.environ.get("SETUP_SECRET", "")
        supplied_key = parse_qs(urlparse(self.path).query).get("key", [""])[0]
        if not expected_key or not hmac.compare_digest(supplied_key, expected_key):
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
            return

        token = os.environ.get("BOT_TOKEN", "").strip()
        webhook_secret = os.environ.get("WEBHOOK_SECRET", "").strip()
        public_url = os.environ.get("PUBLIC_URL", "").strip()
        vercel_url = os.environ.get("VERCEL_URL", "").strip()
        base_url = public_url or (f"https://{vercel_url}" if vercel_url else "")
        if not token or not webhook_secret or not base_url:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(
                b"Missing BOT_TOKEN, WEBHOOK_SECRET, or PUBLIC_URL/VERCEL_URL."
            )
            return

        webhook_url = base_url.rstrip("/") + "/api/webhook"
        payload = json.dumps({
            "url": webhook_url,
            "secret_token": webhook_secret,
            "allowed_updates": ["message", "edited_message"],
            "drop_pending_updates": False,
        }).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/setWebhook",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))
            status = 200 if result.get("ok") else 502
        except (urllib.error.URLError, TimeoutError) as exc:
            result = {"ok": False, "description": str(exc)}
            status = 502

        body = json.dumps({
            "webhook_url": webhook_url,
            "telegram": result,
        }).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(format % args)
