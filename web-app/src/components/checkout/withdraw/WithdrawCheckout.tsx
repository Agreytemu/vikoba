import { FC } from "react";

import LucideIcon from "@/components/LucideIcon";
import Spinner from "@/components/Spinner";
import PaymentMethodSelector from "@/components/checkout/PaymentMethodSelector";
import type { MyAccount } from "@/hooks/api/myAccounts";
import { formatDepositMoney } from "../deposit/depositFlow";
import { CHECKOUT_PAYMENT_METHODS, type CheckoutPaymentMethod } from "../planCheckout";
import WithdrawAmountInput from "./WithdrawAmountInput";
import WithdrawRecipient from "./WithdrawRecipient";
import WithdrawSource from "./WithdrawSource";
import WithdrawSummary from "./WithdrawSummary";

interface WithdrawCheckoutProps {
  accounts: MyAccount[];
  accountNumber: string;
  onAccountChange: (number: string) => void;
  availableLabel: string;
  amount: string;
  amountError: string | null;
  methodId: string | null;
  verifiedPhone: string;
  phoneVerified: boolean;
  onAmountChange: (raw: string) => void;
  onMethodChange: (id: string) => void;
  onConfirm: () => void;
  canSubmit: boolean;
  isInitiating: boolean;
}

/**
 * The withdrawal screen: source account, amount, payment brand, verified
 * destination and summary, ending in the dynamic green CTA. The destination is
 * the member's VERIFIED number — the backend ignores any other value, so it is
 * shown read-only.
 */
const WithdrawCheckout: FC<WithdrawCheckoutProps> = ({
  accounts,
  accountNumber,
  onAccountChange,
  availableLabel,
  amount,
  amountError,
  methodId,
  verifiedPhone,
  phoneVerified,
  onAmountChange,
  onMethodChange,
  onConfirm,
  canSubmit,
  isInitiating,
}) => {
  const method: CheckoutPaymentMethod | null =
    CHECKOUT_PAYMENT_METHODS.find((m) => m.id === methodId) ?? null;

  const ctaLabel = isInitiating
    ? "Initiating withdrawal…"
    : `Withdraw ${formatDepositMoney(amount)}`;

  return (
    <div className="space-y-3">
      <WithdrawSource
        accounts={accounts}
        accountNumber={accountNumber}
        onAccountChange={onAccountChange}
      />

      <WithdrawAmountInput
        value={amount}
        error={amountError}
        maxLabel={availableLabel}
        onChange={onAmountChange}
      />

      <PaymentMethodSelector
        value={methodId}
        phone={verifiedPhone}
        onChange={onMethodChange}
        subtitle="The payout is pushed to your verified mobile money number below."
      />

      <WithdrawRecipient phone={verifiedPhone} verified={phoneVerified} />

      <WithdrawSummary amount={amount} method={method} phone={verifiedPhone} />

      <button
        type="button"
        onClick={onConfirm}
        disabled={!canSubmit || isInitiating}
        className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#115036] px-6 text-[15px] font-semibold text-white shadow-soft transition hover:bg-[#0e442d] active:translate-y-px focus:outline-none focus-visible:ring-2 focus-visible:ring-[#115036]/40 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isInitiating ? (
          <>
            <Spinner />
            <span>{ctaLabel}</span>
          </>
        ) : (
          ctaLabel
        )}
      </button>

      <p className="flex items-center justify-center gap-1.5 px-1 text-[11px] text-slate-400">
        <LucideIcon name="Lock" size={12} />
        Secured by Snippe · Mobile Money · debited only after confirmation
      </p>
    </div>
  );
};

export default WithdrawCheckout;