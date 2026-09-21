import { FC, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "react-toastify";

import LucideIcon from "@/components/LucideIcon";
import Modal from "@/components/ui/Modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApprovalTimeline } from "@/components/governance/ApprovalTimeline";
import { useApproval, useApprovalHistory, useApprovalAction } from "@/hooks/api/governance";
import { useCurrency } from "@/contexts/CurrencyContext";
import { getApiErrorMessage } from "@/lib/utils";
import { ApprovalRequest } from "@/services/governance";
import { SkeletonPage } from "@/components/Skeleton";

interface ApprovalDetailModalProps {
  approvalId: number | null;
  onClose: () => void;
  onChanged?: (updated: ApprovalRequest) => void;
}

const STATUS_STYLES: Record<string, string> = {
  PENDING: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  APPROVED: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300",
  AUTO_APPROVED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  PROCESSING: "bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300",
  COMPLETED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  REJECTED: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300",
  CANCELLED: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  EXPIRED: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  FAILED: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300",
};

/**
 * Full drill-down for one approval request: what is being decided, who is
 * deciding it and at which level, plus the append-only audit trail. Officers
 * and committee members can decide right here (approve / reject / cancel).
 */
export const ApprovalDetailModal: FC<ApprovalDetailModalProps> = ({
  approvalId,
  onClose,
  onChanged,
}) => {
  const { t } = useTranslation();
  const { formatMoney } = useCurrency();
  const { data: approval, isLoading } = useApproval(approvalId ?? undefined);
  const { data: history, isLoading: historyLoading } = useApprovalHistory(
    approvalId ?? undefined,
  );
  const decide = useApprovalAction();

  const [action, setAction] = useState<"approve" | "reject" | "cancel" | null>(null);
  const [reason, setReason] = useState("");

  const statusStyle = STATUS_STYLES[approval?.status ?? ""] ?? STATUS_STYLES.PENDING;
  const pending = approval?.status === "PENDING";
  const actionable = Boolean(approval?.can_act && pending);
  const cancellable = Boolean(approval?.can_cancel && pending);

  const decideError = useMemo(
    () => (decide.isError ? getApiErrorMessage(decide.error) : null),
    [decide.isError, decide.error],
  );

  const submit = () => {
    if (!approvalId || !action) return;
    decide.mutate(
      { approvalId, data: { action, reason: reason.trim() || undefined } },
      {
        onSuccess: (updated) => {
          toast.success(
            action === "approve"
              ? "Request approved."
              : action === "reject"
                ? "Request rejected."
                : "Request cancelled.",
          );
          setAction(null);
          setReason("");
          onChanged?.(updated);
          onClose();
        },
        onError: () => undefined, // surfaced via decideError banner
      },
    );
  };

  return (
    <Modal isOpen={Boolean(approvalId)} onClose={onClose} title="Approval request">
      {isLoading || !approval ? (
        <SkeletonPage />
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Badge variant="outline">#{approval.id}</Badge>
            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusStyle}`}>
              {approval.status_label ?? approval.status}
            </span>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900">
            <p className="text-xl font-semibold text-slate-900 dark:text-slate-50">
              {formatMoney(Number(approval.amount))}
            </p>
            <p className="mt-1 text-sm font-medium capitalize text-slate-700 dark:text-slate-300">
              {approval.request_type.replace("_", " ")}
              {approval.resource_description ? ` — ${approval.resource_description}` : ""}
            </p>
            <dl className="mt-3 grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Requested by</dt>
                <dd className="text-slate-900 dark:text-slate-50">{approval.requester_name}</dd>
              </div>
              {approval.group_name ? (
                <div>
                  <dt className="text-xs text-slate-500 dark:text-slate-400">Group</dt>
                  <dd className="text-slate-900 dark:text-slate-50">{approval.group_name}</dd>
                </div>
              ) : null}
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Required role</dt>
                <dd className="capitalize text-slate-900 dark:text-slate-50">
                  {approval.required_role || "Any officer"}
                  {approval.required_level ? ` · Level ${approval.required_level}` : ""}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Policy</dt>
                <dd className="text-slate-900 dark:text-slate-50">{approval.policy_version}</dd>
              </div>
              {approval.expires_at ? (
                <div>
                  <dt className="text-xs text-slate-500 dark:text-slate-400">Decision deadline</dt>
                  <dd className="text-slate-900 dark:text-slate-50">
                    {new Date(approval.expires_at).toLocaleString()}
                  </dd>
                </div>
              ) : null}
              {approval.decision_reason ? (
                <div className="sm:col-span-2">
                  <dt className="text-xs text-slate-500 dark:text-slate-400">Reason</dt>
                  <dd className="whitespace-pre-wrap text-slate-900 dark:text-slate-50">
                    {approval.decision_reason}
                  </dd>
                </div>
              ) : null}
            </dl>

            {approval.withdrawal ? (
              <div className="mt-4 rounded-xl border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  Withdrawal
                </p>
                <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1.5 sm:grid-cols-2">
                  <div>
                    <dt className="text-xs text-slate-500 dark:text-slate-400">Reference</dt>
                    <dd className="text-slate-900 dark:text-slate-50">
                      {approval.withdrawal.reference}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500 dark:text-slate-400">Member</dt>
                    <dd className="text-slate-900 dark:text-slate-50">
                      {approval.withdrawal.member_name}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500 dark:text-slate-400">Account</dt>
                    <dd className="text-slate-900 dark:text-slate-50">
                      {approval.withdrawal.account_number}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500 dark:text-slate-400">Network</dt>
                    <dd className="capitalize text-slate-900 dark:text-slate-50">
                      {approval.withdrawal.network}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500 dark:text-slate-400">
                      Available balance
                    </dt>
                    <dd className="text-slate-900 dark:text-slate-50">
                      {formatMoney(Number(approval.withdrawal.balance))}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500 dark:text-slate-400">Status</dt>
                    <dd className="text-slate-900 dark:text-slate-50">
                      {approval.withdrawal.status}
                    </dd>
                  </div>
                </dl>
                {approval.withdrawal.decline_reason ? (
                  <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">
                    Decline reason: {approval.withdrawal.decline_reason}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>

          {approval.steps?.length ? (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Approval chain
              </p>
              <div className="space-y-2">
                {approval.steps.map((step) => (
                  <div
                    key={step.level}
                    className="flex items-center justify-between rounded-xl border border-slate-200 px-3 py-2 text-sm dark:border-slate-800"
                  >
                    <div>
                      <p className="font-medium text-slate-900 dark:text-slate-50">
                        Level {step.level} · {step.role || "Any officer"}
                      </p>
                      {step.approved_by_name ? (
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {step.approved_by_name}
                          {step.reason ? ` — ${step.reason}` : ""}
                        </p>
                      ) : null}
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                        step.status === "APPROVED"
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                          : "bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                      }`}
                    >
                      {step.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {approval.rules_passed?.length ? (
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Checks passed
              </p>
              <div className="flex flex-wrap gap-1.5">
                {approval.rules_passed.map((rule) => (
                  <span
                    key={rule}
                    className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                  >
                    <LucideIcon name="Check" size={12} />
                    {rule.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          ) : null}

          <div className="border-t border-slate-200 pt-4 dark:border-slate-800">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              History
            </p>
            <ApprovalTimeline actions={history ?? []} isLoading={historyLoading} />
          </div>

          {actionable ? (
            <div className="space-y-3 border-t border-slate-200 pt-4 dark:border-slate-800">
              {action ? (
                <div className="space-y-3 rounded-xl border border-slate-200 p-3 dark:border-slate-800">
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400">
                    {action === "approve"
                      ? "Approval note (optional)"
                      : action === "reject"
                        ? "Reason for rejection (recommended)"
                        : "Reason for cancellation (optional)"}
                  </label>
                  <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    rows={2}
                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-50"
                  />
                  {decideError ? (
                    <p className="text-sm text-rose-600 dark:text-rose-400">{decideError}</p>
                  ) : null}
                  <div className="flex gap-2">
                    <Button
                      variant="default"
                      disabled={decide.isPending}
                      onClick={submit}
                      className="flex-1"
                    >
                      {decide.isPending ? "Working…" : "Confirm"}
                    </Button>
                    <Button
                      variant="outline"
                      disabled={decide.isPending}
                      onClick={() => {
                        setAction(null);
                        setReason("");
                      }}
                    >
                      Back
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap gap-2">
                  <Button variant="default" onClick={() => setAction("approve")}>
                    <LucideIcon name="ThumbsUp" size={16} className="mr-1.5" />
                    Approve
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={() => setAction("reject")}
                  >
                    <LucideIcon name="ThumbsDown" size={16} className="mr-1.5" />
                    Reject
                  </Button>
                  {cancellable ? (
                    <Button variant="outline" onClick={() => setAction("cancel")}>
                      <LucideIcon name="Ban" size={16} className="mr-1.5" />
                      Cancel
                    </Button>
                  ) : null}
                </div>
              )}
            </div>
          ) : (
            <p className="border-t border-slate-200 pt-3 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
              {t("governance.noDecision", "This request is not awaiting your decision.")}
            </p>
          )}
        </div>
      )}
    </Modal>
  );
};

export default ApprovalDetailModal;