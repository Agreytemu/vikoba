import { FC } from "react";

import { MIN_PAYOUT_TZS } from "@/lib/payments";
import { formatDepositMoney } from "../deposit/depositFlow";

interface WithdrawAmountInputProps {
  id?: string;
  value: string;
  error: string | null;
  maxLabel?: string;
  onChange: (raw: string) => void;
}

/** TZS withdrawal amount field with inline validation and a min/max hint. */
const WithdrawAmountInput: FC<WithdrawAmountInputProps> = ({
  id = "withdraw-amount",
  value,
  error,
  maxLabel,
  onChange,
}) => {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={id} className="block text-sm font-medium text-slate-900 dark:text-white">
          Withdrawal amount
        </label>
        <span className="text-[11px] text-slate-400">
          Min {formatDepositMoney(MIN_PAYOUT_TZS)}{maxLabel ? ` · Max ${maxLabel}` : ""}
        </span>
      </div>

      <div className="relative mt-2">
        <span
          className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-sm font-semibold text-slate-400"
          aria-hidden
        >
          TZS
        </span>
        <input
          id={id}
          name="withdraw-amount"
          type="text"
          inputMode="numeric"
          autoComplete="off"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="0"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : hintId}
          className={`h-12 w-full rounded-xl border bg-white pl-14 pr-4 text-[16px] font-semibold text-slate-900 outline-none transition placeholder:text-slate-300 focus:ring-2 dark:bg-slate-950 dark:text-white dark:placeholder:text-slate-600 ${
            error
              ? "border-red-300 focus:border-red-400 focus:ring-red-100 dark:border-red-800 dark:focus:ring-red-950"
              : "border-slate-200 focus:border-[#115036] focus:ring-[#115036]/15 dark:border-slate-700 dark:focus:ring-emerald-500/20"
          }`}
        />
      </div>

      {error ? (
        <p id={errorId} role="alert" className="mt-2 flex items-center gap-1.5 text-[12px] font-medium text-red-600 dark:text-red-400">
          <span aria-hidden>!</span> {error}
        </p>
      ) : (
        <p id={hintId} className="mt-2 text-[11px] text-slate-400">
          Enter the amount you want to move from your savings to your mobile money.
        </p>
      )}
    </section>
  );
};

export default WithdrawAmountInput;