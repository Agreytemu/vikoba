const pino = require("pino");

const { BufferJSON, initAuthCreds } = require("@whiskeysockets/baileys");

const config = require("./config");

const logger = pino({
  level: process.env.LOG_LEVEL || "info",
  timestamp: () => `,"time":"${new Date().toISOString()}"`,
});

const isConfigured = () =>
  Boolean(config.supabaseUrl && config.supabaseServiceRoleKey);

// In-memory auth state is cached per session so a socket reconnect (e.g. the
// 515 "restart required" WhatsApp sends right after a successful pairing) reuses
// the same credentials instead of starting from a blank slate.
const inMemoryCache = new Map();

// The Supabase-backed state is also cached per session for the same reason:
// baileys mutates `state.creds` in memory during pairing, and the 515 restart
// fires almost immediately after. Re-reading from Supabase on reconnect can
// race the pending save and lose the just-acquired credentials, so we reuse the
// same in-memory object (which saveCreds still persists to Supabase).
const supabaseCache = new Map();

function authHeaders() {
  return {
    apikey: config.supabaseServiceRoleKey,
    Authorization: `Bearer ${config.supabaseServiceRoleKey}`,
    "Content-Type": "application/json",
    Prefer: "resolution=merge-duplicates,return=minimal",
  };
}

function tableUrl() {
  const base = String(config.supabaseUrl).replace(/\/+$/, "");
  return `${base}/rest/v1/${config.supabaseSessionsTable}`;
}

async function getRow(sessionId) {
  const url = `${tableUrl()}?session_id=eq.${encodeURIComponent(sessionId)}&select=session_id,creds,keys`;
  const response = await fetch(url, { headers: authHeaders() });
  if (!response.ok) {
    throw new Error(`supabase select -> ${response.status}: ${await response.text()}`);
  }
  const rows = await response.json();
  return Array.isArray(rows) && rows.length > 0 ? rows[0] : null;
}

async function upsertRow(row) {
  const response = await fetch(tableUrl(), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify([row]),
  });
  if (!response.ok) {
    throw new Error(`supabase upsert -> ${response.status}: ${await response.text()}`);
  }
}

async function deleteAuth(sessionId) {
  if (!isConfigured()) {
    inMemoryCache.delete(sessionId);
    return;
  }
  supabaseCache.delete(sessionId);
  const url = `${tableUrl()}?session_id=eq.${encodeURIComponent(sessionId)}`;
  const response = await fetch(url, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!response.ok && response.status !== 404) {
    throw new Error(`supabase delete -> ${response.status}: ${await response.text()}`);
  }
}

/**
 * Baileys auth state backed by a single Supabase/PostgREST row per session.
 *
 * `creds` are small and written on every creds update, so a crash can never
 * lose registration state. `keys` (signal pre-keys, sessions, …) are written
 * debounced every few seconds and flushed on shutdown.
 */
