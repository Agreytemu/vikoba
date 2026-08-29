const pino = require("pino");

const {
  default: makeWASocket,
  makeCacheableSignalKeyStore,
  fetchLatestBaileysVersion,
  DisconnectReason,
} = require("@whiskeysockets/baileys");

const config = require("./config");
const { useSupabaseAuthState, deleteAuth } = require("./supabase");
const QRCode = require("qrcode");

// A deliberately standard browser identity (what the phone shows as "WhatsApp
// Web/logged-in device"). Safari (macOS) is a current, widely-trusted user
// agent for the "link with phone number instead" flow.
const BROWSER_IDENTITY = ["Safari (Macintosh; Intel Mac OS X 10_15_7)", "safari", "17.4"];

const logger = pino({
  level: process.env.LOG_LEVEL || "info",
  timestamp: () => `,"time":"${new Date().toISOString()}"`,
});

class SessionStore {
  constructor() {
    // id -> { sock, saveCreds, flushAuth, status, pairingCode, phone,
    //         wasConnected, connecting, connectingPromise, closing }
    this.sessions = new Map();
    this.reconnectTimers = new Map();
  }

  start(id, { displayName = "" } = {}) {
    const existing = this.sessions.get(id);
    if (existing) {
      // If a previous attempt is still running, leave it alone.
      if (existing.sock || existing.connecting) {
        return this.publicStatus(id);
      }
      // The socket died while never paired (or errored) — start a fresh one.
      this.sessions.delete(id);
    }
    const live = {
      id,
      displayName,
      sock: null,
      saveCreds: null,
      flushAuth: null,
      status: "connecting",
      pairingCode: "",
      qr: "",
      phone: "",
      wasConnected: false,
      connecting: false,
      connectingPromise: null,
      lastError: "",
      closing: false,
    };
    this.sessions.set(id, live);
    this._connect(id);
    return this.publicStatus(id);
  }

  get(id) {
    return this.sessions.get(id) || null;
  }

  async stop(id, { clearAuth = false } = {}) {
    const live = this.get(id);
    if (!live) return { exists: false };
    live.closing = true;
    const timer = this.reconnectTimers.get(id);
    if (timer) {
      clearTimeout(timer);
      this.reconnectTimers.delete(id);
    }
    if (live.sock) {
      live.sock.end(new Error("Session stopped"));
    }
    if (live.flushAuth) {
      await live.flushAuth();
    }
    if (clearAuth) {
      try {
        await deleteAuth(id);
      } catch (error) {
        logger.warn({ id, error: String(error?.message || "") }, "delete auth failed");
      }
    }
    this.sessions.delete(id);
    return { exists: true };
  }

  list() {
    const result = {};
    for (const id of this.sessions.keys()) {
      result[id] = this.publicStatus(id);
    }
    return result;
  }

  publicStatus(id, { includePairing = false } = {}) {
    const live = this.get(id);
    if (!live) return { id, exists: false, status: "missing" };
    const phone = (live.phone || live.sock?.user?.id || "").split(":")[0];
    const status = {
      id,
      exists: true,
      status: live.status,
      phone,
      display_name: live.displayName,
      last_error: live.lastError || "",
    };
    if (includePairing) {
      if (live.pairingCode) status.pairing_code = live.pairingCode;
      status.qr = live.qr || "";
    }
    return status;
  }

  _clearReconnect(id) {
    const timer = this.reconnectTimers.get(id);
    if (timer) {
      clearTimeout(timer);
      this.reconnectTimers.delete(id);
    }
  }

  _scheduleReconnect(id, delayMs) {
    this._clearReconnect(id);
    this.reconnectTimers.set(
      id,
      setTimeout(() => {
        this.reconnectTimers.delete(id);
        this._connect(id);
      }, delayMs),
    );
  }

