import api from "@/lib/api";

export interface WhatsAppSession {
  id: number;
  session_id: string;
  owner_type: "ADMIN" | "CHAIR";
  group: number | null;
  group_name: string | null;
  display_name: string;
  status: string;
  status_display: string;
  phone: string;
  is_primary: boolean;
  last_error: string;
  can_manage: boolean;
  owner_email?: string;
  created_at: string;
  updated_at: string;
}

export interface WhatsAppSessionStatus extends WhatsAppSession {
  pairing_code?: string | null;
  qr?: string | null;
}

export interface PairingResult {
  ok: boolean;
  pairing?: string;
  error?: string;
  detail?: string;
}

export interface CreateWhatsAppSessionPayload {
  owner_type: "ADMIN" | "CHAIR";
  group?: number | null;
  display_name?: string;
}

export interface SendTestResult {
  ok: boolean;
  error?: string;
  detail?: string | null;
}

export interface BulkSendResult {
  ok: boolean;
  sent: number;
  failed: Array<{ jid: string; error: string }>;
  error?: string;
}

export const whatsappService = {
  listSessions: () =>
    api.get("/whatsapp/sessions/") as Promise<WhatsAppSession[]>,

  createSession: (data: CreateWhatsAppSessionPayload) =>
    api.post("/whatsapp/sessions/", data) as Promise<WhatsAppSession>,

  sessionStatus: (sessionId: string) =>
    api.get(`/whatsapp/sessions/${sessionId}/`) as Promise<WhatsAppSessionStatus>,

  pairSession: (sessionId: string, phone: string) =>
    api.post(`/whatsapp/sessions/${sessionId}/pair/`, { phone }) as Promise<PairingResult>,

  setPrimary: (sessionId: string, isPrimary: boolean) =>
    api.patch(`/whatsapp/sessions/${sessionId}/`, { is_primary: isPrimary }) as Promise<WhatsAppSession>,

  removeSession: (sessionId: string) =>
    api.delete(`/whatsapp/sessions/${sessionId}/`) as Promise<{ detail: string }>,

  sendTest: (sessionId: string, to: string, text: string) =>
    api.post(`/whatsapp/sessions/${sessionId}/send-test/`, { to, text }) as Promise<SendTestResult>,

  bulkSend: (
    sessionId: string,
    payload: { text: string; group_id?: number; phones?: string[] },
  ) => api.post(`/whatsapp/sessions/${sessionId}/bulk/`, payload) as Promise<BulkSendResult>,
};