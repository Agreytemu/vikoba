import { FC } from "react";
import { useTranslation } from "react-i18next";

import LucideIcon from "@/components/LucideIcon";
import { ApprovalAction } from "@/services/governance";

const ACTION_ICONS: Record<string, string> = {
  submit: "FilePlus2",
  auto_approve: "BadgeCheck",
  review_required: "Clock",
  approve: "ThumbsUp",
  reject: "ThumbsDown",
  cancel: "Ban",
  expire: "TimerOff",
  mark_processing: "Send",
  complete: "CheckCircle2",
  fail: "XCircle",
  policy_changed: "Shield",
};

const ACTION_LABELS: Record<string, string> = {
  submit: "Submitted",
  auto_approve: "Auto-approved",
  review_required: "Sent for review",
  approve: "Approved",
  reject: "Rejected",
  cancel: "Cancelled",
  expire: "Expired",
  mark_processing: "Payment dispatched",
  complete: "Completed",
  fail: "Failed",
  policy_changed: "Policy updated",
};

/**
 * Read-only audit trail of system + human decisions. Faithful to the backend's
 * append-only ApprovalAction rows — later decisions never mutate earlier ones.
 */
export const ApprovalTimeline: FC<{ actions: ApprovalAction[]; isLoading?: boolean }> = ({
  actions,
  isLoading,
}) => {
  const { t } = useTranslation();

  if (isLoading) {
    return <p className="text-sm text-slate-500">{t("common.loading", "Loading…")}</p>;
  }
  if (!actions?.length) {
    return <p className="text-sm text-slate-500">No activity recorded yet.</p>;
  }

  return (
    <ol className="space-y-4">
      {actions.map((action, index) => (
        <li key={`${action.created_at}-${index}`} className="relative flex gap-3">
          <div className="flex flex-col items-center">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              <LucideIcon name={ACTION_ICONS[action.action] ?? "Dot"} size={16} />
            </span>
            {index < actions.length - 1 && (
              <span className="mt-1 w-px flex-1 bg-slate-200 dark:bg-slate-700" />
            )}
          </div>
          <div className="flex-1 pb-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="text-sm font-semibold text-slate-900 dark:text-slate-50">
                {ACTION_LABELS[action.action] ?? action.action}
              </span>
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  action.actor_type === "SYSTEM"
                    ? "bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300"
                    : "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300"
                }`}
              >
                {action.actor_type === "SYSTEM" ? "System" : "Officer"}
              </span>
            </div>
            {action.reason ? (
              <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-400">{action.reason}</p>
            ) : null}
            <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
              {action.actor_name ? `${action.actor_name} · ` : ""}
              {new Date(action.created_at).toLocaleString()}
              {action.from_status && action.to_status ? (
                <span className="ml-1">({action.from_status} → {action.to_status})</span>
              ) : null}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
};

export { ACTION_LABELS };