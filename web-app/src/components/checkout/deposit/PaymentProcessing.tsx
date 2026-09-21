import { FC } from "react";

import Button from "@/components/Button";
import LucideIcon from "@/components/LucideIcon";
import Spinner from "@/components/Spinner";
import { displayTzPhone, formatDepositMoney } from "./depositFlow";

interface PaymentProcessingProps {
  amount: string;
  phone: string;
  onBack: () => void;
  canBack?: boolean;
}

/**
 * "Payment request sent — waiting for confirmation." Success only ever follows
 * a verified webhook; this screen keeps polling until the backend confirms or
 * the payment terminal state changes.
 */
const PaymentProcessing: FC<PaymentProcessingProps> = ({
  amount,
  phone,
  onBack,
  canBack = true,
}) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-card dark:border-slate-800 dark:bg-slate-900">
    <span className="relative mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#115036]/10 text-[#115036] dark:bg-emerald-950/50 dark:text-emerald-300">
      <LucideIcon name="Loader2" size={30} className="animate-spin" />
    </span>

    <h1 className="mt-4 font-display text-2xl font-semibold">Payment request sent</h1>
    <p className="mx-auto mt-2 max-w-sm text-sm text-slate-500 dark:text-slate-400">
      We sent a {formatDepositMoney(amount)} push to{" "}
      <strong className="text-slate-900 dark:text-white">{displayTzPhone(phone)}</strong>.
      Complete it with your mobile money PIN to approve the deposit.
    </p>

    <p className="mt-5 inline-flex items-center gap-2 rounded-lg bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">
      <Spinner />
      Waiting for payment…
    </p>

    <p className="mt-4 text-xs leading-relaxed text-slate-400">
      This usually takes a few minutes. You can leave this page — your savings
      are credited automatically once the payment is confirmed.
    </p>

    <div className="mt-6">
      <Button text="Back to deposit" onClick={onBack} variant="secondary" disabled={!canBack} />
    </div>
  </div>
);

export default PaymentProcessing;