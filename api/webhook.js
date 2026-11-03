import { neon } from "@neondatabase/serverless";

const json = (statusCode, body) => ({ statusCode, headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
const env = (key) => process.env[key];

async function tg(method, payload) {
  const response = await fetch(`https://api.telegram.org/bot${env("BOT_TOKEN")}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!data.ok) throw new Error(data.description || "Telegram API request failed");
  return data.result;
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
  const secret = req.headers["x-telegram-bot-api-secret-token"];
  if (!env("WEBHOOK_SECRET") || secret !== env("WEBHOOK_SECRET")) {
    return res.status(401).json({ ok: false, error: "Unauthorized webhook" });
  }
  if (!env("BOT_TOKEN") || !env("DATABASE_URL")) {
    return res.status(500).json({ ok: false, error: "BOT_TOKEN or DATABASE_URL is missing" });
  }

  try {
    const sql = neon(env("DATABASE_URL"));
    await ensureSchema(sql);
    const update = req.body || {};
    const message = update.message || update.edited_message;
    if (!message || !message.chat) return res.status(200).json({ ok: true });

    const chatId = message.chat.id;
    const text = (message.text || message.caption || "").trim();
    const from = message.from || {};
    const isAdmin = String(from.id) === String(env("ADMIN_ID") || "");

    if (text === "/start" || text.startsWith("/start ")) {
      await sql`INSERT INTO subscribers (chat_id, username, first_name, is_active)
        VALUES (${chatId}, ${from.username || null}, ${from.first_name || null}, TRUE)
        ON CONFLICT (chat_id) DO UPDATE SET username = EXCLUDED.username,
        first_name = EXCLUDED.first_name, is_active = TRUE, updated_at = NOW()`;
      await tg("sendMessage", { chat_id: chatId, text: "Welcome! You are subscribed. Use /help to see commands." });
    } else if (text === "/stop") {
      await sql`UPDATE subscribers SET is_active = FALSE, updated_at = NOW() WHERE chat_id = ${chatId}`;
      await tg("sendMessage", { chat_id: chatId, text: "You have been unsubscribed. Send /start to subscribe again." });
    } else if (text === "/help") {
      await tg("sendMessage", { chat_id: chatId, text: "Commands:\n/start - Subscribe\n/stop - Unsubscribe\n/help - Help\nAdmin: /stats, /broadcast your message, /post your message or send media privately to copy it to the channel." });
    } else if (isAdmin && text === "/stats") {
      const rows = await sql`SELECT COUNT(*)::int AS total, COUNT(*) FILTER (WHERE is_active)::int AS active FROM subscribers`;
      await tg("sendMessage", { chat_id: chatId, text: `Subscribers: ${rows[0].total}\nActive: ${rows[0].active}` });
    } else if (isAdmin && text.startsWith("/broadcast ")) {
      const broadcastText = text.slice(11).trim();
      if (!broadcastText) {
        await tg("sendMessage", { chat_id: chatId, text: "Usage: /broadcast your message" });
      } else {
        const rows = await sql`SELECT chat_id FROM subscribers WHERE is_active = TRUE`;
        let sent = 0;
        for (const row of rows) {
          try { await tg("sendMessage", { chat_id: row.chat_id, text: broadcastText }); sent++; }
          catch { await sql`UPDATE subscribers SET is_active = FALSE, updated_at = NOW() WHERE chat_id = ${row.chat_id}`; }
        }
        await tg("sendMessage", { chat_id: chatId, text: `Broadcast sent to ${sent} active subscribers.` });
      }
    } else if (isAdmin && text.startsWith("/post ")) {
      const postText = text.slice(6).trim();
      if (!env("CHANNEL_ID")) throw new Error("CHANNEL_ID is missing");
      await tg("sendMessage", { chat_id: env("CHANNEL_ID"), text: postText });
      await tg("sendMessage", { chat_id: chatId, text: "Posted to channel." });
    } else if (isAdmin && message.chat.type === "private" && env("CHANNEL_ID")) {
      await tg("copyMessage", { chat_id: env("CHANNEL_ID"), from_chat_id: chatId, message_id: message.message_id });
      await tg("sendMessage", { chat_id: chatId, text: "Copied to channel." });
    } else if (message.chat.type === "private" && !text.startsWith("/")) {
      await tg("sendMessage", { chat_id: chatId, text: env("AUTO_REPLY") || "Thanks for your message. Our team will get back to you soon." });
    }
    return res.status(200).json({ ok: true });
  } catch (error) {
    console.error("Webhook error:", error);
    return res.status(500).json({ ok: false, error: "Webhook processing failed" });
  }
}
