import { FC, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "react-toastify";
import { useQueryClient } from "@tanstack/react-query";

import Button from "@/components/Button";
import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";
import { SkeletonPage } from "@/components/Skeleton";
import SelectedPlan from "@/components/checkout/SelectedPlan";
import PaymentMethodSelector from "@/components/checkout/PaymentMethodSelector";
import CustomerPaymentForm, { type CustomerDetails, type CustomerFieldErrors } from "@/components/checkout/CustomerPaymentForm";
import PaymentSummary from "@/components/checkout/PaymentSummary";
import { CancelledView, FailedView, ProcessingView, SuccessView } from "@/components/checkout/PaymentStages";
import {
  formatPlanMoney,
  intervalLabel,
  isValidEmail,
  suggestMethod,
  tzPhoneError,
  type SubscriptionStage,
} from "@/components/checkout/planCheckout";
import { normalizeTzPhone } from "@/lib/payments";
import { getApiErrorMessage } from "@/lib/utils";
import { useUserProfileInfo } from "@/hooks/useUserProfile";
import { useGetPlans, useGetMyMemberProfile } from "@/hooks/api/memberSelf";
import { useInitiateSubscriptionPayment, useMyPaymentStatus, useMySubscription } from "@/hooks/api/memberPayments";
import type { MembershipPlan } from "@/services/memberSelf";

const localDigits = (raw?: string | null): string => {
  const d = (raw || "").replace(/\D/g, "");
  if (d.startsWith("255")) return d.slice(3);
  if (d.startsWith("0")) return d.slice(1);
  return d;
};

const emptyCustomer = (): CustomerDetails => ({ fullName: "", email: "", phone: "" });

/**
 * PLAN PAYMENT CHECKOUT — subscribe to an admin-managed plan via Snippe mobile
 * money. The page only decides plan_id + customer details; the Django backend
 * derives the amount from the DB and frees the frontend from money logic.
 */
const PlanCheckoutPage: FC = () => {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const { profile } = useUserProfileInfo();
  const isMember = profile?.role === "ME";

  const { data: me } = useGetMyMemberProfile(isMember);
  const { data: plans, isLoading: plansLoading } = useGetPlans(isMember);

  const initiate = useInitiateSubscriptionPayment();
  const [stage, setStage] = useState<SubscriptionStage>("checkout");
  const [planId, setPlanId] = useState<number | string | null>(null);
  const [txRef, setTxRef] = useState("");
  const [method, setMethod] = useState<string | null>(null);
  const [customer, setCustomer] = useState<CustomerDetails>(emptyCustomer());
  const [errors, setErrors] = useState<CustomerFieldErrors>({});
  const [submitError, setSubmitError] = useState("");

  const { data: pollData } = useMyPaymentStatus(txRef, stage === "processing");
  const { data: subscription } = useMySubscription(stage === "success");

  const plansActive = useMemo(() => (plans ?? []).filter((p) => p.is_active !== false), [plans]);

  // Default selection: the plan pinned in the query string, else the member's
  // current plan if it is still active.
  useEffect(() => {
    if (planId !== null) return;
    const fromQuery = searchParams.get("plan");
    const initial = plansActive.find((p) => String(p.id) === fromQuery);
    if (initial) setPlanId(initial.id);
    else if (me?.selected_plan) {
      const current = plansActive.find((p) => String(p.id) === String((me.selected_plan as MembershipPlan).id));
      if (current) setPlanId(current.id);
    } else if (plansActive.length === 1) setPlanId(plansActive[0].id);
  }, [plansActive, searchParams, me?.selected_plan, planId]);

  // Prefill customer details from the member profile (editable).
  useEffect(() => {
    if (!me) return;
    setCustomer((prev) => ({
      fullName: prev.fullName || `${me.first_name ?? ""} ${me.last_name ?? ""}`.trim(),
      email: prev.email || me.email || "",
      phone: prev.phone || localDigits(me.phone_number),
    }));
  }, [me]);

  const plan = plansActive.find((p) => String(p.id) === String(planId)) ?? null;
  const methodSuggested = suggestMethod(customer.phone);

  // Auto-suggest the network matching the phone until the member chooses.
  useEffect(() => {
    if (stage !== "checkout" || !methodSuggested || method) return;
    setMethod(methodSuggested);
  }, [methodSuggested, method, stage]);

  // Poll outcome → next stage.
  useEffect(() => {
    if (!pollData) return;
    if (pollData.status === "SUCCESS") {
      setStage("success");
      toast.success("Payment Successful — plan activated!");
      queryClient.invalidateQueries({ queryKey: ["my-subscription"] });
      queryClient.invalidateQueries({ queryKey: ["member", "me"] });
    } else if (["FAILED", "VOIDED", "EXPIRED"].includes(pollData.status)) {
      setStage("failed");
    } else if (pollData.status === "CANCELLED") {
      setStage("cancelled");
    }
  }, [pollData, queryClient]);

  const validate = (): CustomerFieldErrors => {
    const next: CustomerFieldErrors = {};
    const name = customer.fullName.trim();
    if (!name || name.length < 2) next.fullName = "Enter your full name";
    if (!isValidEmail(customer.email)) next.email = "Enter a valid email address";
    const phoneErr = tzPhoneError(customer.phone);
    if (phoneErr) next.phone = phoneErr;
    return next;
  };

  const goCheckout = () => {
    setStage("checkout");
    setSubmitError("");
    setErrors({});
  };

  const handleChangeMethod = () => {
    setMethod(null);
    goCheckout();
  };

  const submitPayment = () => {
    if (!plan || initiate.isPending) return;
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0 || !method) {
      if (!method) setSubmitError("Choose a payment method to continue.");
      return;
    }
    setSubmitError("");
    initiate.mutate(
      {
        plan_id: plan.id,
        payment_method: method,
        phone: normalizeTzPhone(customer.phone),
        full_name: customer.fullName.trim(),
        email: customer.email.trim(),
      },
      {
        onSuccess: (data) => {
          setTxRef(data.transaction.reference);
          setStage("processing");
        },
        onError: (err) => {
          const message = getApiErrorMessage(err, "Payment could not be initiated.");
          setSubmitError(message);
          toast.error(message);
        },
      },
    );
  };

  if (!isMember) {
    return <p className="text-slate-500">This page is for members.</p>;
  }

  if (plansLoading) {
    return <SkeletonPage />;
  }

  if (plansActive.length === 0) {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-card dark:border-slate-800 dark:bg-slate-900">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300">
          <LucideIcon name="PackageOpen" size={28} />
        </span>
        <h1 className="mt-4 font-display text-xl font-semibold">No plans available</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Your group administrator hasn't added any subscription plans yet.
        </p>
      </div>
    );
  }

  // --------------------------------- PROCESSING ------------------------------
  if (stage === "processing" && plan && txRef) {
    return (
      <ProcessingView
        plan={plan}
        phone={customer.phone}
        method={method}
        txRef={txRef}
        onCancel={goCheckout}
      />
    );
  }

  // --------------------------------- SUCCESS ----------------------------------
  if (stage === "success" && plan) {
    return (
      <SuccessView
        plan={plan}
        txRef={txRef}
        method={method}
        amount={plan.price}
        subscription={subscription ?? null}
      />
    );
  }

  // --------------------------------- FAILED -----------------------------------
  if (stage === "failed" && plan) {
    return <FailedView plan={plan} txRef={txRef} onRetry={goCheckout} onChangeMethod={handleChangeMethod} />;
  }

  // --------------------------------- CANCELLED --------------------------------
  if (stage === "cancelled" && plan) {
    return <CancelledView plan={plan} onBack={goCheckout} />;
  }

  // --------------------------------- CHECKOUT ---------------------------------
  return (
    <div className="mx-auto max-w-lg space-y-5">
      <div>
        <h1 className="font-display text-2xl font-semibold">Complete Payment</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {plan ? `Subscribe to ${plan.name}` : "Choose the plan you want to subscribe to"}
        </p>
      </div>

      {!plan && (
        <div className="grid gap-3">
          {plansActive.map((p) => (
            <button
              key={String(p.id)}
              type="button"
              onClick={() => setPlanId(p.id)}
              className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-card transition hover:border-[#115036]/40 dark:border-slate-800 dark:bg-slate-900"
            >
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[#115036]/10 text-[#115036] dark:bg-[#115036]/20 dark:text-emerald-300">
                <LucideIcon name="Crown" size={22} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-[15px] font-semibold text-slate-900 dark:text-white">{p.name}</span>
                <span className="block text-[12px] text-slate-400">
                  {p.features?.length ?? 0} feature{(p.features?.length ?? 0) === 1 ? "" : "s"} · {intervalLabel(p.interval)}
                </span>
              </span>
              <span className="font-display text-base font-bold text-[#115036] dark:text-emerald-300">
                {formatPlanMoney(p.price, p.currency)}
              </span>
            </button>
          ))}
        </div>
      )}

      {plan && (
        <>
          <SelectedPlan plan={plan} onChangePlan={() => setPlanId(null)} />

          {subscription?.status === "ACTIVE" && (
            <div className="flex items-center gap-2 rounded-2xl bg-[#115036]/5 px-4 py-3 text-xs text-[#115036] dark:bg-emerald-950/30 dark:text-emerald-300">
              <LucideIcon name="ShieldCheck" size={15} className="shrink-0" />
              <span>
                You already have the {plan.name} plan active
                {subscription.expires_at
                  ? ` until ${new Date(subscription.expires_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}`
                  : ""}
                . Paying again extends it from today.
              </span>
            </div>
          )}

          <PaymentMethodSelector value={method} phone={customer.phone} onChange={setMethod} />

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
            <CustomerPaymentForm
              value={customer}
              errors={errors}
              onChange={(field, value) => {
                setCustomer((prev) => ({ ...prev, [field]: value }));
                setErrors((prev) => ({ ...prev, [field]: undefined }));
                setSubmitError("");
              }}
              onBlur={(field) => {
                const next = validate();
                setErrors((prev) => ({ ...prev, [field]: next[field] }));
              }}
            />
          </div>

          <PaymentSummary plan={plan} />

          {submitError && (
            <div className="flex items-start gap-2 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
              <LucideIcon name="AlertCircle" size={15} className="mt-0.5 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}

          <Button
            text={initiate.isPending ? <Spinner /> : `Pay ${formatPlanMoney(plan.price, plan.currency)}`}
            variant="primary"
            disabled={initiate.isPending}
            onClick={submitPayment}
            className="w-full"
          />

          <p className="flex items-center justify-center gap-1.5 text-[11px] text-slate-400">
            <LucideIcon name="Lock" size={12} />
            Secured by Snippe · Mobile Money
          </p>
        </>
      )}
    </div>
  );
};

export default PlanCheckoutPage;