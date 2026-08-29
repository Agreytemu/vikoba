import { FC, useState } from "react";
import { toast } from "react-toastify";

import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";
import { Button } from "@/components/ui/button";
import FormInput from "@/components/FormInput";
import WhatsAppConnectModal from "@/components/whatsapp/WhatsAppConnectModal";
import CountryPhoneInput from "@/components/CountryPhoneInput";
import {
  useBulkSendMessage,
  useGetWhatsAppSessions,
  useRemoveSession,
  useRescanSession,
  useSendTestMessage,
  useSetPrimarySession,
} from "@/hooks/api/whatsapp";
import { useGetMyGroups } from "@/hooks/api/groups";
import { getApiErrorMessage } from "@/lib/utils";

const STATUS_PILL: Record<string, string> = {
  connected: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300",
  awaiting_pairing: "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300",
  scanning: "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300",
  connecting: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  disconnected: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
  logged_out: "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300",
  error: "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300",
};

export const WhatsApp: FC = () => {
  const { data: sessions, refetch } = useGetWhatsAppSessions();
  const { data: myGroups } = useGetMyGroups();
  const setPrimary = useSetPrimarySession();
  const removeSession = useRemoveSession();
  const rescan = useRescanSession();
  const [connectOpen, setConnectOpen] = useState(false);
  const [rescanId, setRescanId] = useState<string | undefined>();

  const handleOpenConnect = () => {
    setRescanId(undefined);
    setConnectOpen(true);
  };

  const handleRescan = (sessionId: string) => {
    rescan.mutate(sessionId, {
      onError: (error) => toast.error(getApiErrorMessage(error), { autoClose: 4000 }),
    });
    setRescanId(sessionId);
    setConnectOpen(true);
  };

  const manageable = (sessions ?? []).filter((s) => s.can_manage);
  const groupDevices = (sessions ?? []).filter(
    (s) => s.owner_type === "CHAIR" && !s.can_manage,
  );
  const hasAny = (sessions ?? []).length > 0;

  return (
    <div className="mx-auto max-w-4xl p-4 md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold">
            <LucideIcon name="MessageCircle" size={22} /> WhatsApp gateway
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Your device for verification codes; group chairperson devices for receipts.
          </p>
        </div>
        <Button type="button" onClick={handleOpenConnect}>
          <LucideIcon name="Plus" size={16} className="mr-1" /> Connect device
        </Button>
      </div>

      {!hasAny ? (
        <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-10 text-center dark:border-slate-800 dark:bg-slate-900">
          <p className="text-sm text-slate-500 dark:text-slate-400">
            No devices yet. Connect the primary device to start delivering
            verification codes and receipts over WhatsApp.
          </p>
        </div>
      ) : (
        <>
          {manageable.length > 0 && (
            <section className="mt-6">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Your devices
              </h2>
              <div className="space-y-4">
                {manageable.map((session) => (
                  <DeviceCard
                    key={session.id}
                    sessionId={session.session_id}
                    displayName={session.display_name}
                    ownerType={session.owner_type}
                    status={session.status}
                    phone={session.phone}
                    isPrimary={session.is_primary}
                    canManage
                    onSetPrimary={() =>
                      setPrimary.mutate(
                        { sessionId: session.session_id, isPrimary: !session.is_primary },
                        {
                          onError: (error) => toast.error(getApiErrorMessage(error), { autoClose: 4000 }),
                        },
                      )
                    }
                    onRemove={() =>
                      window.confirm("Remove this device? It will be disconnected.") &&
                      removeSession.mutate(session.session_id, {
                        onSuccess: () => refetch(),
                        onError: (error) => toast.error(getApiErrorMessage(error), { autoClose: 4000 }),
                      })
                    }
                    onRescan={handleRescan}
                    groupOptions={myGroups ?? []}
                  />
                ))}
              </div>
            </section>
          )}

          {groupDevices.length > 0 && (
            <section className="mt-8">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                Group chairperson devices
              </h2>
              <p className="mb-3 text-xs text-slate-500 dark:text-slate-400">
                These belong to the chairperson of each group. They pair and manage them from
                their group page — you can only see their status here.
              </p>
              <div className="space-y-4">
                {groupDevices.map((session) => (
                  <DeviceCard
                    key={session.id}
                    sessionId={session.session_id}
                    displayName={session.display_name || "Chairperson device"}
                    ownerType={session.owner_type}
                    status={session.status}
                    phone={session.phone}
                    isPrimary={session.is_primary}
                    groupName={session.group_name}
                    canManage={false}
                    onSetPrimary={() => {}}
                    onRemove={() => {}}
                    onRescan={() => {}}
                    groupOptions={[]}
                  />
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <WhatsAppConnectModal
        isOpen={connectOpen}
        onClose={() => setConnectOpen(false)}
        sessionId={rescanId}
      />
    </div>
  );
};

const DeviceCard = ({
  sessionId,
  displayName,
  ownerType,
  status,
  phone,
  isPrimary,
  canManage,
  groupName,
  onSetPrimary,
  onRemove,
  onRescan,
  groupOptions,
}: {
  sessionId: string;
  displayName: string;
  ownerType: string;
  status: string;
  phone: string;
  isPrimary: boolean;
  canManage: boolean;
  groupName?: string | null;
  onSetPrimary: () => void;
  onRemove: () => void;
  onRescan: (sessionId: string) => void;
  groupOptions: { id: number; name: string }[];
}) => {
  const [expanded, setExpanded] = useState(false);
  const [testForm, setTestForm] = useState({ to: "", text: "Hello from Vikoba Kidigitali!" });
  const [bulkForm, setBulkForm] = useState({ groupId: "", phones: "", text: "" });
  const sendTest = useSendTestMessage(sessionId);
  const bulkSend = useBulkSendMessage(sessionId);

  const isConnected = status === "connected";

  const handleTest = (e: React.FormEvent) => {
    e.preventDefault();
    if (!testForm.to) return;
    sendTest.mutate(
      { to: testForm.to, text: testForm.text },
      {
        onSuccess: (result) => {
          if (result.ok) toast.success("Test message sent.", { autoClose: 3000 });
          else toast.error(`Send failed: ${result.error}${result.detail ? ` — ${result.detail}` : ""}`, { autoClose: 5000 });
        },
        onError: (error) => toast.error(getApiErrorMessage(error), { autoClose: 4000 }),
      },
    );
  };

  const handleBulk = (e: React.FormEvent) => {
    e.preventDefault();
    const phones = bulkForm.phones
      .split(/[\n,]+/)
      .map((p) => p.trim())
      .filter(Boolean);
    if (!bulkForm.text || (!bulkForm.groupId && phones.length === 0)) return;
    bulkSend.mutate(
      {
        text: bulkForm.text,
        group_id: bulkForm.groupId ? Number(bulkForm.groupId) : undefined,
        phones,
      },
      {
        onSuccess: (result) => {
          if (result.ok) toast.success(`Broadcast sent to ${result.sent} recipient(s).`, { autoClose: 4000 });
          else
            toast.error(
              `Broadcast finished with failures: ${result.sent} sent, ${result.failed.length} failed.`,
              { autoClose: 6000 },
            );
        },
        onError: (error) => toast.error(getApiErrorMessage(error), { autoClose: 4000 }),
      },
    );
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full ${
              isConnected
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300"
            }`}
          >
            <LucideIcon name="Phone" size={18} />
          </span>
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold">
              {displayName || ownerType === "ADMIN" ? "Primary admin device" : "Chairperson device"}
              {isPrimary && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-800 dark:bg-blue-950/60 dark:text-blue-300">
                  Primary
                </span>
              )}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {phone ? `+${phone} · ` : ""}
              {sessionId}
              {status === "awaiting_pairing" ? " · awaiting scan" : ""}
              {!canManage && groupName ? ` · ${groupName}` : ""}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_PILL[status] ?? ""}`}>
            {status}
          </span>
          {canManage && (
            <>
              <Button type="button" size="sm" variant="outline" onClick={() => setExpanded((v) => !v)}>
                {expanded ? "Close" : "Actions"}
              </Button>
              {!isConnected && (
                <Button type="button" size="sm" variant="ghost" onClick={() => onRescan(sessionId)}>
                  Rescan QR
                </Button>
              )}
              {!isPrimary && (
                <Button type="button" size="sm" variant="ghost" onClick={onSetPrimary}>
                  Set primary
                </Button>
              )}
            </>
          )}
        </div>
      </div>

      {canManage && expanded && (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-slate-100 p-4 dark:border-slate-800">
            <h3 className="mb-3 text-sm font-semibold">Send a test message</h3>
            <form onSubmit={handleTest} className="space-y-3">
              <CountryPhoneInput
                id="test-to"
                label="Phone (with country code)"
                value={testForm.to}
                onChange={(v) => setTestForm({ ...testForm, to: v })}
                placeholder="712 345 678"
              />
              <FormInput
                type="text"
                label="Message"
                value={testForm.text}
                onChange={(e) => setTestForm({ ...testForm, text: e.target.value })}
              />
              <Button type="submit" size="sm" disabled={!isConnected || sendTest.isPending} className="w-full">
                {sendTest.isPending ? <Spinner /> : "Send"}
              </Button>
            </form>
          </div>

          <div className="rounded-xl border border-slate-100 p-4 dark:border-slate-800">
            <h3 className="mb-3 text-sm font-semibold">Broadcast</h3>
            <form onSubmit={handleBulk} className="space-y-3">
              {groupOptions.length > 0 && (
                <div>
                  <label className="mb-1 block text-xs text-slate-500 dark:text-slate-400">
                    Group (active members)
                  </label>
                  <select
                    className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                    value={bulkForm.groupId}
                    onChange={(e) => setBulkForm({ ...bulkForm, groupId: e.target.value })}
                  >
                    <option value="">— None —</option>
                    {groupOptions.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <FormInput
                type="text"
                label="Or phone numbers (comma separated)"
                value={bulkForm.phones}
                placeholder="+2547…, +2547…"
                onChange={(e) => setBulkForm({ ...bulkForm, phones: e.target.value })}
              />
              <FormInput
                type="text"
                label="Message"
                value={bulkForm.text}
                onChange={(e) => setBulkForm({ ...bulkForm, text: e.target.value })}
              />
              <Button type="submit" size="sm" disabled={!isConnected || bulkSend.isPending} className="w-full">
                {bulkSend.isPending ? <Spinner /> : "Broadcast"}
              </Button>
            </form>
          </div>
        </div>
      )}

      {canManage && !(isConnected || isPrimary) && (
        <div className="mt-3 flex justify-end">
          <Button type="button" size="sm" variant="destructive" onClick={onRemove}>
            Remove device
          </Button>
        </div>
      )}
    </div>
  );
};