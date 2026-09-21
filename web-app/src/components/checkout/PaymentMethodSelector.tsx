import { FC } from "react";

import MobileNetworkLogo from "@/components/MobileNetworkLogo";
import LucideIcon from "@/components/LucideIcon";
import { CHECKOUT_PAYMENT_METHODS, suggestMethod } from "./planCheckout";
import type { CheckoutPaymentMethod } from "./planCheckout";

interface PaymentMethodSelectorProps {
  value: string | null;
  phone: string;
  onChange: (id: string) => void;
  /** Override the subtitle line (deposit uses USSD push copy, withdraw uses payout copy). */
  subtitle?: string;
}

/**
 * Data-driven mobile-money method rows plus a disabled Card option. The phone
 * number drives the suggested method (Snippe resolves the real operator).
 */
const PaymentMethodSelector: FC<PaymentMethodSelectorProps> = ({
  value,
  phone,
  onChange,
  subtitle = "The USSD push is sent to the mobile money number you confirm below.",
}) => {
  const suggested = suggestMethod(phone);

  const Row: FC<{ method: CheckoutPaymentMethod; selected: boolean; isSuggested: boolean }> = ({
    method,
    selected,
    isSuggested,
  }) => {
    const brand = method.networkId ? (
      <MobileNetworkLogo networkId={method.networkId} size={40} />
    ) : (
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
        <LucideIcon name={method.icon} size={20} />
      </span>
    );
    if (!method.enabled) {
      return (
        <div className="flex w-full cursor-not-allowed items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 opacity-60 dark:border-slate-800 dark:bg-slate-900">
          {brand}
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold text-slate-700 dark:text-slate-200">{method.label}</span>
            <span className="block text-[11px] text-slate-400 dark:text-slate-500">{method.tagline}</span>
          </span>
          <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[11px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            Coming soon
          </span>
        </div>
      );
    }
    return (
      <button
        type="button"
        onClick={() => onChange(method.id)}
        aria-pressed={selected}
        className={`flex w-full items-center gap-3 rounded-2xl border bg-white p-4 text-left shadow-sm transition dark:bg-slate-900 ${
          selected
            ? "border-[#115036] ring-2 ring-[#115036]/15 dark:border-emerald-400"
            : "border-slate-200 hover:border-[#115036]/40 dark:border-slate-800 dark:hover:border-slate-700"
        }`}
      >
        {brand}
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-900 dark:text-white">{method.label}</span>
            {isSuggested && (
              <span className="rounded-full bg-[#115036]/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#115036] dark:bg-emerald-950/50 dark:text-emerald-300">
                Suggested
              </span>
            )}
          </span>
          <span className="block text-[11px] text-slate-400 dark:text-slate-500">{method.tagline}</span>
        </span>
        <span
          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition ${
            selected ? "border-[#115036] bg-[#115036] text-white dark:border-emerald-400 dark:bg-emerald-400" : "border-slate-300 dark:border-slate-600"
          }`}
        >
          {selected && <LucideIcon name="Check" size={12} />}
        </span>
      </button>
    );
  };

  return (
    <div>
      <h2 className="font-display text-[16px] font-semibold">Payment method</h2>
      <p className="mt-0.5 text-[12px] text-slate-500 dark:text-slate-400">{subtitle}</p>
      <div className="mt-3 space-y-2.5">
        {CHECKOUT_PAYMENT_METHODS.map((m) => (
          <Row
            key={m.id}
            method={m}
            selected={m.enabled && value === m.id}
            isSuggested={m.enabled && m.id === suggested}
          />
        ))}
      </div>
    </div>
  );
};

export default PaymentMethodSelector;