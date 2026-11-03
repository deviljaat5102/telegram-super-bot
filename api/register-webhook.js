export default async function handler(req, res) {
  const key = req.query?.key;
  const secret = process.env.WEBHOOK_SECRET;
  const token = process.env.BOT_TOKEN;
  if (!secret || key !== secret) return res.status(401).json({ ok: false, error: "Unauthorized" });
  if (!token) return res.status(500).json({ ok: false, error: "BOT_TOKEN is missing" });
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  const proto = req.headers["x-forwarded-proto"] || "https";
  const webhookUrl = `${proto}://${host}/api/webhook`;
  const response = await fetch(`https://api.telegram.org/bot${token}/setWebhook`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      url: webhookUrl,
      secret_token: secret,
      allowed_updates: ["message", "edited_message"],
      drop_pending_updates: false
    })
  });
  const data = await response.json();
  return res.status(data.ok ? 200 : 502).json({ webhook_url: webhookUrl, telegram: data });
}
