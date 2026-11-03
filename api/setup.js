export default async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).json({ ok: false, error: "Method not allowed" });
  const setupSecret = process.env.SETUP_SECRET;
  if (!setupSecret || req.query?.key !== setupSecret) {
    return res.status(401).json({ ok: false, error: "Unauthorized setup request" });
  }
  if (!process.env.BOT_TOKEN || !process.env.WEBHOOK_SECRET) {
    return res.status(500).json({ ok: false, error: "BOT_TOKEN or WEBHOOK_SECRET is missing" });
  }

  const baseUrl = process.env.PUBLIC_URL
    ? process.env.PUBLIC_URL.replace(/\/$/, "")
    : process.env.VERCEL_URL
      ? `https://${process.env.VERCEL_URL}`
      : "";
  if (!baseUrl) return res.status(500).json({ ok: false, error: "PUBLIC_URL or VERCEL_URL is unavailable" });

  const webhookUrl = `${baseUrl}/api/webhook`;
  const response = await fetch(`https://api.telegram.org/bot${process.env.BOT_TOKEN}/setWebhook`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      url: webhookUrl,
      secret_token: process.env.WEBHOOK_SECRET,
      allowed_updates: ["message", "edited_message"],
      drop_pending_updates: false
    })
  });
  const result = await response.json();
  return res.status(result.ok ? 200 : 502).json({ ok: result.ok, webhook_url: webhookUrl, telegram: result });
}
