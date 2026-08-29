import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AddContributionPayload,
  BuySharesPayload,
  CreateGroupPayload,
  groupsService,
} from "@/services/groups";

const GROUP_KEYS = ["groups"] as const;

export const useGetMyGroups = (enabled = true) =>
  useQuery({ queryKey: [...GROUP_KEYS], queryFn: groupsService.listMyGroups, enabled });

export const useGetMyGroupsSummary = (enabled = true) =>
  useQuery({
    queryKey: [...GROUP_KEYS, "summary"],
    queryFn: groupsService.mySummary,
    enabled,
  });

export const useGetCommittee = (groupId?: number | string) =>
  useQuery({
    queryKey: [...GROUP_KEYS, groupId, "committee"],
    queryFn: () => groupsService.committee(groupId as number | string),
    enabled: groupId !== undefined && groupId !== null && groupId !== "",
  });

export const useDeclareCandidacy = (groupId?: number | string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (role: string) =>
      groupsService.declareCandidacy(groupId as number | string, role),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: [...GROUP_KEYS, groupId, "committee"],
      }),
  });
};

export const useVoteCommittee = (groupId?: number | string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ role, candidate_id }: { role: string; candidate_id: string }) =>
      groupsService.voteCommittee(groupId as number | string, role, candidate_id),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: [...GROUP_KEYS, groupId, "committee"],
      }),
  });
};

export const useCloseCommittee = (groupId?: number | string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (role: string) =>
      groupsService.closeCommittee(groupId as number | string, role),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [...GROUP_KEYS, groupId, "committee"],
      });
      queryClient.invalidateQueries({ queryKey: [...GROUP_KEYS, groupId] });
    },
  });
};

export const useGetGroup = (groupId?: number | string) =>
  useQuery({
    queryKey: [...GROUP_KEYS, groupId],
    queryFn: () => groupsService.getGroup(groupId as number | string),
    enabled: groupId !== undefined && groupId !== null && groupId !== "",
  });

export const useGetPendingInvitations = (enabled = true) =>
  useQuery({
    queryKey: [...GROUP_KEYS, "invitations"],
    queryFn: groupsService.pendingInvitations,
    enabled,
  });

export const useCreateGroup = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateGroupPayload) => groupsService.createGroup(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: GROUP_KEYS }),
  });
};

export const useInviteToGroup = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ groupId, email }: { groupId: number | string; email: string }) =>
      groupsService.invite(groupId, email),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: GROUP_KEYS }),
  });
};

export const useJoinGroup = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ groupId, token }: { groupId: number | string; token: string }) =>
      groupsService.join(groupId, token),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: GROUP_KEYS }),
  });
};

export const useAcceptInvite = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => groupsService.acceptInvite(token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: GROUP_KEYS });
      queryClient.invalidateQueries({ queryKey: ["groups", "invitations"] });
    },
  });
};

export const useBuyShares = (groupId?: number | string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: BuySharesPayload) =>
      groupsService.buyShares(groupId as number | string, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: GROUP_KEYS });
      queryClient.invalidateQueries({ queryKey: [...GROUP_KEYS, groupId] });
    },
  });
};

export const useGetContributions = (groupId?: number | string) =>
  useQuery({
    queryKey: [...GROUP_KEYS, groupId, "contributions"],
    queryFn: () => groupsService.listContributions(groupId as number | string),
    enabled: groupId !== undefined && groupId !== null && groupId !== "",
  });

export const useAddContribution = (groupId?: number | string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AddContributionPayload) =>
      groupsService.addContribution(groupId as number | string, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...GROUP_KEYS, groupId, "contributions"] });
    },
  });
};