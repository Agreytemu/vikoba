import { FC } from "react";

import MobileNetworkLogo from "@/components/MobileNetworkLogo";
import { displayTzPhone, formatDepositMoney } from "./depositFlow";
import type { CheckoutPaymentMethod } from "../planCheckout";

interface DepositSummaryProps {
  amount: string;
  method: CheckoutPaymentMethod | null;
  phone: string;
  feeLabel?: string;
  totalLabel?: string;
}

/**
 * Cost breakdown rendered entirely from the member's own inputs + fixed backend
 * fee (TZS 0 for Snippe collections). Total is always amount + fee — never a
 * value the frontend invents.
 */
const DepositSummary: FC<DepositSummaryProps> = ({
  amount,
  method,
  phone,
  feeLabel = `${formatDepositMoney(0)} · free by us`,
  totalLabel,
}) => {
  const amountLabel = formatDepositMoney(amount);
  const total = totalLabel ?? amountLabel;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-[16px] font-semibold">Deposit summary</h2>
        <span className="rounded-full bg-[#115036]/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-[#115036] dark:bg-emerald-950/50 dark:text-emerald-300">
          TZS
        </span>
      </div>

      <dl className="space-y-2.5 text-sm">
        <div className="flex items-center justify-between">
          <dt className="text-slate-500 dark:text-slate-400">Deposit amount</dt>
          <dd className="font-medium text-slate-900 dark:text-white">{amountLabel}</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-slate-500 dark:text-slate-400">Payment method</dt>
          <dd className="flex items-center gap-2 font-medium text-slate-900 dark:text-white">
            {method?.networkId ? (
              <MobileNetworkLogo networkId={method.networkId} size={22} />
            ) : null}
            {method ? method.label : "—"}
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-slate-500 dark:text-slate-400">Mobile number</dt>
          <dd className="font-medium text-slate-900 dark:text-white">
            {phone ? displayTzPhone(phone) : "—"}
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-slate-500 dark:text-slate-400">Payment fee</dt>
          <dd className="font-medium text-slate-900 dark:text-white">{feeLabel}</dd>
        </div>
        <div className="flex items-center justify-between border-t border-dashed border-slate-200 pt-3 dark:border-slate-700">
          <dt className="font-semibold text-slate-900 dark:text-white">Total</dt>
          <dd className="font-display text-lg font-bold text-[#115036] dark:text-emerald-300">
            {total}
          </dd>
        </div>
      </dl>
    </section>
  );
};

export default DepositSummary;