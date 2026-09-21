import { FC } from "react";

import Button from "@/components/Button";
import LucideIcon from "@/components/LucideIcon";
import { formatDepositMoney } from "../deposit/depositFlow";

interface WithdrawFailedProps {
  amount: string;
  status?: string;
  reference?: string;
  onRetry: () => void;
  onHelp: () => void;
}

const STATUS_TITLE: Record<string, string> = {
  CANCELLED: "Withdrawal cancelled",
  EXPIRED: "Withdrawal expired",
  VOIDED: "Withdrawal voided",
  FAILED: "Withdrawal failed",
};

/**
 * Terminal failure screen. The status comes straight from the backend payout
 * status, so a cancelled request reads differently from a declined one.
 */
const WithdrawFailed: FC<WithdrawFailedProps> = ({
  amount,
  status = "FAILED",
  reference,
  onRetry,
  onHelp,
}) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-card dark:border-slate-800 dark:bg-slate-900">
    <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-100 text-red-600 dark:bg-red-950/50 dark:text-red-300">
      <LucideIcon name="XCircle" size={34} />
    </span>

    <h1 className="mt-4 font-display text-2xl font-semibold">
      {STATUS_TITLE[status] ?? "Withdrawal failed"}
    </h1>
    <p className="mx-auto mt-2 max-w-sm text-sm text-slate-500 dark:text-slate-400">
      The money was not sent — your balance is unchanged.
    </p>

    <p className="mt-4 font-display text-2xl font-bold">{formatDepositMoney(amount)}</p>

    {reference ? (
      <p className="mt-2 text-xs text-slate-400">Reference · {reference}</p>
    ) : null}

    <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
      <Button text="Try again" onClick={onRetry} variant="primary" />
      <Button text="View help" onClick={onHelp} variant="secondary" />
    </div>
  </div>
);

export default WithdrawFailed;