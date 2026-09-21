import { FC } from "react";

import LucideIcon from "@/components/LucideIcon";

interface DepositDestinationProps {
  memberName: string;
  membershipNumber: string;
  accountNumber: string;
  availableBalance: string;
}

/**
 * "Deposit to" block — the money lands in the member's own VICOBA savings
 * account. The balance shown is read-only reference; the deposit amount is
 * never limited by it (mobile money can top up from any balance).
 */
const DepositDestination: FC<DepositDestinationProps> = ({
  memberName,
  membershipNumber,
  accountNumber,
  availableBalance,
}) => (
  <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">
          Deposit to
        </p>
        <div className="mt-2 flex items-center gap-2.5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#115036]/10 text-[#115036] dark:bg-emerald-950/50 dark:text-emerald-300">
            <LucideIcon name="Wallet" size={19} />
          </span>
          <span className="min-w-0">
            <span className="block truncate font-display text-[16px] font-semibold text-slate-900 dark:text-white">
              VICOBA savings account
            </span>
            <span className="block truncate text-[12px] text-slate-500 dark:text-slate-400">
              {memberName} · {membershipNumber} · {accountNumber}
            </span>
          </span>
        </div>
      </div>
      <div className="shrink-0 text-right">
        <p className="text-[11px] text-slate-500 dark:text-slate-400">
          Available balance
        </p>
        <p className="mt-0.5 font-display text-[15px] font-semibold text-slate-900 dark:text-white">
          {availableBalance}
        </p>
      </div>
    </div>
  </section>
);

export default DepositDestination;