# Telegram Super Bot

Telegram bot with subscriber management, admin broadcasts, channel posting, and automatic replies. The repository contains a legacy Python long-polling runner and a separate Vercel webhook implementation.

## Vercel + Neon deployment

Use the Python serverless functions in `api/`. Do not run the old `bot.py` polling process on Vercel.

### 1. Neon database

1. Create a free project at https://neon.tech.
2. Open **Connect** for the `production` branch.
3. Select the pooled connection string (the hostname contains `-pooler`) and copy the full PostgreSQL URL.
4. Keep the URL private. The app creates the `subscribers` table automatically on the first webhook update. The webhook creates the `subscribers` table automatically.

### 2. Import to Vercel

1. In Vercel, choose **Add New → Project**.
2. Import `deviljaat5102/telegram-super-bot`.
3. Root Directory: `./`.
4. The Vercel functions are Python files in `api/`.

### 3. Environment variables

In Vercel → Project → Settings → Environment Variables, add the following for **Production**:

- `BOT_TOKEN`: Telegram token from BotFather
- `ADMIN_ID`: your numeric Telegram user ID
- `CHANNEL_ID`: channel username (for example `@yourchannel`) or numeric channel ID
- `DATABASE_URL`: full Neon pooled PostgreSQL connection string
- `WEBHOOK_SECRET`: random 32–64 character secret using letters, numbers, underscores, or hyphens
- `SETUP_SECRET`: a different long random secret used only for initial webhook registration
- `AUTO_REPLY`: optional reply text for private messages from non-admin users
- `PUBLIC_URL`: optional production URL, for example `https://your-project.vercel.app`. If omitted, the setup function uses Vercel's `VERCEL_URL`.

Never paste these secrets into chat or commit them to GitHub.

### 4. Deploy and register webhook

1. Deploy the project and wait until Vercel reports **Ready**.
2. Open this URL once in your browser, replacing both placeholders:
   `https://YOUR-PROJECT.vercel.app/api/webhook?key=YOUR_SETUP_SECRET`
3. A successful response has `"ok": true` and Telegram's `"Webhook was set"` description.
4. Remove `SETUP_SECRET` from Vercel environment variables after successful setup, then redeploy. The webhook keeps working.

The setup URL contains a secret. Do not share it or post a screenshot that reveals it.

### 5. Telegram configuration and test

- Add the bot as an administrator in your channel with permission to post messages.
- Send `/start` to the bot, then `/help`.
- Admin commands: `/stats`, `/post Hello channel`, and `/broadcast Hello subscribers`.
- Send a photo, video, or document privately to the bot as admin; it copies the message to the channel.

## Commands

- `/start` — subscribe
- `/stop` — unsubscribe
- `/help` — help
- `/stats` — admin-only subscriber counts
- `/broadcast MESSAGE` — admin-only text broadcast (up to 100 recipients per command)
- `/post MESSAGE` — admin-only text post to the channel

## Database

Subscriber records are stored in Neon PostgreSQL, not the Vercel filesystem. The webhook creates the required subscriber table automatically.

## Legacy local runner

`bot.py` is the original Python long-polling version for an always-on Python host. It uses SQLite and is not used by the Vercel webhook deployment.
