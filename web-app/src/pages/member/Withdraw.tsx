import { FC, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";

import { SkeletonPage } from "@/components/Skeleton";
import LucideIcon from "@/components/LucideIcon";
import VerificationGate from "@/components/VerificationGate";
import WithdrawCheckout from "@/components/checkout/withdraw/WithdrawCheckout";
import WithdrawFailed from "@/components/checkout/withdraw/WithdrawFailed";
import WithdrawProcessing from "@/components/checkout/withdraw/WithdrawProcessing";
import WithdrawSuccess from "@/components/checkout/withdraw/WithdrawSuccess";
import {
  normalizeWithdrawAmount,
  withdrawAmountError,
  type WithdrawStage,
} from "@/components/checkout/withdraw/withdrawFlow";
import { CHECKOUT_PAYMENT_METHODS, suggestMethod } from "@/components/checkout/planCheckout";
import { useUserProfileInfo } from "@/hooks/useUserProfile";
import { useGetMyMemberProfile } from "@/hooks/api/memberSelf";
import { useGetMyAccounts } from "@/hooks/api/myAccounts";
import { useCurrency } from "@/contexts/CurrencyContext";
import { useAutoWithdraw, useMyPaymentStatus } from "@/hooks/api/memberPayments";
import { getApiErrorMessage } from "@/lib/utils";

/**
 * Member withdrawal — savings account → verified mobile money via Snippe.
 *
 * The payout ALWAYS goes to the member's verified number: the backend ignores
 * any client-supplied phone, so this page only ever shows that number (read-only)
 * and only moves to success after the verified payout webhook confirms it.
 */
const Withdraw: FC = () => {
  const navigate = useNavigate();
  const { formatMoney } = useCurrency();
  const { profile } = useUserProfileInfo();

  const isMember = profile?.role === "ME";
  const { data: me, isLoading: meLoading } = useGetMyMemberProfile(isMember);
  const { data: accounts, isLoading: accLoading } = useGetMyAccounts();

  const withdraw = useAutoWithdraw();

  const [stage, setStage] = useState<WithdrawStage>("checkout");
  const [accountNumber, setAccountNumber] = useState("");
  const [amount, setAmount] = useState("");
  const [methodId, setMethodId] = useState<string | null>(null);
  const [gateOpen, setGateOpen] = useState(false);
  const [payoutRef, setPayoutRef] = useState("");
  const [failedStatus, setFailedStatus] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [reviewed, setReviewed] = useState(false);

  // Default the source to the first savings account.
  useEffect(() => {
    if (!accountNumber && accounts?.accounts?.[0]?.account_number) {
      setAccountNumber(accounts.accounts[0].account_number);
    }
  }, [accounts, accountNumber]);

  // Pre-suggest the brand matching the verified number (payouts resolve to it).
  useEffect(() => {
    if (!methodId && me?.phone_number) setMethodId(suggestMethod(me.phone_number));
  }, [me, methodId]);

  // The poll only matters while we are waiting for the provider's webhook.
  const { data: pollData } = useMyPaymentStatus(payoutRef, stage === "processing");

  // React to the payout status poll (payout.completed / payout.failed webhook).
  useEffect(() => {
    if (!pollData) return;
    if (pollData.status === "SUCCESS") {
      setStage("success");
      toast.success("Withdrawal sent to your phone!");
    } else if (["FAILED", "VOIDED", "EXPIRED", "CANCELLED"].includes(pollData.status)) {
      setFailedStatus(pollData.status);
      setStage("failed");
    }
  }, [pollData]);

  if (!isMember) {
    return <p className="text-slate-500">This page is for members.</p>;
  }

  if (meLoading || accLoading) {
    return <SkeletonPage />;
  }

  const isVerified = Boolean(me?.is_verified) && Boolean(me?.phone_verified);
  const accountsList = accounts?.accounts ?? [];
  const selected =
    accountsList.find((a) => a.account_number === accountNumber) ?? accountsList[0];
  const availableBalance = Number(selected?.balance || 0);
  const availableLabel = formatMoney(availableBalance);
  const verifiedPhone = me?.phone_number ?? "";

  const amountErr = withdrawAmountError(amount, availableBalance);
  const amountError = submitted ? amountErr : null;
  const hasAll = amount.trim() !== "" && Boolean(methodId) && Boolean(accountNumber);
  // The member's brand choice drives the Snippe payout network (the backend
  // still pays out only to the verified number, on the chosen network).
  const method = CHECKOUT_PAYMENT_METHODS.find((m) => m.id === methodId);
  const network = method?.networkId ?? undefined;

  const submit = () => {
    setSubmitted(true);
    if (amountErr || !methodId || !accountNumber || !network) return;
    if (!isVerified) {
      setGateOpen(true);
      return;
    }
    withdraw.mutate(
      {
        account_number: accountNumber,
        amount: String(Number(normalizeWithdrawAmount(amount))),
        network,
      },
      {
        onSuccess: (data) => {
          if (data.review_required) {
            toast.success(
              "Withdrawal submitted for review — a staff officer will approve it shortly.",
            );
            setReviewed(true);
            setStage("review");
            return;
          }
          if (data.payout?.reference) {
            setPayoutRef(data.payout.reference);
            setStage("processing");
          } else if (data.withdrawal?.status === "PENDING") {
            // Amounts below the provider minimum stay as pending requests.
            toast.success("Withdrawal submitted. It will be processed shortly.");
            setStage("review");
          }
        },
        onError: (err) => {
          toast.error(getApiErrorMessage(err, "Withdrawal could not be sent."));
        },
      },
    );
  };

  const resetForm = () => {
    setStage("checkout");
    setAmount("");
    setSubmitted(false);
    setPayoutRef("");
    setFailedStatus("");
    setReviewed(false);
  };

  const header = (
    <div>
      <h1 className="font-display text-2xl font-semibold">Withdraw</h1>
      <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
        Send money from your savings to your verified mobile money number —
        no staff approval needed.
      </p>
    </div>
  );

  if (stage === "processing") {
    return (
      <div className="mx-auto w-full max-w-xl space-y-5">
        {header}
        <WithdrawProcessing
          amount={amount}
          phone={verifiedPhone}
          onBack={resetForm}
          canBack={!withdraw.isPending}
        />
      </div>
    );
  }

  if (stage === "review") {
    return (
      <div className="mx-auto w-full max-w-xl space-y-5">
        {header}
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-6 dark:border-amber-700/50 dark:bg-amber-950/30">
          <div className="flex items-start gap-3">
            <LucideIcon name="Clock" size={22} className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
            <div>
              <h2 className="font-display text-base font-semibold text-amber-900 dark:text-amber-200">
                {reviewed ? "Submitted for approval" : "Pending approval"}
              </h2>
              <p className="mt-1 text-sm text-amber-800 dark:text-amber-300">
                {reviewed
                  ? "Your withdrawal amount is above your group's auto-approval limit, so a staff officer or committee member must approve it before the money is sent to your phone. You'll see it as pending in your wallet."
                  : "This withdrawal is waiting for an officer to approve it before payout."}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => navigate("/wallet")}
            className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white dark:bg-slate-100 dark:text-slate-900"
          >
            View wallet
            <LucideIcon name="ArrowRight" size={16} />
          </button>
        </div>
      </div>
    );
  }

  if (stage === "success") {
    return (
      <div className="mx-auto w-full max-w-xl space-y-5">
        {header}
        <WithdrawSuccess
          amount={amount}
          phone={verifiedPhone}
          reference={payoutRef}
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
        <WithdrawFailed
          amount={amount}
          status={failedStatus}
          reference={payoutRef || undefined}
          onRetry={resetForm}
          onHelp={() => navigate("/help")}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-xl">
      <div className="mb-5">{header}</div>

      <WithdrawCheckout
        accounts={accountsList}
        accountNumber={accountNumber}
        onAccountChange={setAccountNumber}
        availableLabel={availableLabel}
        amount={amount}
        amountError={amountError}
        methodId={methodId}
        verifiedPhone={verifiedPhone}
        phoneVerified={Boolean(me?.phone_verified)}
        onAmountChange={(raw) => setAmount(normalizeWithdrawAmount(raw))}
        onMethodChange={setMethodId}
        onConfirm={submit}
        canSubmit={hasAll && !withdraw.isPending}
        isInitiating={withdraw.isPending}
      />

      {!isVerified && (
        <div className="mt-5 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/30 dark:text-amber-200">
          <LucideIcon name="ShieldAlert" size={18} className="mt-0.5 shrink-0" />
          <p>
            Withdrawals go only to your verified number and require a verified
            account. Verify your phone, ID, next of kin and passport photo first.
          </p>
        </div>
      )}

      <VerificationGate
        open={gateOpen}
        onClose={() => setGateOpen(false)}
        message="Finish your verification before you can withdraw: confirm your phone, add a next of kin, upload your ID, passport photo and signature, then staff approve them."
      />
    </div>
  );
};

export default Withdraw;