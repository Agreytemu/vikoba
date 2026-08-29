const express = require("express");
const config = require("./config");
const { store, toWhatsAppJid } = require("./sessions");
const { flushAllPending } = require("./supabase");

const app = express();
app.use(express.json({ limit: "4mb" }));

// Every call must carry the shared token so only the Django backend (and
// anything we give the token to) can use the gateway.
app.use((req, res, next) => {
  if (req.header("x-bridge-token") !== config.bridgeToken) {
    return res.status(401).json({ error: "unauthorized" });
  }
  next();
});

app.get("/health", (req, res) => {
  res.json({
    ok: true,
    bridge: "vikoba-whatsapp-bridge",
    pairingMethod: "qr-or-phone-code",
    storage: "supabase",
    uptimeSeconds: Math.round(process.uptime()),
  });
});

// Sessions ----------------------------------------------------------------

app.post("/sessions", (req, res) => {
  const { id, display_name } = req.body || {};
  if (!id || !/^[A-Za-z0-9_-]{1,64}$/.test(id)) {
    return res.status(400).json({ error: "invalid_session_id" });
  }
  const status = store.start(id, { displayName: display_name || "" });
  res.json(status);
});

app.get("/sessions", (req, res) => {
  res.json(store.list());
});

app.get("/sessions/:id", (req, res) => {
  const status = store.publicStatus(req.params.id, { includePairing: true });
  if (!status.exists) return res.status(404).json({ error: "not_found" });
  res.json(status);
});

// Pair a device by phone number — returns a pairing code to type into the
// phone (WhatsApp > Linked devices > "Link with phone number instead").
// The QR flow is also supported by Baileys and surfaced to the frontend when
// the phone is scanned instead of entering a code.
app.post("/sessions/:id/pair", async (req, res) => {
  const { phone } = req.body || {};
  if (!phone) return res.status(400).json({ error: "phone_required" });
  const result = await store.requestPairingCode(req.params.id, phone);
  if (result.ok) return res.json(result);
  const statusCode = result.error === "missing_session" ? 404 : 400;
  return res.status(statusCode).json(result);
});

app.delete("/sessions/:id", async (req, res) => {
  // ?clear=1 also wipes the stored auth so the device can be re-paired fresh
  // (e.g. after a stuck logged_out or ban).
  const result = await store.stop(req.params.id, { clearAuth: req.query.clear === "1" });
  res.json(result);
});

// Messaging ---------------------------------------------------------------

app.post("/sessions/:id/send", async (req, res) => {
  const { to, text } = req.body || {};
  if (!to || !text) return res.status(400).json({ error: "to_and_text_required" });
  const jid = toWhatsAppJid(to);
  if (!jid) return res.status(400).json({ error: "invalid_recipient" });
  const result = await store.send(req.params.id, jid, String(text));
  if (result.sent) return res.json({ ok: true });
  return res.json({ ok: false, error: result.error, detail: result.detail || null });
});

app.post("/sessions/:id/send-bulk", async (req, res) => {
  const { to, text } = req.body || {};
  if (!Array.isArray(to) || to.length === 0 || !text) {
    return res.status(400).json({ error: "to_list_and_text_required" });
  }
  const jids = to.map(toWhatsAppJid).filter(Boolean);
  const result = await store.sendBulk(req.params.id, jids, String(text));
  return res.json({ ok: result.failed.length === 0, ...result });
});

app.use((req, res) => res.status(404).json({ error: "not_found" }));

app.listen(config.port, () => {
  console.log(`[bridge] listening on :${config.port}`);
});

// Flush debounced auth writes so sessions survive a restart (Render sends
// SIGTERM on deploy/scale-down).
async function shutdown() {
  try {
    await flushAllPending();
  } catch (error) {
    console.error("[bridge] shutdown flush error:", String(error?.message || error));
  }
  process.exit(0);
}
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);