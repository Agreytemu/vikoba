import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AutoWithdrawalPayload,
  InitiateContributionPayload,
  InitiateLoanRepaymentPayload,
  InitiateSavingsDepositPayload,
  InitiateSubscriptionPayload,
  memberPaymentsService,
} from "@/services/memberPayments";

const PAYMENT_KEYS = ["my-payments"] as const;

export const useMyPayments = (enabled = true) =>
  useQuery({
    queryKey: PAYMENT_KEYS,
    queryFn: memberPaymentsService.listMyPayments,
    enabled,
  });

/**
 * Polls one payment until it leaves PENDING/PROCESSING (SUCCESS / FAILED /
 * EXPIRED / VOIDED / CANCELLED), then stops.
 */
export const useMyPaymentStatus = (reference?: string, enabled = true) =>
  useQuery({
    queryKey: [...PAYMENT_KEYS, "status", reference],
    queryFn: () => memberPaymentsService.getMyPayment(reference as string),
    enabled: Boolean(reference) && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "PENDING" || status === "PROCESSING" ? 3500 : false;
    },
  });

export const useInitiateContributionPayment = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: InitiateContributionPayload) =>
      memberPaymentsService.initiateContribution(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PAYMENT_KEYS });
      queryClient.invalidateQueries({ queryKey: ["my-accounts"] });
      queryClient.invalidateQueries({ queryKey: ["my-wallet"] });
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });
};

export const useInitiateLoanRepayment = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: InitiateLoanRepaymentPayload) =>
      memberPaymentsService.initiateLoanRepayment(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PAYMENT_KEYS });
      queryClient.invalidateQueries({ queryKey: ["my-accounts"] });
      queryClient.invalidateQueries({ queryKey: ["my-wallet"] });
      queryClient.invalidateQueries({ queryKey: ["my-loan-accounts"] });
    },
  });
};

export const useInitiateSavingsDeposit = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: InitiateSavingsDepositPayload) =>
      memberPaymentsService.initiateSavingsDeposit(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PAYMENT_KEYS });
      queryClient.invalidateQueries({ queryKey: ["my-accounts"] });
      queryClient.invalidateQueries({ queryKey: ["my-wallet"] });
    },
  });
};

export const useAutoWithdraw = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AutoWithdrawalPayload) => memberPaymentsService.autoWithdraw(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PAYMENT_KEYS });
      queryClient.invalidateQueries({ queryKey: ["my-accounts"] });
      queryClient.invalidateQueries({ queryKey: ["my-wallet"] });
      queryClient.invalidateQueries({ queryKey: ["my-withdrawals"] });
    },
  });
};

/** The member's most recent subscription (used on the checkout landing state). */
export const useMySubscription = (enabled = true) =>
  useQuery({
    queryKey: ["my-subscription"],
    queryFn: memberPaymentsService.getMySubscription,
    enabled,
    retry: false,
  });

export const useInitiateSubscriptionPayment = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: InitiateSubscriptionPayload) =>
      memberPaymentsService.initiateSubscription(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PAYMENT_KEYS });
      queryClient.invalidateQueries({ queryKey: ["my-subscription"] });
      queryClient.invalidateQueries({ queryKey: ["member", "me"] });
    },
  });
};