import os


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


BOT_TOKEN = _required("BOT_TOKEN")
ADMIN_ID = int(_required("ADMIN_ID"))
CHANNEL_ID = _required("CHANNEL_ID")
AUTO_REPLY = os.getenv("AUTO_REPLY", "Thanks for contacting us! Our team will get back to you soon.")
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.sqlite3")
