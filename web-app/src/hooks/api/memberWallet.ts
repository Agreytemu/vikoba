import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CreateDepositPayload,
  CreateWithdrawalPayload,
  memberWalletService,
} from "@/services/memberWallet";

const WALLET_KEYS = ["my-wallet"] as const;

export const useGetMyDeposits = (enabled = true) =>
  useQuery({
    queryKey: [...WALLET_KEYS, "deposits"],
    queryFn: memberWalletService.listDeposits,
    enabled,
  });

export const useGetMyWithdrawals = (enabled = true) =>
  useQuery({
    queryKey: [...WALLET_KEYS, "withdrawals"],
    queryFn: memberWalletService.listWithdrawals,
    enabled,
  });

export const useGetMyStatement = (accountNumber?: string) =>
  useQuery({
    queryKey: [...WALLET_KEYS, "statement", accountNumber],
    queryFn: () => memberWalletService.getStatement(accountNumber as string),
    enabled: Boolean(accountNumber),
  });

export const useCreateDeposit = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateDepositPayload) => memberWalletService.createDeposit(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WALLET_KEYS });
      queryClient.invalidateQueries({ queryKey: ["my-accounts"] });
    },
  });
};

export const useCreateWithdrawal = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateWithdrawalPayload) => memberWalletService.createWithdrawal(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WALLET_KEYS });
      queryClient.invalidateQueries({ queryKey: ["my-accounts"] });
    },
  });
};