import { FC } from "react";

import LucideIcon from "@/components/LucideIcon";
import Spinner from "@/components/Spinner";
import PaymentMethodSelector from "@/components/checkout/PaymentMethodSelector";
import DepositAmountInput from "./DepositAmountInput";
import DepositDestination from "./DepositDestination";
import DepositSummary from "./DepositSummary";
import MobileMoneyNumberInput from "./MobileMoneyNumberInput";
import { formatDepositMoney } from "./depositFlow";
import { CHECKOUT_PAYMENT_METHODS, type CheckoutPaymentMethod } from "../planCheckout";

interface DepositCheckoutProps {
  memberName: string;
  membershipNumber: string;
  accountNumber: string;
  availableBalance: string;
  amount: string;
  amountError: string | null;
  methodId: string | null;
  phone: string;
  phoneError: string | null;
  onAmountChange: (raw: string) => void;
  onMethodChange: (id: string) => void;
  onPhoneChange: (raw: string) => void;
  onConfirm: () => void;
  canSubmit: boolean;
  isInitiating: boolean;
}

/**
 * The enter-deposit screen: destination, amount, payment brand, mobile number
 * and summary, ending in the dynamic green CTA. Validation messages are inline;
 * the CTA reflects the current state (disabled / initiating / ready).
 */
const DepositCheckout: FC<DepositCheckoutProps> = ({
  memberName,
  membershipNumber,
  accountNumber,
  availableBalance,
  amount,
  amountError,
  methodId,
  phone,
  phoneError,
  onAmountChange,
  onMethodChange,
  onPhoneChange,
  onConfirm,
  canSubmit,
  isInitiating,
}) => {
  const method: CheckoutPaymentMethod | null =
    CHECKOUT_PAYMENT_METHODS.find((m) => m.id === methodId) ?? null;

  const ctaLabel = isInitiating
    ? "Initiating deposit…"
    : `Deposit ${formatDepositMoney(amount)}`;

  return (
    <div className="space-y-3">
      <DepositDestination
        memberName={memberName}
        membershipNumber={membershipNumber}
        accountNumber={accountNumber}
        availableBalance={availableBalance}
      />

      <DepositAmountInput value={amount} error={amountError} onChange={onAmountChange} />

      <PaymentMethodSelector value={methodId} phone={phone} onChange={onMethodChange} />

      <MobileMoneyNumberInput
        value={phone}
        error={phoneError}
        onChange={onPhoneChange}
      />

      <DepositSummary amount={amount} method={method} phone={phone} />

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
        Secured by Snippe · Mobile Money · credited only after confirmation
      </p>
    </div>
  );
};

export default DepositCheckout;