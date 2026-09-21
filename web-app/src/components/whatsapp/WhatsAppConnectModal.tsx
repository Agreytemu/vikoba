import { FC, useEffect, useState } from "react";
import { toast } from "react-toastify";

import Modal from "@/components/ui/Modal";
import { Button } from "@/components/ui/button";
import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";
import FormInput from "@/components/FormInput";
import {
  useCreateWhatsAppSession,
  useGetWhatsAppSessions,
  usePairWhatsAppSession,
  useRescanSession,
  useSessionStatus,
} from "@/hooks/api/whatsapp";
import { WhatsAppSession } from "@/services/whatsapp";
import { getApiErrorMessage } from "@/lib/utils";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  /** Provide a group id to pair the chairperson's device for that group. */
  groupId?: number;
  /** Provide an existing session id to rescan/show it instead of creating one. */
  sessionId?: string;
  onConnected?: (phone: string) => void;
  defaultDisplayName?: string;
}

const STATUS_LABEL: Record<string, string> = {
  connecting: "Connecting to WhatsApp…",
  awaiting_pairing: "Scan the QR code with WhatsApp",
  connected: "Device connected",
  disconnected: "Disconnected — waiting to reconnect",
  logged_out: "Device logged out — pair it again",
  error: "Connection error — please retry",
};

