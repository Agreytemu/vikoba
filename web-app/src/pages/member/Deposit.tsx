import { FC, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { useQueryClient } from "@tanstack/react-query";

import { SkeletonPage } from "@/components/Skeleton";
import DepositCheckout from "@/components/checkout/deposit/DepositCheckout";
import DepositFailed from "@/components/checkout/deposit/DepositFailed";
import DepositSuccess from "@/components/checkout/deposit/DepositSuccess";
import PaymentProcessing from "@/components/checkout/deposit/PaymentProcessing";
import {
  depositAmountError,
  normalizeDepositAmount,
  type DepositStage,
} from "@/components/checkout/deposit/depositFlow";
import { suggestMethod, tzPhoneError } from "@/components/checkout/planCheckout";
import { useUserProfileInfo } from "@/hooks/useUserProfile";
import { useGetMyMemberProfile } from "@/hooks/api/memberSelf";
import { useGetMyAccounts } from "@/hooks/api/myAccounts";
import { useCurrency } from "@/contexts/CurrencyContext";
import { useInitiateSavingsDeposit, useMyPaymentStatus } from "@/hooks/api/memberPayments";
import { normalizeTzPhone } from "@/lib/payments";
import { getApiErrorMessage } from "@/lib/utils";

/**
 * Member wallet deposit — mobile money → savings account via Snippe.
 *
 * Credit happens ONLY when the verified webhook reports success; this page only
 * moves to the success screen after the status poll confirms it. The amount is
 * always the member's own input (min/max validated inline), the fee is the
 * fixed backend fee (TZS 0 for Snippe collections) and the CTA is dynamic.
 */
const Deposit: FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { formatMoney } = useCurrency();
  const { profile } = useUserProfileInfo();

  const isMember = profile?.role === "ME";
  const { data: me, isLoading: meLoading } = useGetMyMemberProfile(isMember);
  const { data: accounts, isLoading: accLoading } = useGetMyAccounts();

  const initiate = useInitiateSavingsDeposit();

  const [stage, setStage] = useState<DepositStage>("checkout");
  const [amount, setAmount] = useState("");
  const [methodId, setMethodId] = useState<string | null>(null);
  const [methodTouched, setMethodTouched] = useState(false);
  const [phone, setPhone] = useState("");
  const [txRef, setTxRef] = useState("");
  const [failedStatus, setFailedStatus] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const { data: pollData } = useMyPaymentStatus(txRef, stage === "processing");

  // Default the mobile-money number to the member's own profile number.
  useEffect(() => {
    if (!phone && me?.phone_number) setPhone(me.phone_number);
  }, [me, phone]);

  // Pre-suggest the brand matching the number until the member picks their own.
  useEffect(() => {
    if (methodTouched) return;
    setMethodId(suggestMethod(phone) ?? null);
  }, [phone, methodTouched]);

  // The poll only matters while we are waiting for the provider's webhook.
  useEffect(() => {
    if (!pollData) return;
    if (pollData.status === "SUCCESS") {
      setStage("success");
      toast.success("Deposit confirmed!");
      queryClient.invalidateQueries({ queryKey: ["my-accounts"] });
      queryClient.invalidateQueries({ queryKey: ["my-wallet"] });
      queryClient.invalidateQueries({ queryKey: ["my-payments"] });
    } else if (["FAILED", "VOIDED", "EXPIRED", "CANCELLED"].includes(pollData.status)) {
      setFailedStatus(pollData.status);
      setStage("failed");
    }
  }, [pollData, queryClient]);

  const amountErr = depositAmountError(amount);
  const phoneErr = tzPhoneError(phone);
  const amountError = submitted ? amountErr : null;
  const phoneError = submitted ? phoneErr : null;

  const hasAll =
    amount.trim() !== "" && phone.trim() !== "" && Boolean(methodId);

  const memberName = [me?.first_name, me?.last_name].filter(Boolean).join(" ").trim();
  const primaryAccount = accounts?.accounts?.[0];
  const accountNumber = primaryAccount?.account_number ?? "";
  const availableBalance = formatMoney(Number(accounts?.total_balance || 0));

  const handleAmount = (raw: string) => setAmount(normalizeDepositAmount(raw));

  const handleMethod = (id: string) => {
    setMethodTouched(true);
    setMethodId(id);
  };

  const resetForm = () => {
    setStage("checkout");
    setAmount("");
    setMethodId(null);
    setMethodTouched(false);
    setPhone(me?.phone_number ?? "");
    setTxRef("");
    setFailedStatus("");
    setSubmitted(false);
  };

  const confirmPayment = () => {
    setSubmitted(true);
    if (amountErr || phoneErr || !methodId) return;

    initiate.mutate(
      {
        amount: String(Number(normalizeDepositAmount(amount))),
        phone: normalizeTzPhone(phone),
      },
      {
        onSuccess: (data) => {
          setTxRef(data.reference);
          setStage("processing");
        },
        onError: (error) => {
          toast.error(getApiErrorMessage(error, "Payment could not be initiated."));
        },
      },
    );
  };

  if (!isMember) {
    return <p className="text-slate-500">This page is for members.</p>;
  }

  if (meLoading || accLoading) {
    return <SkeletonPage />;
  }

  const header = (
    <div>
      <h1 className="font-display text-2xl font-semibold">Make a deposit</h1>
      <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
        Deposit money from your mobile money into your savings — credited
        automatically once the payment is confirmed.
      </p>
    </div>
  );

  if (stage === "processing") {
    return (
      <div className="mx-auto w-full max-w-xl space-y-5">
        {header}
        <PaymentProcessing
          amount={amount}
          phone={phone}
          onBack={resetForm}
          canBack={!initiate.isPending}
        />
      </div>
    );
  }

  if (stage === "success") {
    return (
      <div className="mx-auto w-full max-w-xl space-y-5">
        {header}
        <DepositSuccess
          amount={amount}
          accountNumber={accountNumber}
          memberName={memberName}
          reference={txRef}
          onViewWallet={() => navigate("/wallet")}
          onDone={() => navigate("/")}
        />
      </div>
    );
  }

  if (stage === "failed") {
    return (
      <div className="mx-auto w-full max-w-xl space-y-5">
        {header}
        <DepositFailed
          amount={amount}
          status={failedStatus}
          reference={txRef || undefined}
          onRetry={resetForm}
          onHelp={() => navigate("/help")}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-xl">
      <div className="mb-5">{header}</div>
      <DepositCheckout
        memberName={memberName}
        membershipNumber={me?.membership_number ?? ""}
        accountNumber={accountNumber}
        availableBalance={availableBalance}
        amount={amount}
        amountError={amountError}
        methodId={methodId}
        phone={phone}
        phoneError={phoneError}
        onAmountChange={handleAmount}
        onMethodChange={handleMethod}
        onPhoneChange={setPhone}
        onConfirm={confirmPayment}
        canSubmit={hasAll && !initiate.isPending}
        isInitiating={initiate.isPending}
      />
    </div>
  );
};

export default Deposit;