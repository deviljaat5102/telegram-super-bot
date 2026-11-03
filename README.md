# Telegram Super Bot

A Python Telegram bot with subscriber management, admin broadcasts, and channel posting.

## Features

- Subscribe users with `/start` and unsubscribe with `/stop`
- Show subscriber count with admin-only `/stats`
- Send a text broadcast to subscribers with admin-only `/broadcast MESSAGE`
- Publish text to the configured channel with admin-only `/post MESSAGE`
- Copy a message or media sent privately by the admin to the configured channel
- Send an automatic reply to non-admin private messages

## Requirements

- Python 3.10+
- A Telegram bot token from BotFather
- A Telegram channel where the bot is an administrator with permission to post
- The numeric Telegram user ID of the bot administrator

## Setup

1. Clone this repository.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in the values:

   - `BOT_TOKEN`: token from BotFather
   - `ADMIN_ID`: your numeric Telegram user ID
   - `CHANNEL_ID`: channel username (for example, `@my_channel`) or numeric channel ID
   - `AUTO_REPLY`: optional reply for non-admin users
   - `DATABASE_PATH`: optional SQLite database path

4. Start the bot:

   ```bash
   python bot.py
   ```

## Admin commands

- `/stats` — show subscriber count
- `/broadcast Your message` — send a text message to all subscribers
- `/post Your message` — post a text message to the channel

To publish media, send a photo, video, document, or other supported Telegram message directly to the bot from the configured admin account. The bot copies that message to the channel.

## Security and deployment

- Never commit your real `.env` file or bot token.
- Keep `ADMIN_ID` restricted to trusted administrators.
- If the bot token is exposed, revoke it through BotFather and generate a new one.
- Use a persistent disk for the SQLite database when deploying.
- Run only one polling instance for this bot token unless you intentionally configure a webhook-based deployment.

## Notes

This starter version broadcasts text to subscribers. It copies admin-sent media to the channel, but does not yet include media broadcasting to all subscribers.
