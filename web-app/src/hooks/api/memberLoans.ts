import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AddDocumentPayload,
  AddGuarantorPayload,
  CreateLoanPayload,
  memberLoansService,
  RepayLoanPayload,
} from "@/services/memberLoans";

const MY_LOANS_KEYS = ["my-loans"] as const;
const MY_LOAN_ACCOUNTS_KEYS = ["my-loan-accounts"] as const;

export const useGetMyLoans = (enabled = true) =>
  useQuery({
    queryKey: [...MY_LOANS_KEYS],
    queryFn: memberLoansService.listMyLoans,
    enabled,
  });

export const useGetMyLoan = (applicationNumber?: string) =>
  useQuery({
    queryKey: [...MY_LOANS_KEYS, applicationNumber],
    queryFn: () => memberLoansService.getMyLoan(applicationNumber as string),
    enabled: Boolean(applicationNumber),
  });

export const useGetLoanTypes = (enabled = true) =>
  useQuery({
    queryKey: ["loan-types"],
    queryFn: memberLoansService.listLoanTypes,
    enabled,
  });

export const useCreateMyLoan = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateLoanPayload) => memberLoansService.createMyLoan(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MY_LOANS_KEYS }),
  });
};

export const useSubmitMyLoan = (applicationNumber: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => memberLoansService.submitMyLoan(applicationNumber),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MY_LOANS_KEYS });
      queryClient.invalidateQueries({ queryKey: [...MY_LOANS_KEYS, applicationNumber] });
    },
  });
};

export const useAddMyGuarantor = (applicationNumber: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AddGuarantorPayload) =>
      memberLoansService.addMyGuarantor(applicationNumber, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: [...MY_LOANS_KEYS, applicationNumber] }),
  });
};

export const useAddMyDocument = (applicationNumber: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AddDocumentPayload) =>
      memberLoansService.addMyDocument(applicationNumber, data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: [...MY_LOANS_KEYS, applicationNumber] }),
  });
};

export const useGetMyLoanAccounts = (enabled = true) =>
  useQuery({
    queryKey: [...MY_LOAN_ACCOUNTS_KEYS],
    queryFn: memberLoansService.listMyLoanAccounts,
    enabled,
  });

export const useGetMyEligibility = (enabled = true) =>
  useQuery({
    queryKey: ["my-eligibility"],
    queryFn: memberLoansService.getMyEligibility,
    enabled,
  });

export const useRepayMyLoan = (loanNumber: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: RepayLoanPayload) => memberLoansService.repayLoan(loanNumber, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MY_LOAN_ACCOUNTS_KEYS });
      queryClient.invalidateQueries({ queryKey: ["my-accounts"] });
    },
  });
};