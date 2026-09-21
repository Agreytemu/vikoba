import { FC } from "react";

import LucideIcon from "@/components/LucideIcon";
import type { MembershipPlan } from "@/services/memberSelf";
import { formatPlanMoney, intervalLabel } from "./planCheckout";

interface SelectedPlanProps {
  plan: MembershipPlan;
  preview?: boolean;
  onChangePlan?: () => void;
}

/**
 * The prominent green plan card shown on the checkout. Price always comes from
 * the admin-managed plan — it is never entered or hardcoded here.
 */
const SelectedPlan: FC<SelectedPlanProps> = ({ plan, preview = false, onChangePlan }) => {
  const featureCount = plan.features?.length ?? 0;
  return (
    <div className="relative overflow-hidden rounded-2xl border border-[#115036]/20 bg-gradient-to-br from-[#115036] to-[#0b3a26] p-5 text-white shadow-card">
      <span className="absolute -right-4 -top-4 h-24 w-24 rounded-full bg-white/5 blur-2xl" aria-hidden />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.08em] text-white">
            <LucideIcon name="Crown" size={12} />
            {preview ? "Plan preview" : "Selected plan"}
          </p>
          <p className="mt-2.5 font-display text-xl font-semibold text-white">{plan.name}</p>
          {featureCount > 0 && (
            <p className="mt-0.5 text-[12px] text-white/70">
              {featureCount} feature{featureCount === 1 ? "" : "s"} included
            </p>
          )}
        </div>
        <div className="text-right">
          <p className="font-display text-[26px] font-bold leading-none tracking-tight text-white">
            {formatPlanMoney(plan.price, plan.currency)}
          </p>
          <p className="mt-1 text-[12px] text-white/70">{intervalLabel(plan.interval)}</p>
        </div>
      </div>
      {onChangePlan && (
        <button
          type="button"
          onClick={onChangePlan}
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-white/15 px-3 py-1.5 text-[12px] font-medium text-white transition hover:bg-white/25"
        >
          <LucideIcon name="RefreshCw" size={13} /> Change plan
        </button>
      )}
    </div>
  );
};

export default SelectedPlan;