const WhatsAppConnectModal: FC<Props> = ({
  isOpen,
  onClose,
  groupId,
  sessionId: propSessionId,
  onConnected,
  defaultDisplayName,
}) => {
  const owner = groupId ? "CHAIR" : "ADMIN";
  const { data: sessions } = useGetWhatsAppSessions(isOpen);
  const createSession = useCreateWhatsAppSession();
  const rescanSession = useRescanSession();
  const [sessionId, setSessionId] = useState<string>();
  const [phone, setPhone] = useState("");
  const [numberLabel, setNumberLabel] = useState("");
  const [pairingCode, setPairingCode] = useState("");
  const [showCodeForm, setShowCodeForm] = useState(false);

  const scopeSession: WhatsAppSession | undefined = sessions?.find((s) =>
    owner === "ADMIN" ? s.owner_type === "ADMIN" : s.group === groupId,
  );
  const activeSessionId = propSessionId ?? sessionId ?? scopeSession?.session_id;

  const statusQuery = useSessionStatus(activeSessionId, 1500);
  const currentStatus = statusQuery.data?.status ?? scopeSession?.status;
  const pairSession = usePairWhatsAppSession(activeSessionId);

  useEffect(() => {
    if (statusQuery.data?.status === "connected" && statusQuery.data?.phone) {
      onConnected?.(statusQuery.data.phone);
    }
  }, [statusQuery.data?.status, statusQuery.data?.phone, onConnected]);

  // Show a freshly requested code; also pick up an existing one from polling.
  const visibleCode =
    pairingCode ||
    (currentStatus === "awaiting_pairing" ? statusQuery.data?.pairing_code ?? "" : "");

  const visibleQr =
    currentStatus === "awaiting_pairing" ? statusQuery.data?.qr ?? "" : "";

  useEffect(() => {
    if (!activeSessionId) {
      setPairingCode("");
      setPhone("");
    }
  }, [activeSessionId]);

  const handleStart = () => {
    // If we already point at an existing session, rescan it in place instead of
    // spinning up a brand new one — prevents sessions piling up.
    if (activeSessionId) {
      rescanSession.mutate(activeSessionId, {
        onError: (error: unknown) =>
          toast.error(getApiErrorMessage(error), { autoClose: 4000 }),
      });
      return;
    }
    createSession.mutate(
      {
        owner_type: owner,
        group: groupId ?? null,
        display_name:
          owner === "ADMIN"
            ? numberLabel.trim() || "Admin device"
            : defaultDisplayName,
      },
      {
        onSuccess: (session) => setSessionId(session.session_id),
        onError: (error) =>
          toast.error(getApiErrorMessage(error), { autoClose: 4000 }),
      },
    );
  };

  const handleConnectAnother = () => {
    setSessionId(undefined);
    setNumberLabel("");
    setPhone("");
    setPairingCode("");
    setShowCodeForm(false);
  };

  const handlePairCode = (e: React.FormEvent) => {
    e.preventDefault();
    if (!phone.trim()) return;
    pairSession.mutate(phone.trim(), {
      onSuccess: (result) => {
        if (result.ok && result.pairing) {
          setPairingCode(result.pairing);
        } else {
          toast.error(result.detail || result.error || "Could not get a pairing code.", {
            autoClose: 5000,
          });
        }
      },
      onError: (error) =>
        toast.error(getApiErrorMessage(error), { autoClose: 4000 }),
    });
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={groupId ? "Pair chairperson's WhatsApp" : "Connect a WhatsApp device"}
    >
      <div className="text-sm text-slate-600 dark:text-slate-300">
        {!activeSessionId ? (
          <div className="space-y-4 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-green-100 text-green-800 dark:bg-green-950/60 dark:text-green-300">
              <LucideIcon name="MessageCircle" size={26} />
            </div>
            <p>
              {groupId
                ? "Receipts for this group's confirmed contributions will be sent from the chairperson's WhatsApp. Scan the QR with that phone."
                : "Generate a QR code, then scan it with the WhatsApp account you want to link. You can connect more than one device."}
            </p>

            {owner === "ADMIN" ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleStart();
                }}
                className="mx-auto max-w-sm space-y-3"
              >
                <FormInput
                  type="tel"
                  label="WhatsApp number for this device"
                  placeholder="+255712345678"
                  value={numberLabel}
                  onChange={(e) => setNumberLabel(e.target.value)}
                />
                <Button type="submit" disabled={createSession.isPending}>
                  {createSession.isPending ? <Spinner /> : "Generate QR code"}
                </Button>
              </form>
            ) : (
              <Button
                type="button"
                onClick={handleStart}
                disabled={createSession.isPending}
              >
                {createSession.isPending ? <Spinner /> : "Generate QR code"}
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-4 text-center">
            <p className="font-medium">
              {STATUS_LABEL[currentStatus ?? "connecting"] ?? currentStatus}
            </p>

            {currentStatus === "connecting" && (
              <div className="flex items-center justify-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                <Spinner /> We are still getting the WhatsApp connection ready…
              </div>
            )}

            {currentStatus === "connected" ? (
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                <LucideIcon name="Check" size={26} />
              </div>
            ) : null}

            {currentStatus === "connected" && statusQuery.data?.phone && (
              <p className="text-sm">
                Connected as <span className="font-semibold">+{statusQuery.data.phone}</span>
              </p>
            )}

            {currentStatus === "connected" && owner === "ADMIN" && (
              <Button type="button" variant="outline" onClick={handleConnectAnother}>
                Connect another device
              </Button>
            )}

            {currentStatus === "awaiting_pairing" && (
              <div className="space-y-4">
                {visibleQr ? (
                  <div className="mx-auto max-w-sm space-y-3">
                    <img
                      src={visibleQr}
                      alt="WhatsApp QR code"
                      className="mx-auto h-60 w-60 rounded-lg border border-slate-200 bg-white p-2 dark:border-slate-700"
                    />
                    <ol className="space-y-1 text-left text-xs text-slate-500 dark:text-slate-400">
                      <li>
                        <span className="font-medium text-slate-700 dark:text-slate-200">1.</span> Open{" "}
                        <em>WhatsApp</em> on your phone.
                      </li>
                      <li>
                        <span className="font-medium text-slate-700 dark:text-slate-200">2.</span> Go to{" "}
                        <em>Settings</em> &gt; <em>Linked devices</em> &gt; <em>Link a device</em>.
                      </li>
                      <li>
                        <span className="font-medium text-slate-700 dark:text-slate-200">3.</span> Scan this QR
                        code with your phone camera.
                      </li>
                    </ol>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Tip: open this on a computer or tablet and scan it with your
                      phone. The code refreshes automatically — if it changes, just
                      scan the latest one. You have a few minutes to scan; after
                      that it expires and a new code appears.
                    </p>
                    <div className="flex flex-wrap items-center justify-center gap-4">
                      <button
                        type="button"
                        onClick={handleStart}
                        className="text-xs text-blue-600 underline dark:text-blue-400"
                      >
                        Refresh QR code
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowCodeForm(true)}
                        className="text-xs text-blue-600 underline dark:text-blue-400"
                      >
                        Can’t scan? Link with a pairing code instead
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <Spinner /> Waiting for the WhatsApp QR code…
                  </div>
                )}

                {showCodeForm && (
                  <div className="space-y-4 border-t border-slate-100 pt-4 dark:border-slate-800">
                    <ol className="mx-auto max-w-sm space-y-1 text-left text-xs text-slate-500 dark:text-slate-400">
                      <li>
                        <span className="font-medium text-slate-700 dark:text-slate-200">1.</span> Enter the
                        WhatsApp number of this phone (with country code, e.g. +2557…).
                      </li>
                      <li>
                        <span className="font-medium text-slate-700 dark:text-slate-200">2.</span> On that phone
                        open WhatsApp &gt; <em>Linked devices</em> &gt;{" "}
                        <em>Link with phone number instead</em>.
                      </li>
                      <li>
                        <span className="font-medium text-slate-700 dark:text-slate-200">3.</span> Get the code and
                        type it into the phone.
                      </li>
                    </ol>

                    <form
                      onSubmit={handlePairCode}
                      className="mx-auto flex max-w-sm items-end gap-2"
                    >
                      <FormInput
                        type="tel"
                        label="WhatsApp number"
                        placeholder="+255712345678"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        className="flex-1"
                      />
                      <Button type="submit" variant="secondary" disabled={pairSession.isPending || !phone.trim()}>
                        {pairSession.isPending ? <Spinner /> : "Get code"}
                      </Button>
                    </form>

                    {visibleCode && (
                      <div className="mx-auto max-w-sm rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 dark:border-blue-900 dark:bg-blue-950/40">
                        <p className="mb-2 text-xs text-blue-700 dark:text-blue-300">
                          Enter this pairing code on the phone:
                        </p>
                        <p className="text-2xl font-bold tracking-widest text-blue-900 dark:text-blue-100">
                          {visibleCode}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {(currentStatus === "logged_out" ||
              currentStatus === "error" ||
              currentStatus === "disconnected") && (
              <Button type="button" variant="outline" onClick={handleStart} disabled={createSession.isPending}>
                {createSession.isPending ? <Spinner /> : "Regenerate QR code"}
              </Button>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
};

export default WhatsAppConnectModal;