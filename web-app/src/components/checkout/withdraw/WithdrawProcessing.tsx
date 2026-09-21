import { FC } from "react";

import Button from "@/components/Button";
import LucideIcon from "@/components/LucideIcon";
import Spinner from "@/components/Spinner";
import { maskPhone } from "@/lib/payments";
import { formatDepositMoney } from "../deposit/depositFlow";

interface WithdrawProcessingProps {
  amount: string;
  phone: string;
  onBack: () => void;
  canBack?: boolean;
}

/**
 * "Withdrawal sent — waiting for confirmation." The balance is debited only when
 * the payout.completed webhook lands; this screen polls until then (or the
 * payout reaches a terminal failure state).
 */
const WithdrawProcessing: FC<WithdrawProcessingProps> = ({
  amount,
  phone,
  onBack,
  canBack = true,
}) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-card dark:border-slate-800 dark:bg-slate-900">
    <span className="relative mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#115036]/10 text-[#115036] dark:bg-emerald-950/50 dark:text-emerald-300">
      <LucideIcon name="Loader2" size={30} className="animate-spin" />
    </span>

    <h1 className="mt-4 font-display text-2xl font-semibold">Withdrawal in progress</h1>
    <p className="mx-auto mt-2 max-w-sm text-sm text-slate-500 dark:text-slate-400">
      {formatDepositMoney(amount)} is on its way to{" "}
      <strong className="text-slate-900 dark:text-white">{maskPhone(phone)}</strong>.
      No staff approval is needed — the system sent it automatically.
    </p>

    <p className="mt-5 inline-flex items-center gap-2 rounded-lg bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">
      <Spinner />
      Waiting for payout…
    </p>

    <p className="mt-4 text-xs leading-relaxed text-slate-400">
      Payouts usually arrive within a minute. Your balance is only debited once
      the payout is confirmed.
    </p>

    <div className="mt-6">
      <Button text="Back to withdraw" onClick={onBack} variant="secondary" disabled={!canBack} />
    </div>
  </div>
);

export default WithdrawProcessing;