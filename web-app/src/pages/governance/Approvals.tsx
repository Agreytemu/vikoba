import { FC, useMemo, useState } from "react";

import LucideIcon from "@/components/LucideIcon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SkeletonPage } from "@/components/Skeleton";
import ApprovalDetailModal from "@/components/governance/ApprovalDetailModal";
import GroupWithdrawalPolicies from "@/components/governance/GroupWithdrawalPolicies";
import { useApprovals } from "@/hooks/api/governance";
import { useApproverAccess } from "@/hooks/useApproverAccess";
import { useCurrency } from "@/contexts/CurrencyContext";
import { getApiErrorMessage } from "@/lib/utils";
import { ApprovalRequest } from "@/services/governance";

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

const TYPE_OPTIONS = [
  { value: "", label: "All types" },
  { value: "WITHDRAWAL", label: "Withdrawals" },
  { value: "CONTRIBUTION", label: "Contributions" },
  { value: "LOAN", label: "Loans" },
  { value: "PAYMENT", label: "Payments" },
];

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "PENDING", label: "Pending" },
  { value: "APPROVED,AUTO_APPROVED", label: "Approved" },
  { value: "PROCESSING,COMPLETED", label: "Processing / done" },
  { value: "REJECTED", label: "Rejected" },
  { value: "CANCELLED", label: "Cancelled" },
  { value: "EXPIRED", label: "Expired" },
  { value: "FAILED", label: "Failed" },
];

/**
 * Officer & committee approvals workspace. Lists pending requests first, with
 * history and per-group withdrawal-policy tabs. The backend authorises every
 * decision — invisible approvals or cross-group access are rejected there.
 */
const Approvals: FC = () => {
  const { formatMoney } = useCurrency();
  const { canAccessApprovals, isLoading } = useApproverAccess();

  const [tab, setTab] = useState<"inbox" | "history" | "policies">("inbox");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("PENDING");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data: approvals, isLoading: listLoading, isError, error, refetch } = useApprovals({
    type: typeFilter || undefined,
    status: statusFilter || undefined,
  });

  const rows = useMemo(() => approvals ?? [], [approvals]);

  if (isLoading) {
    return <SkeletonPage />;
  }

  if (!canAccessApprovals) {
    return (
      <div className="mx-auto w-full max-w-lg py-10 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-100 text-amber-600 dark:bg-amber-950 dark:text-amber-400">
          <LucideIcon name="ShieldAlert" size={24} />
        </div>
        <h1 className="font-display text-xl font-semibold">Approvals</h1>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          This workspace is for staff officers and committee members only.
        </p>
        <Button variant="outline" className="mt-4" asChild>
          <a href="/">Back to dashboard</a>
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-5">
      <div>
        <h1 className="font-display text-2xl font-semibold">Approvals</h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
          Review and decide on withdrawals and other financial actions.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 dark:border-slate-800">
        {(
          [
            ["inbox", "Inbox"],
            ["history", "History"],
            ["policies", "Group policies"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              tab === key
                ? "border-slate-900 text-slate-900 dark:border-slate-100 dark:text-slate-50"
                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-300"
            }`}
          >
            {label}
            {key === "inbox" && rows.filter((r) => r.status === "PENDING").length > 0 ? (
              <Badge variant="destructive" className="ml-1.5">
                {rows.filter((r) => r.status === "PENDING").length}
              </Badge>
            ) : null}
          </button>
        ))}
      </div>

      {tab !== "policies" ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-50"
            >
              {TYPE_OPTIONS.map((opt) => (
                <option key={opt.label} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-50"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.label} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {listLoading ? (
            <SkeletonPage />
          ) : isError ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/30 dark:text-rose-300">
              <p>{getApiErrorMessage(error, "Could not load approvals.")}</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={() => refetch()}
              >
                Retry
              </Button>
            </div>
          ) : rows.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 py-12 text-center dark:border-slate-700">
              <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                <LucideIcon name="Inbox" size={20} />
              </div>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                No approvals match the current filters.
              </p>
            </div>
          ) : (
            <div className="overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-800">
              <ul className="divide-y divide-slate-200 dark:divide-slate-800">
                {rows.map((approval: ApprovalRequest) => (
                  <li key={approval.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(approval.id)}
                      className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-slate-50 dark:hover:bg-slate-900"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-slate-900 dark:text-slate-50">
                            {formatMoney(Number(approval.amount))}
                          </span>
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium capitalize text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                            {approval.request_type.replace(/_/g, " ")}
                          </span>
                          {approval.group_name ? (
                            <span className="text-xs text-slate-400 dark:text-slate-500">
                              {approval.group_name}
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-0.5 truncate text-sm text-slate-500 dark:text-slate-400">
                          {approval.requester_name} · {approval.resource_description}
                        </p>
                        <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">
                          {new Date(approval.created_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span
                          className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                            STATUS_STYLES[approval.status] ?? STATUS_STYLES.PENDING
                          }`}
                        >
                          {approval.status_label ?? approval.status}
                        </span>
                        <LucideIcon
                          name="ChevronRight"
                          size={16}
                          className="text-slate-300 dark:text-slate-600"
                        />
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : (
        <GroupWithdrawalPolicies />
      )}

      <ApprovalDetailModal
        approvalId={selectedId}
        onClose={() => setSelectedId(null)}
        onChanged={() => {
          refetch();
        }}
      />
    </div>
  );
};

export default Approvals;