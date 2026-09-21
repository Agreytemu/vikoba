import { FC } from "react";
import { useNavigate } from "react-router-dom";

import Button from "@/components/Button";
import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";
import { maskPhone } from "@/lib/payments";
import type { MembershipPlan } from "@/services/memberSelf";
import type { MemberSubscription } from "@/services/memberPayments";
import { formatPlanMoney, intervalLabel, methodLabel } from "./planCheckout";

interface StageShellProps {
  children: React.ReactNode;
}

const StageShell: FC<StageShellProps> = ({ children }) => (
  <div className="mx-auto max-w-lg">
    <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-card dark:border-slate-800 dark:bg-slate-900">
      {children}
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// PROCESSING — "Payment Request Sent" then "Waiting for payment confirmation…"
// ---------------------------------------------------------------------------
interface ProcessingViewProps {
  plan: MembershipPlan;
  phone: string;
  method: string | null;
  txRef: string;
  onCancel: () => void;
}

export const ProcessingView: FC<ProcessingViewProps> = ({ plan, phone, method, txRef, onCancel }) => (
  <StageShell>
    <Spinner />
    <h1 className="mt-4 font-display text-2xl font-semibold">Payment Request Sent</h1>
    <p className="mx-auto mt-2 max-w-sm text-sm text-slate-500 dark:text-slate-400">
      A {plan.name} mobile money request has been sent to{" "}
      <strong className="text-ink dark:text-slate-100">{maskPhone(phone)}</strong>
      {method ? ` via ${methodLabel(method)}` : ""}. Complete the Mobile Money authorization on your phone to finish.
    </p>
    <p className="mt-5 inline-flex items-center gap-2 rounded-lg bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">
      <LucideIcon name="Loader2" size={16} className="animate-spin" />
      Waiting for payment confirmation…
    </p>
    <p className="mt-4 text-xs text-slate-400">
      Do not close this page — we update it the moment the payment is confirmed. This usually takes a few minutes.
    </p>
    <p className="mt-2 text-xs text-slate-400">Transaction ID · {txRef}</p>
    <div className="mt-6">
      <Button text="Cancel payment" onClick={onCancel} variant="secondary" />
    </div>
  </StageShell>
);

// ---------------------------------------------------------------------------
// SUCCESS — "Payment Successful / Your {plan} plan is now active"
// ---------------------------------------------------------------------------
interface SuccessViewProps {
  plan: MembershipPlan;
  txRef: string;
  method: string | null;
  amount: string | number;
  subscription?: MemberSubscription | null;
}

export const SuccessView: FC<SuccessViewProps> = ({ plan, txRef, method, amount, subscription }) => {
  const navigate = useNavigate();
  const started = subscription?.started_at;
  const expires = subscription?.expires_at;
  return (
    <StageShell>
      <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-green-700 dark:bg-emerald-950/50 dark:text-emerald-300">
        <LucideIcon name="CheckCircle2" size={34} />
      </span>
      <h1 className="mt-4 font-display text-2xl font-semibold">Payment Successful</h1>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Your <strong className="text-ink dark:text-slate-100">{plan.name}</strong> plan is now active.
      </p>

      <div className="mt-5 rounded-2xl border border-[#115036]/20 bg-[#EEF6F0] p-4 text-left dark:border-emerald-900 dark:bg-emerald-950/30">
        <p className="font-display text-xl font-bold text-[#115036] dark:text-emerald-300">
          {formatPlanMoney(amount, plan.currency)}
        </p>
        <p className="text-[12px] text-slate-500 dark:text-slate-400">
          {plan.name} · {intervalLabel(plan.interval)}
          {method ? ` · paid via ${methodLabel(method)}` : ""}
        </p>
      </div>

      <dl className="mt-4 space-y-2 rounded-xl bg-slate-50 p-4 text-left text-[13px] dark:bg-slate-800/60">
        <div className="flex justify-between gap-3">
          <dt className="text-slate-500 dark:text-slate-400">Transaction ID</dt>
          <dd className="truncate font-mono text-slate-700 dark:text-slate-200">{txRef}</dd>
        </div>
        {started && (
          <div className="flex justify-between gap-3">
            <dt className="text-slate-500 dark:text-slate-400">Activated</dt>
            <dd className="text-slate-700 dark:text-slate-200">
              {new Date(started).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}
            </dd>
          </div>
        )}
        {expires && (
          <div className="flex justify-between gap-3">
            <dt className="text-slate-500 dark:text-slate-400">Next billing</dt>
            <dd className="text-slate-700 dark:text-slate-200">
              {new Date(expires).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}
            </dd>
          </div>
        )}
      </dl>

      <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
        <Button text="Continue" onClick={() => navigate("/")} variant="primary" />
        <Button text="View my plan" onClick={() => navigate("/")} variant="secondary" />
      </div>
    </StageShell>
  );
};

// ---------------------------------------------------------------------------
// FAILED
// ---------------------------------------------------------------------------
interface FailedViewProps {
  plan: MembershipPlan;
  txRef: string;
  onRetry: () => void;
  onChangeMethod: () => void;
}

export const FailedView: FC<FailedViewProps> = ({ plan, txRef, onRetry, onChangeMethod }) => (
  <StageShell>
    <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-red-600 dark:bg-red-950/50 dark:text-red-300">
      <LucideIcon name="XCircle" size={34} />
    </span>
    <h1 className="mt-4 font-display text-2xl font-semibold">Payment Failed</h1>
    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
      Your {plan.name} payment could not be completed.
    </p>
    <p className="mt-3 font-display text-xl font-bold">{formatPlanMoney(plan.price, plan.currency)}</p>
    {txRef ? <p className="mt-2 text-xs text-slate-400">Reference · {txRef}</p> : null}
    <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
      <Button text="Try Again" onClick={onRetry} variant="primary" />
      <Button text="Change Payment Method" onClick={onChangeMethod} variant="secondary" />
    </div>
  </StageShell>
);

// ---------------------------------------------------------------------------
// CANCELLED
// ---------------------------------------------------------------------------
interface CancelledViewProps {
  plan: MembershipPlan;
  onBack: () => void;
}

export const CancelledView: FC<CancelledViewProps> = ({ plan, onBack }) => (
  <StageShell>
    <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300">
      <LucideIcon name="Ban" size={30} />
    </span>
    <h1 className="mt-4 font-display text-2xl font-semibold">Payment Cancelled</h1>
    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
      The {plan.name} payment request was cancelled before it was confirmed.
    </p>
    <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
      <Button text="Back to checkout" onClick={onBack} variant="primary" />
    </div>
  </StageShell>
);