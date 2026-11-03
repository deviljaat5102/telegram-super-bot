# Telegram Super Bot

A Telegram bot with subscriber management, admin broadcasts, channel posting, and automatic replies. The repository includes both the original local polling runner and a Vercel webhook deployment.

## Vercel deployment

The Vercel version uses Telegram webhooks and Neon PostgreSQL. Do not deploy the old polling runner as a Vercel serverless function.

### 1. Create a Neon database

1. Create a free project at https://neon.tech.
2. Open the project's connection details.
3. Copy the PostgreSQL connection string and keep it private.

### 2. Import this repository into Vercel

1. In Vercel, choose **Add New → Project**.
2. Import `deviljaat5102/telegram-super-bot`.
3. Keep Root Directory as `./`.
4. The Python functions are in the `api/` folder.

### 3. Add Vercel environment variables

Add these under Project → Settings → Environment Variables. Apply them to Production (and Preview if you plan to test previews).

- `BOT_TOKEN`: token from BotFather
- `ADMIN_ID`: your numeric Telegram user ID
- `CHANNEL_ID`: channel username such as `@my_channel` or numeric channel ID
- `DATABASE_URL`: Neon PostgreSQL connection string (keep the SSL parameters supplied by Neon)
- `WEBHOOK_SECRET`: a private 32–64 character value using only letters, numbers, underscores, and hyphens
- `SETUP_SECRET`: a separate long random value used only for the one-time setup URL
- `AUTO_REPLY`: optional automatic reply to private messages from non-admin users
- `PUBLIC_URL`: optional production URL such as `https://your-project.vercel.app`; if omitted, the setup endpoint uses Vercel's `VERCEL_URL`

Never commit real tokens, database URLs, or secrets to GitHub.

### 4. Deploy

Deploy the project from Vercel. After deployment is READY, note its production URL.

### 5. Register the Telegram webhook

Open this URL once in your browser, replacing the placeholders:

```
https://YOUR-PROJECT.vercel.app/api/setup?key=YOUR_SETUP_SECRET
```

A successful response contains `"ok": true` from Telegram. Do not share this setup URL because it contains your setup secret. After successful setup, remove `SETUP_SECRET` from Vercel environment variables and redeploy; the webhook itself will continue working.

### 6. Test the bot

- Open the bot in Telegram and send `/start`.
- Send `/help`.
- As admin, try `/stats`, `/post Hello channel`, and `/broadcast Hello subscribers`.
- Add the bot as an administrator in the target channel with permission to post messages.

## Bot commands

- `/start` — subscribe to updates
- `/stop` — unsubscribe
- `/help` — show help
- `/stats` — admin-only subscriber count
- `/broadcast MESSAGE` — admin-only text broadcast
- `/post MESSAGE` — admin-only channel text post

An admin can send a photo, video, document, or other Telegram message privately to the bot; the bot copies it to the configured channel.

The webhook broadcast currently processes up to 100 subscribers per command to keep a serverless request bounded. If there are more than 100 subscribers, the response reports how many remain.

## Local polling runner (optional)

The original `bot.py` remains available for an always-on Python host. It uses SQLite and long polling. It is not the entry point for Vercel deployment.

For local use, install `python-telegram-bot` separately if you want to run the legacy polling version.

## Security

- Never commit a real `.env`, Telegram bot token, Neon URL, or setup secret.
- If the bot token is exposed, revoke it through BotFather and generate a new one.
- Keep the webhook secret and setup secret private.
- Vercel filesystem is ephemeral; subscriber data is stored in Neon PostgreSQL.
