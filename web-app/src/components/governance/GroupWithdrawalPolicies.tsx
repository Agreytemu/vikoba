import { FC, useEffect, useState } from "react";
import { toast } from "react-toastify";

import LucideIcon from "@/components/LucideIcon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Modal from "@/components/ui/Modal";
import { SkeletonPage } from "@/components/Skeleton";
import { useGetMyGroups } from "@/hooks/api/groups";
import { useGroupWithdrawalPolicy, useUpdateGroupWithdrawalPolicy } from "@/hooks/api/governance";
import { useCurrency } from "@/contexts/CurrencyContext";
import { getApiErrorMessage } from "@/lib/utils";
import { GroupWithdrawalPolicyPayload } from "@/services/governance";

const RATIO_PERCENT = (value: unknown): string =>
  value === null || value === undefined || value === "" ? "" : String(Number(value) * 100);

/**
 * Per-group withdrawal policy editor (officers + committee). Blank number
 * fields inherit the platform default shown in the effective summary; the
 * backend re-validates and records every change in the audit trail.
 */
export const GroupWithdrawalPolicies: FC = () => {
  const { data: groups, isLoading } = useGetMyGroups();
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);

  if (isLoading) return <SkeletonPage />;
  if (!groups?.length) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 py-12 text-center dark:border-slate-700">
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
          <LucideIcon name="Users" size={20} />
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          You are not a member of any group yet, so there are no policies to
          configure.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {groups.map((group) => (
        <GroupPolicyRow
          key={group.id}
          groupId={group.id}
          groupName={group.name}
          groupRole={group.my_role}
          onEdit={() => setSelectedGroupId(group.id)}
        />
      ))}
      <PolicyEditorModal
        groupId={selectedGroupId}
        onClose={() => setSelectedGroupId(null)}
      />
    </div>
  );
};

const GroupPolicyRow: FC<{
  groupId: number;
  groupName: string;
  groupRole: string | null;
  onEdit: () => void;
}> = ({ groupId, groupName, groupRole, onEdit }) => {
  const { formatMoney } = useCurrency();
  const { data: policy, isLoading, isError } = useGroupWithdrawalPolicy(groupId);
  const effective = policy?.effective;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 px-4 py-3 dark:border-slate-800">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium text-slate-900 dark:text-slate-50">{groupName}</p>
          {groupRole ? (
            <Badge variant="secondary" className="capitalize">
              {groupRole.toLowerCase()}
            </Badge>
          ) : null}
        </div>
        {isError ? (
          <p className="mt-0.5 text-xs text-rose-600 dark:text-rose-400">
            No access to this group's policy.
          </p>
        ) : isLoading ? (
          <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">Loading policy…</p>
        ) : (
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            Auto-approve up to{" "}
            {effective?.auto_approve_limit != null
              ? formatMoney(Number(effective.auto_approve_limit))
              : "unlimited"}
            {" · "}
            {effective?.review_levels === "TWO_LEVEL"
              ? "Treasurer + Chairperson review"
              : `Reviewed by ${effective?.reviewer_role?.toLowerCase() ?? "treasurer"}`}
            {" · "}
            {effective?.policy_version}
          </p>
        )}
      </div>
      <Button variant="outline" size="sm" onClick={onEdit}>
        Configure
      </Button>
    </div>
  );
};

const NUMERIC_FIELDS = [
  { key: "auto_approve_limit", label: "Auto-approve limit", hint: "Above this amount, manual review is required. Blank = unlimited." },
  { key: "max_withdrawal_limit", label: "Max single withdrawal", hint: "Hard ceiling per withdrawal. Blank = no ceiling." },
  { key: "min_withdrawal_amount", label: "Min withdrawal", hint: "Lower bound for a single withdrawal. Blank = none." },
  { key: "weekly_withdrawal_limit", label: "Weekly limit", hint: "Rolling 7-day total before manual review. Blank = unlimited." },
  { key: "weekly_withdrawal_count", label: "Weekly frequency", hint: "Max withdrawals per rolling week. Blank = unlimited." },
  { key: "monthly_withdrawal_limit", label: "Monthly limit", hint: "Rolling 30-day total before manual review. Blank = unlimited." },
] as const;

interface PolicyForm {
  auto_approve_limit: string;
  max_withdrawal_limit: string;
  min_withdrawal_amount: string;
  weekly_withdrawal_limit: string;
  weekly_withdrawal_count: string;
  monthly_withdrawal_limit: string;
  min_retained_ratio: string;
  min_retained_ratio_percent: string;
  review_on_outstanding_loan: boolean;
  review_on_outstanding_penalty: boolean;
  review_levels: string;
  reviewer_role: string;
}

