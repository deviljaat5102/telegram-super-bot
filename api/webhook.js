import { neon } from "@neondatabase/serverless";

const env = (key) => process.env[key];

async function telegram(method, payload) {
  const response = await fetch(`https://api.telegram.org/bot${env("BOT_TOKEN")}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.description || `Telegram ${method} failed`);
  return result.result;
}

async function ensureSchema(sql) {
  await sql`CREATE TABLE IF NOT EXISTS subscribers (
    chat_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  )`;
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ ok: false, error: "Method not allowed" });
  if (!env("BOT_TOKEN") || !env("DATABASE_URL") || !env("WEBHOOK_SECRET")) {
    return res.status(500).json({ ok: false, error: "Missing BOT_TOKEN, DATABASE_URL, or WEBHOOK_SECRET" });
  }
  if (req.headers["x-telegram-bot-api-secret-token"] !== env("WEBHOOK_SECRET")) {
    return res.status(401).json({ ok: false, error: "Unauthorized webhook" });
  }

  try {
    const sql = neon(env("DATABASE_URL"));
    await ensureSchema(sql);
    const update = req.body || {};
    const message = update.message || update.edited_message;
    if (!message?.chat) return res.status(200).json({ ok: true });

    const chatId = message.chat.id;
    const messageText = (message.text || message.caption || "").trim();
    const from = message.from || {};
    const isAdmin = Boolean(env("ADMIN_ID")) && String(from.id) === String(env("ADMIN_ID"));
    const isPrivate = message.chat.type === "private";

    if (messageText === "/start" || messageText.startsWith("/start ")) {
      await sql`INSERT INTO subscribers (chat_id, username, first_name, is_active)
        VALUES (${chatId}, ${from.username || null}, ${from.first_name || null}, TRUE)
        ON CONFLICT (chat_id) DO UPDATE SET username = EXCLUDED.username,
        first_name = EXCLUDED.first_name, is_active = TRUE, updated_at = NOW()`;
      await telegram("sendMessage", { chat_id: chatId, text: "Welcome! You are subscribed. Send /help to see commands." });
    } else if (messageText === "/stop") {
      await sql`UPDATE subscribers SET is_active = FALSE, updated_at = NOW() WHERE chat_id = ${chatId}`;
      await telegram("sendMessage", { chat_id: chatId, text: "You are unsubscribed. Send /start to subscribe again." });
    } else if (messageText === "/help") {
      await telegram("sendMessage", { chat_id: chatId, text: "Commands:\n/start - Subscribe\n/stop - Unsubscribe\n/help - Help\nAdmin: /stats, /broadcast MESSAGE, /post MESSAGE. Admin can also send media privately to copy it to the channel." });
    } else if (isAdmin && messageText === "/stats") {
      const rows = await sql`SELECT COUNT(*)::int AS total, COUNT(*) FILTER (WHERE is_active)::int AS active FROM subscribers`;
      await telegram("sendMessage", { chat_id: chatId, text: `Subscribers: ${rows[0].total}\nActive: ${rows[0].active}` });
    } else if (isAdmin && messageText.startsWith("/broadcast ")) {
      const broadcastText = messageText.slice(11).trim();
      if (!broadcastText) {
        await telegram("sendMessage", { chat_id: chatId, text: "Usage: /broadcast your message" });
      } else {
        const rows = await sql`SELECT chat_id FROM subscribers WHERE is_active = TRUE ORDER BY created_at ASC LIMIT 100`;
        let sent = 0;
        for (const row of rows) {
          try {
            await telegram("sendMessage", { chat_id: row.chat_id, text: broadcastText });
            sent++;
          } catch (error) {
            console.error("Broadcast delivery failed for a subscriber");
            await sql`UPDATE subscribers SET is_active = FALSE, updated_at = NOW() WHERE chat_id = ${row.chat_id}`;
          }
        }
        const remaining = await sql`SELECT COUNT(*)::int AS count FROM subscribers WHERE is_active = TRUE`;
        await telegram("sendMessage", { chat_id: chatId, text: `Broadcast delivered to ${sent} users. Active subscribers remaining (including those already sent): ${remaining[0].count}. Limit: 100 recipients per command.` });
      }
    } else if (isAdmin && messageText.startsWith("/post ")) {
      if (!env("CHANNEL_ID")) throw new Error("CHANNEL_ID is missing");
      await telegram("sendMessage", { chat_id: env("CHANNEL_ID"), text: messageText.slice(6).trim() });
      await telegram("sendMessage", { chat_id: chatId, text: "Posted to channel." });
    } else if (isAdmin && isPrivate && env("CHANNEL_ID")) {
      await telegram("copyMessage", { chat_id: env("CHANNEL_ID"), from_chat_id: chatId, message_id: message.message_id });
      await telegram("sendMessage", { chat_id: chatId, text: "Copied to channel." });
    } else if (isPrivate && !messageText.startsWith("/")) {
      await telegram("sendMessage", { chat_id: chatId, text: env("AUTO_REPLY") || "Thanks for your message. Our team will get back to you soon." });
    }

    return res.status(200).json({ ok: true });
  } catch (error) {
    console.error("Telegram webhook processing failed:", error.message);
    return res.status(500).json({ ok: false, error: "Webhook processing failed" });
  }
}
