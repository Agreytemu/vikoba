import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApprovalActionPayload,
  ApprovalFilters,
  GroupWithdrawalPolicyPayload,
  governanceService,
} from "@/services/governance";

const APPROVAL_KEYS = ["approvals"] as const;
const POLICY_KEYS = ["withdrawal-policy"] as const;

export const useApprovals = (filters?: ApprovalFilters) =>
  useQuery({
    queryKey: [...APPROVAL_KEYS, "list", filters],
    queryFn: () => governanceService.listApprovals(filters),
  });

export const useApproval = (approvalId?: number | string) =>
  useQuery({
    queryKey: [...APPROVAL_KEYS, "detail", approvalId],
    queryFn: () => governanceService.getApproval(approvalId as number | string),
    enabled: Boolean(approvalId),
  });

export const useApprovalHistory = (approvalId?: number | string) =>
  useQuery({
    queryKey: [...APPROVAL_KEYS, approvalId, "history"],
    queryFn: () => governanceService.approvalHistory(approvalId as number | string),
    enabled: Boolean(approvalId),
  });

export const useApprovalAction = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ approvalId, data }: { approvalId: number | string; data: ApprovalActionPayload }) =>
      governanceService.actOnApproval(approvalId, data),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: APPROVAL_KEYS });
      queryClient.invalidateQueries({ queryKey: [APPROVAL_KEYS[0], "detail", variables.approvalId] });
      queryClient.invalidateQueries({ queryKey: ["my-withdrawals"] });
      queryClient.invalidateQueries({ queryKey: ["my-payments"] });
      queryClient.invalidateQueries({ queryKey: ["my-wallet"] });
      queryClient.invalidateQueries({ queryKey: ["my-accounts"] });
    },
  });
};

export const useGroupWithdrawalPolicy = (groupId?: number | string) =>
  useQuery({
    queryKey: [...POLICY_KEYS, groupId],
    queryFn: () => governanceService.getGroupWithdrawalPolicy(groupId as number | string),
    enabled: Boolean(groupId),
  });

export const useUpdateGroupWithdrawalPolicy = (groupId?: number | string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: GroupWithdrawalPolicyPayload) =>
      governanceService.updateGroupWithdrawalPolicy(groupId as number | string, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [POLICY_KEYS[0], groupId] });
    },
  });
};