const PolicyEditorModal: FC<{ groupId: number | null; onClose: () => void }> = ({
  groupId,
  onClose,
}) => {
  const { data: policy, isLoading } = useGroupWithdrawalPolicy(groupId ?? undefined);
  const update = useUpdateGroupWithdrawalPolicy(groupId ?? undefined);

  const [form, setForm] = useState<PolicyForm>({
    auto_approve_limit: "",
    max_withdrawal_limit: "",
    min_withdrawal_amount: "",
    weekly_withdrawal_limit: "",
    weekly_withdrawal_count: "",
    monthly_withdrawal_limit: "",
    min_retained_ratio: "",
    min_retained_ratio_percent: "",
    review_on_outstanding_loan: false,
    review_on_outstanding_penalty: false,
    review_levels: "SINGLE",
    reviewer_role: "TREASURER",
  });

  useEffect(() => {
    if (!policy) return;
    setForm({
      auto_approve_limit: policy.auto_approve_limit ?? "",
      max_withdrawal_limit: policy.max_withdrawal_limit ?? "",
      min_withdrawal_amount: policy.min_withdrawal_amount ?? "",
      weekly_withdrawal_limit: policy.weekly_withdrawal_limit ?? "",
      weekly_withdrawal_count:
        policy.weekly_withdrawal_count == null ? "" : String(policy.weekly_withdrawal_count),
      monthly_withdrawal_limit: policy.monthly_withdrawal_limit ?? "",
      min_retained_ratio: policy.min_retained_ratio ?? "",
      min_retained_ratio_percent: RATIO_PERCENT(policy.min_retained_ratio),
      review_on_outstanding_loan: policy.review_on_outstanding_loan,
      review_on_outstanding_penalty: policy.review_on_outstanding_penalty,
      review_levels: policy.review_levels,
      reviewer_role: policy.reviewer_role,
    });
  }, [policy]);

  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const submit = () => {
    if (!groupId) return;
    const payload: GroupWithdrawalPolicyPayload = {
      auto_approve_limit: form.auto_approve_limit || null,
      max_withdrawal_limit: form.max_withdrawal_limit || null,
      min_withdrawal_amount: form.min_withdrawal_amount || null,
      weekly_withdrawal_limit: form.weekly_withdrawal_limit || null,
      weekly_withdrawal_count: form.weekly_withdrawal_count
        ? Number(form.weekly_withdrawal_count)
        : null,
      monthly_withdrawal_limit: form.monthly_withdrawal_limit || null,
      min_retained_ratio: form.min_retained_ratio || null,
      review_on_outstanding_loan: form.review_on_outstanding_loan,
      review_on_outstanding_penalty: form.review_on_outstanding_penalty,
      review_levels: form.review_levels,
      reviewer_role: form.reviewer_role,
    };
    update.mutate(payload, {
      onSuccess: () => {
        toast.success("Withdrawal policy updated.");
        onClose();
      },
      onError: (err) => {
        toast.error(getApiErrorMessage(err, "Could not update the policy."));
      },
    });
  };

  const setRatioPercent = (value: string) => {
    const percent = Number(value);
    const ratio =
      value === "" || Number.isNaN(percent)
        ? ""
        : String(Math.min(100, Math.max(0, percent)) / 100);
    set("min_retained_ratio", ratio);
    set("min_retained_ratio_percent", value);
  };

  return (
    <Modal
      isOpen={Boolean(groupId)}
      onClose={onClose}
      title="Withdrawal policy"
    >
      {isLoading || !policy ? (
        <SkeletonPage />
      ) : (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            Effective defaults: auto-approve{" "}
            {policy.effective.auto_approve_limit != null
              ? String(policy.effective.auto_approve_limit)
              : "unlimited"}
            {" · "}min {String(policy.effective.min_withdrawal_amount)}
            {" · "}retain {RATIO_PERCENT(policy.effective.min_retained_ratio)}%. Blank fields
            keep the platform default.
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {NUMERIC_FIELDS.map((field) => (
              <label key={field.key} className="block">
                <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                  {field.label}
                </span>
                <input
                  type="number"
                  min="0"
                  step="any"
                  inputMode="decimal"
                  value={form[field.key] ?? ""}
                  onChange={(e) => set(field.key, e.target.value)}
                  placeholder="inherit"
                  className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-50"
                />
                <span className="mt-0.5 block text-[11px] text-slate-400 dark:text-slate-500">
                  {field.hint}
                </span>
              </label>
            ))}
            <label className="block">
              <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                Minimum retained balance (%)
              </span>
              <input
                type="number"
                min="0"
                max="100"
                step="1"
                inputMode="decimal"
                value={form.min_retained_ratio_percent}
                onChange={(e) => setRatioPercent(e.target.value)}
                placeholder="inherit"
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-50"
              />
            </label>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                Review levels
              </span>
              <select
                value={form.review_levels}
                onChange={(e) => set("review_levels", e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-50"
              >
                <option value="SINGLE">Single review</option>
                <option value="TWO_LEVEL">Treasurer + Chairperson</option>
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                Reviewing officer role
              </span>
              <select
                value={form.reviewer_role}
                onChange={(e) => set("reviewer_role", e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-50"
              >
                <option value="TREASURER">Treasurer</option>
                <option value="CHAIRPERSON">Chairperson</option>
                <option value="SECRETARY">Secretary</option>
              </select>
            </label>
          </div>

          <div className="space-y-2 rounded-xl border border-slate-200 p-3 dark:border-slate-800">
            <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
              Manual review triggers
            </span>
            <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={form.review_on_outstanding_loan}
                onChange={(e) => set("review_on_outstanding_loan", e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-slate-900"
              />
              When the member has an outstanding loan
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={form.review_on_outstanding_penalty}
                onChange={(e) => set("review_on_outstanding_penalty", e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-slate-900"
              />
              When the member has an unpaid loan penalty
            </label>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Save policy"}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
};

export default GroupWithdrawalPolicies;