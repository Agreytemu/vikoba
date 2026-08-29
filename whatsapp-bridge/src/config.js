module.exports = {
  port: Number(process.env.PORT || process.env.BRIDGE_PORT || 8787),
  // Shared secret checked on every request (`x-bridge-token` header).
  // MUST match the backend's WHATSAPP_BRIDGE_TOKEN exactly.
  bridgeToken: process.env.BRIDGE_TOKEN || "vikoba-bridge-dev-token",
  // Supabase — session auth (creds + keys) is stored here, not on disk.
  supabaseUrl: process.env.SUPABASE_URL || "",
  supabaseServiceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY || "",
  supabaseSessionsTable: process.env.SUPABASE_SESSIONS_TABLE || "whatsapp_sessions",
  // Restart after an unexpected disconnect after this many seconds.
  reconnectDelayMs: Number(process.env.RECONNECT_DELAY_MS || 5000),
  // Pause between messages while sending to many recipients.
  bulkDelayMs: Number(process.env.BULK_DELAY_MS || 800),
  // Fallback Baileys app version if the latest-version fetch fails.
  baileysVersionFallback: process.env.BAILEYS_VERSION_FALLBACK || "2.3000.1014506005-cloud",
};