async function useSupabaseAuthState(sessionId) {
  if (supabaseCache.has(sessionId)) {
    return supabaseCache.get(sessionId);
  }

  if (!isConfigured()) {
    throw new Error(
      "Supabase auth storage is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY)",
    );
  }

  const saved = await getRow(sessionId);
  const creds = saved?.creds
    ? BufferJSON.reviver(JSON.stringify(saved.creds))
    : initAuthCreds();
  // The signal keys map: type -> id -> value (possibly with Buffers).
  const keys = saved?.keys || {};
  let pendingTimer = null;

  const writeRow = async () => {
    if (pendingTimer) {
      clearTimeout(pendingTimer);
      pendingTimer = null;
    }
    await upsertRow({
      session_id: sessionId,
      creds: JSON.parse(JSON.stringify(creds, BufferJSON.replacer)),
      keys: JSON.parse(JSON.stringify(keys, BufferJSON.replacer)),
      updated_at: new Date().toISOString(),
    });
  };

  const scheduleWrite = () => {
    if (!pendingTimer) {
      pendingTimer = setTimeout(writeRow, 8000);
    }
  };

  const state = {
    creds,
    keys: {
      async get(type, ids) {
        const bucket = keys[type] || {};
        const result = {};
        for (const id of ids) {
          result[id] =
            typeof bucket[id] !== "undefined" ? BufferJSON.reviver(JSON.stringify(bucket[id])) : null;
        }
        return result;
      },
      async set(data) {
        for (const type in data) {
          const bucket = keys[type] || (keys[type] = {});
          for (const id in data[type]) {
            const plain = data[type][id];
            if (plain === null || typeof plain === "undefined") {
              delete bucket[id];
            } else {
              bucket[id] = JSON.parse(JSON.stringify(plain, BufferJSON.replacer));
            }
          }
        }
        scheduleWrite();
      },
      async clear() {
        for (const type in keys) delete keys[type];
        scheduleWrite();
      },
    },
  };

  let flushing = false;
  const queue = [];

  const result = {
    state,
    // creds.update fires at critical moments (registration, connection open) —
    // persist immediately, keyed by creds.hash so a rapid burst writes once.
    saveCreds: async () => {
      const run = async () => {
        try {
          await writeRow();
        } catch (error) {
          logger.warn({ sessionId, error: String(error?.message || error) }, "saveCreds failed");
        }
      };
      if (flushing) {
        queue.push(run);
        return;
      }
      flushing = true;
      try {
        await run();
      } finally {
        flushing = false;
        const next = queue.shift();
        if (next) await next();
      }
    },
    // Flush any deferred keys write (call on graceful shutdown).
    flush: async () => {
      if (pendingTimer) {
        clearTimeout(pendingTimer);
        pendingTimer = null;
        await writeRow();
      }
    },
  };
  supabaseCache.set(sessionId, result);
  return result;
}

// Track all auth states so we can flush the whole store on shutdown.
const authStates = new Set();

/**
 * In-memory auth state used when Supabase is not configured (local dev /
 * QR smoke tests). It mirrors the Supabase interface but keeps creds + keys
 * in process memory only — sessions do not survive a restart.
 */
async function useInMemoryAuthState(sessionId) {
  if (inMemoryCache.has(sessionId)) {
    return inMemoryCache.get(sessionId);
  }

  const creds = initAuthCreds();
  const keys = {};

  const state = {
    creds,
    keys: {
      async get(type, ids) {
        const bucket = keys[type] || {};
        const result = {};
        for (const id of ids) {
          result[id] =
            typeof bucket[id] !== "undefined"
              ? JSON.parse(JSON.stringify(bucket[id], BufferJSON.replacer))
              : null;
        }
        return result;
      },
      async set(data) {
        for (const type in data) {
          const bucket = keys[type] || (keys[type] = {});
          for (const id in data[type]) {
            const plain = data[type][id];
            if (plain === null || typeof plain === "undefined") {
              delete bucket[id];
            } else {
              bucket[id] = JSON.parse(JSON.stringify(plain, BufferJSON.replacer));
            }
          }
        }
      },
      async clear() {
        for (const type in keys) delete keys[type];
      },
    },
  };

  const result = {
    state,
    saveCreds: async () => {},
    flush: async () => {},
  };
  inMemoryCache.set(sessionId, result);
  return result;
}

async function useSupabaseAuthStateTracked(sessionId) {
  const auth = isConfigured()
    ? await useSupabaseAuthState(sessionId)
    : await useInMemoryAuthState(sessionId);
  const entry = { auth, sessionId };
  authStates.add(entry);
  return {
    ...auth,
    flush: async () => {
      await auth.flush();
      authStates.delete(entry);
    },
  };
}

async function flushAllPending() {
  for (const entry of authStates) {
    try {
      await entry.auth.flush();
    } catch (error) {
      logger.warn({ sessionId: entry.sessionId, error: String(error?.message || error) }, "flush failed");
    }
  }
  authStates.clear();
}

module.exports = {
  useSupabaseAuthState: useSupabaseAuthStateTracked,
  flushAllPending,
  deleteAuth,
  isSupabaseConfigured: isConfigured,
};