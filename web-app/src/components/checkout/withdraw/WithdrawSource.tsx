import { FC } from "react";

import LucideIcon from "@/components/LucideIcon";
import { useCurrency } from "@/contexts/CurrencyContext";
import type { MyAccount } from "@/hooks/api/myAccounts";

interface WithdrawSourceProps {
  accounts: MyAccount[];
  accountNumber: string;
  onAccountChange: (number: string) => void;
}

/** "Withdraw from" — pick which VICOBA savings account the money leaves. */
const WithdrawSource: FC<WithdrawSourceProps> = ({
  accounts,
  accountNumber,
  onAccountChange,
}) => {
  const { formatMoney } = useCurrency();

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">
          Withdraw from
        </p>
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#115036]/10 text-[#115036] dark:bg-emerald-950/50 dark:text-emerald-300">
          <LucideIcon name="Wallet" size={19} />
        </span>
      </div>

      {!accounts || accounts.length === 0 ? (
        <p className="mt-3 rounded-xl bg-slate-50 px-4 py-6 text-center text-[13px] text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
          No savings account yet — ask staff to open one for you.
        </p>
      ) : (
        <div className="mt-3 space-y-2.5">
          {accounts.map((a) => {
            const selected = a.account_number === accountNumber;
            return (
              <button
                key={a.account_number}
                type="button"
                onClick={() => onAccountChange(a.account_number)}
                aria-pressed={selected}
                className={`flex w-full items-center gap-3 rounded-2xl border bg-white p-4 text-left shadow-sm transition dark:bg-slate-900 ${
                  selected
                    ? "border-[#115036] ring-2 ring-[#115036]/15 dark:border-emerald-400"
                    : "border-slate-200 hover:border-[#115036]/40 dark:border-slate-800 dark:hover:border-slate-700"
                }`}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-slate-900 dark:text-white">
                    {a.product_name}
                  </span>
                  <span className="block truncate text-[11px] text-slate-400">
                    {a.account_number}
                  </span>
                </span>
                <span className="shrink-0 text-right">
                  <span className="block text-[11px] text-slate-500 dark:text-slate-400">
                    Balance
                  </span>
                  <span className="block font-display text-[15px] font-semibold text-slate-900 dark:text-white">
                    {formatMoney(Number(a.balance))}
                  </span>
                </span>
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition ${
                    selected
                      ? "border-[#115036] bg-[#115036] text-white dark:border-emerald-400 dark:bg-emerald-400"
                      : "border-slate-300 dark:border-slate-600"
                  }`}
                >
                  {selected && <LucideIcon name="Check" size={12} />}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
};

export default WithdrawSource;