  async _connect(id) {
    const live = this.get(id);
    if (!live || live.closing) return;

    // Only one socket per session at a time.
    if (live.connecting) return live.connectingPromise;
    live.connecting = true;
    live.lastError = "";
    live.connectingPromise = (async () => {
      try {
        const { state, saveCreds, flush } = await useSupabaseAuthState(id);
        let version;
        try {
          // fetchLatestBaileysVersion hits the GitHub API; on a cold Render
          // instance that can be flaky/rate-limited. Fall back to a pinned
          // known-good version so session startup never dies on it.
          ({ version } = await fetchLatestBaileysVersion());
        } catch (versionError) {
          version = config.baileysVersionFallback || "2.3000.1014506005-cloud";
          logger.warn(
            { id, error: String(versionError?.message || "") },
            "baileys version fetch failed, using pinned fallback",
          );
        }
        const socket = makeWASocket({
          version,
          auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(state.keys, logger),
          },
          printQRInTerminal: false,
          browser: BROWSER_IDENTITY,
          markOnlineOnConnect: false,
          logger,
          // Keep the WebSocket quiet when idle; the phone will not see a
          // "typing" online presence from an unattended gateway.
          emitOwnEvents: false,
          shouldSyncHistoryMessage: () => false,
        });

        live.sock = socket;
        live.saveCreds = saveCreds;
        live.flushAuth = flush;

        socket.ev.on("creds.update", saveCreds);

        socket.ev.on("connection.update", (update) => {
          if (update.qr) {
            // WhatsApp wants a device linked — we prefer QR scanning on the
            // phone (standard WhatsApp Web flow); the pairing code remains as
            // a fallback for devices with no second screen. The raw connect
            // string is turned into a scannable image (data URL) here.
            QRCode.toDataURL(update.qr)
              .then((url) => {
                live.qr = url;
              })
              .catch((error) => {
                logger.warn({ id, error: String(error?.message || "") }, "qr render failed");
                live.qr = "";
              });
            if (live.status !== "connected") {
              live.status = "awaiting_pairing";
            }
          }
          if (update.connection === "open") {
            live.status = "connected";
            live.wasConnected = true;
            live.phone = (socket.user?.id || "").split(":")[0];
            live.pairingCode = "";
            live.qr = "";
          }
          if (update.connection === "close") {
            live.pairingCode = "";
            live.qr = "";
            if (live.closing) return;
            const statusCode = update.lastDisconnect?.error?.output?.statusCode;
            if (statusCode === DisconnectReason.loggedOut) {
              live.status = "logged_out";
              return;
            }
            // Bring the socket back for any non-logout close. If credentials
            // are present the next connect logs straight in; if not, it
            // regenerates a fresh QR. This also covers the 515 "restart
            // required" WhatsApp sends immediately after a first successful
            // pairing — without it the session would be orphaned with no socket
            // and the frontend would hang on "awaiting pairing".
            live.status = live.wasConnected ? "disconnected" : "awaiting_pairing";
            this._scheduleReconnect(id, config.reconnectDelayMs);
          }
        });

        socket.ev.on("messages.upsert", () => {
          // Receiving-side handling is intentionally not part of this gateway;
          // it only delivers server-originated messages (OTP, receipts, bulk).
        });
      } catch (error) {
        live.status = "error";
        live.lastError = String(error?.message || error);
        live.pairingCode = "";
        logger.warn({ id, error: String(error?.message || "") }, "session connect error");
        // Never paired yet -> idle so we do not retry-loop on config problems.
        if (live.wasConnected) {
          this._scheduleReconnect(id, config.reconnectDelayMs);
        }
      } finally {
        live.connecting = false;
        live.connectingPromise = null;
      }
    })();
    return live.connectingPromise;
  }

  /**
   * Makes sure a socket exists for a not-yet-paired session (restarting the
   * connection if the previous one died), so a pairing code can be requested.
   */
  async _ensureSocket(id) {
    const live = this.get(id);
    if (!live) return false;
    if (live.sock && (live.status === "connecting" || live.status === "awaiting_pairing")) {
      return true;
    }
    if (live.status === "connected") return true;
    // Tear down the stale socket and reconnect.
    try {
      if (live.sock) live.sock.end(new Error("restart for pairing"));
    } catch {
      // ignore
    }
    live.sock = null;
    this._clearReconnect(id);
    for (let attempt = 1; attempt <= 2 && !live.sock; attempt += 1) {
      await this._connect(id);
      // A connecting run that is still in flight may assign sock right after
      // our await turns; give it one more short beat before retrying.
      if (!live.sock) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
    }
    return Boolean(live.sock);
  }

  /**
   * Requests a WhatsApp pairing code for the phone number (with country code).
   *
   * The code is meant to be typed into the phone (WhatsApp > Linked devices >
   * "Link with phone number instead"). Baileys also emits a QR code flow, which
   * is exposed to the frontend automatically for in-app scanning.
   */
  async requestPairingCode(id, phone) {
    const live = this.get(id);
    if (!live) return { ok: false, error: "missing_session" };
    if (live.status === "connected") {
      return { ok: false, error: "already_connected" };
    }

    const digits = String(phone || "").replace(/[^\d]/g, "");
    // Accept any country code (254, 255, 1, 44, …) — just require a full
    // number with the country code (no leading zero).
    if (digits.length < 7 || digits.startsWith("0")) {
      return {
        ok: false,
        error: "invalid_phone",
        detail: "Provide the full number with country code, e.g. +2547… or +25574…",
      };
    }

    await this._ensureSocket(id);
    if (!live.sock) {
      return {
        ok: false,
        error: "session_not_started",
        detail: live.lastError || "socket could not be created",
      };
    }

    let code = "";
    let lastError = "";
    // The socket may still be establishing the WebSocket when we are asked —
    // retry a few times before giving up.
    for (let attempt = 1; attempt <= 6; attempt += 1) {
      if (live.status === "connected") {
        return { ok: false, error: "already_connected" };
      }
      try {
        code = await live.sock.requestPairingCode(digits);
        if (code) break;
      } catch (error) {
        lastError = String(error?.message || error);
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }

    if (!code) {
      return {
        ok: false,
        error: "pairing_request_failed",
        detail: lastError || "waited too long for the WhatsApp connection",
      };
    }

    const clean = String(code).replace(/[^\w]/g, "").toUpperCase();
    live.pairingCode = clean.length > 4 ? `${clean.slice(0, 4)}-${clean.slice(4)}` : clean;
    return { ok: true, pairing: live.pairingCode };
  }

  async send(id, jid, text) {
    const live = this.get(id);
    if (!live) return { sent: false, error: "missing_session" };
    if (!live.sock || live.status !== "connected") {
      return { sent: false, error: "not_connected", status: live.status };
    }
    try {
      await live.sock.sendMessage(jid, { text });
      return { sent: true };
    } catch (error) {
      logger.warn({ id, jid, error: String(error?.message || "") }, "send failed");
      return { sent: false, error: "send_failed", detail: String(error?.message || "") };
    }
  }

  async sendBulk(id, jids, text) {
    const live = this.get(id);
    if (!live) return { sent: 0, failed: [{ jid: "", error: "missing_session" }] };
    if (!live.sock || live.status !== "connected") {
      return { sent: 0, failed: jids.map((jid) => ({ jid, error: "not_connected" })) };
    }
    const failed = [];
    let sent = 0;
    for (const jid of jids) {
      const result = await this.send(id, jid, text);
      if (result.sent) {
        sent += 1;
      } else {
        failed.push({ jid, error: result.error || "send_failed" });
      }
      await new Promise((resolve) => setTimeout(resolve, config.bulkDelayMs));
    }
    return { sent, failed };
  }
}

const store = new SessionStore();

/** Converts an E.164 phone to a WhatsApp JID (e.g. +254712345678 -> 254712345678@s.whatsapp.net). */
function toWhatsAppJid(phone) {
  const digits = String(phone || "").replace(/[^\d]/g, "");
  if (!digits) return "";
  const cleaned = digits.replace(/^0+/, "");
  return `${cleaned}@s.whatsapp.net`;
}

module.exports = { store, toWhatsAppJid };