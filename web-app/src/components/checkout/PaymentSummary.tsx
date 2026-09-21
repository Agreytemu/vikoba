import { FC } from "react";

import type { MembershipPlan } from "@/services/memberSelf";
import { formatPlanMoney, intervalLabel } from "./planCheckout";

interface PaymentSummaryProps {
  plan: MembershipPlan;
  feeLabel?: string;
}

/**
 * Cost breakdown rendered straight from the selected plan (never typed):
 * Plan / Billing / Amount / Payment fee / prominent Total.
 */
const PaymentSummary: FC<PaymentSummaryProps> = ({ plan, feeLabel = "Free" }) => {
  const total = formatPlanMoney(plan.price, plan.currency);
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-[16px] font-semibold">Payment summary</h2>
        <span className="rounded-full bg-[#115036]/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-[#115036] dark:bg-emerald-950/50 dark:text-emerald-300">
          {plan.currency}
        </span>
      </div>
      <dl className="space-y-2.5 text-sm">
        <div className="flex items-center justify-between">
          <dt className="text-slate-500 dark:text-slate-400">Plan</dt>
          <dd className="font-medium text-slate-900 dark:text-white">{plan.name}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-slate-500 dark:text-slate-400">Billing</dt>
          <dd className="font-medium capitalize text-slate-900 dark:text-white">
            {intervalLabel(plan.interval)} · auto-renews
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-slate-500 dark:text-slate-400">Amount</dt>
          <dd className="font-medium text-slate-900 dark:text-white">{formatPlanMoney(plan.price, plan.currency)}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-slate-500 dark:text-slate-400">Payment fee</dt>
          <dd className="font-medium text-slate-900 dark:text-white">{feeLabel}</dd>
        </div>
        <div className="flex items-center justify-between border-t border-dashed border-slate-200 pt-3 dark:border-slate-700">
          <dt className="font-semibold text-slate-900 dark:text-white">Total</dt>
          <dd className="font-display text-lg font-bold text-[#115036] dark:text-emerald-300">{total}</dd>
        </div>
      </dl>
    </div>
  );
};

export default PaymentSummary;