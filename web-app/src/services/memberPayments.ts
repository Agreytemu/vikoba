import api from "@/lib/api";
import type { SnippeNetworkId } from "@/lib/payments";

// Member-facing Snippe-powered flows. All money movement goes through the
// Django backend — the frontend never talks to Snippe directly.

export interface PaymentTransaction {
  id: number;
  reference: string;
  transaction_type: string;
  amount: string;
  currency: string;
  status: string;
  provider: string;
  provider_reference: string | null;
  internal_reference: string;
  fee: string;
  net_amount: string;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface InitiateContributionPayload {
  group_id: number;
  amount: string;
  month: string; // YYYY-MM
  phone?: string;
}

export interface InitiateLoanRepaymentPayload {
  loan_number: string;
  installment_number: number;
  phone?: string;
}

export interface InitiateSavingsDepositPayload {
  amount: string;
  phone?: string;
}

export interface AutoWithdrawalPayload {
  account_number: string;
  amount: string;
  narration?: string;
  /** The Snippe network the payout settles on (mpesa / airtel / mixx / halotel). */
  network?: SnippeNetworkId;
}

export interface WithdrawalRequestSummary {
  id: number;
  status: string;
  amount: string;
  narration?: string;
  created_at: string;
}

export interface AutoWithdrawalResult {
  withdrawal: WithdrawalRequestSummary;
  payout?: PaymentTransaction | null;
  /** Straight-through (AUTO_APPROVED) vs manual review (MANUAL_REVIEW). */
  decision?: string;
  decision_reason?: string;
  /** True when this withdrawal needs a staff/committee decision before payout. */
  review_required?: boolean;
  /** The governance ApprovalRequest id when review_required, otherwise null. */
  approval_id?: number | null;
}

export interface SubscriptionPlan {
  id: number;
  name: string;
  price: string;
  currency: string;
  interval: string;
}

export interface MemberSubscription {
  id: number;
  status: "PENDING" | "ACTIVE" | "EXPIRED" | "CANCELLED" | "FAILED";
  plan: SubscriptionPlan;
  payment_reference: string | null;
  started_at: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InitiateSubscriptionPayload {
  plan_id: number | string;
  payment_method: string;
  phone: string;
  full_name: string;
  email: string;
}

export interface InitiateSubscriptionResult {
  transaction: PaymentTransaction;
  subscription: MemberSubscription;
}

export const memberPaymentsService = {
  /** Start a mobile-money contribution for the selected group. */
  initiateContribution: (data: InitiateContributionPayload) =>
    api.post("/payments/contributions/pay/", data) as Promise<PaymentTransaction>,

  /** Start a mobile-money repayment for one loan installment. */
  initiateLoanRepayment: (data: InitiateLoanRepaymentPayload) =>
    api.post("/payments/loans/repay/", data) as Promise<PaymentTransaction>,

  /** Top up the member's own savings account via Snippe mobile money. */
  initiateSavingsDeposit: (data: InitiateSavingsDepositPayload) =>
    api.post("/payments/savings/deposit/", data) as Promise<PaymentTransaction>,

  /** Withdraw straight to the member's phone — the system approves itself. */
  autoWithdraw: (data: AutoWithdrawalPayload) =>
    api.post("/payments/withdrawals/auto/", data) as Promise<AutoWithdrawalResult>,

  /** The current member's recent payments. */
  listMyPayments: () =>
    api.get("/payments/transactions/") as Promise<PaymentTransaction[]>,

  /** Live status of one payment by internal reference (used for polling). */
  getMyPayment: (reference: string) =>
    api.get(`/payments/transactions/${reference}/`) as Promise<PaymentTransaction>,

  /** Start a mobile-money payment for the member's chosen plan subscription. */
  initiateSubscription: (data: InitiateSubscriptionPayload) =>
    api.post("/payments/subscriptions/checkout/", data) as Promise<InitiateSubscriptionResult>,

  /** The member's most recent subscription (with nested plan). */
  getMySubscription: () =>
    api.get("/payments/subscriptions/me/") as Promise<MemberSubscription>,
};