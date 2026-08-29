import api from "@/lib/api";

export interface MemberBrief {
  membership_number: string;
  first_name: string;
  last_name: string;
  profile_image?: string | null;
}

export interface GroupMembershipInfo {
  id: number;
  member: MemberBrief;
  role: string;
  shares_count: number;
  joined_at: string;
  is_active: boolean;
}

export interface GroupSummary {
  id: number;
  name: string;
  area: string;
  region: string;
  country: string;
  status: string;
  member_count: number;
  my_shares: number;
  my_role: string | null;
}

export interface GroupDetail extends GroupSummary {
  description: string;
  created_by?: MemberBrief | null;
  created_at: string;
  total_shares: number;
  members: GroupMembershipInfo[];
}

export interface GroupSummaryStats {
  total_shares: number;
  hisa_value: number;
  contributed_total: number;
  contributed_pending: number;
  group_count: number;
  created_count: number;
}

export interface CommitteeCandidate {
  member: MemberBrief;
  member_id: string;
  votes: number;
  declared_at: string;
}

export interface CommitteeRoleState {
  role: string;
  open: boolean;
  candidates: CommitteeCandidate[];
  my_vote: string | null;
  my_candidacy: boolean;
}

export interface CommitteeState {
  chairperson: MemberBrief | null;
  treasurer: MemberBrief | null;
  secretary: MemberBrief | null;
  is_chairperson: boolean;
  roles: {
    TREASURER: CommitteeRoleState;
    SECRETARY: CommitteeRoleState;
  };
}

export interface ElectedMember {
  role: string;
  member: MemberBrief | null;
}

export interface GroupInvitation {
  id: number;
  group_id: number;
  group_name: string;
  email: string;
  status: string;
  token: string;
  expires_at: string;
  created_at: string;
}

export interface GroupShareRecord {
  id: number;
  member: MemberBrief;
  quantity: number;
  amount_paid: string;
  created_at: string;
}

export interface GroupContribution {
  id: number;
  member: MemberBrief;
  amount: string;
  month: string;
  reference: string;
  status: string;
  status_display: string;
  created_at: string;
}

export interface CreateGroupPayload {
  name: string;
  area?: string;
  region?: string;
  country?: string;
  description?: string;
}

export interface InvitePayload {
  email: string;
}

export interface BuySharesPayload {
  quantity: number;
  amount_paid: string;
}

export interface AddContributionPayload {
  amount: string;
  month: string;
  reference?: string;
}

export const groupsService = {
  listMyGroups: () =>
    api.get("/groups") as Promise<GroupSummary[]>,

  mySummary: () =>
    api.get("/groups/me/summary") as Promise<GroupSummaryStats>,

  getGroup: (groupId: number | string) =>
    api.get(`/groups/${groupId}`) as Promise<GroupDetail>,

  createGroup: (data: CreateGroupPayload) =>
    api.post("/groups", data) as Promise<GroupDetail>,

  committee: (groupId: number | string) =>
    api.get(`/groups/${groupId}/committee`) as Promise<CommitteeState>,

  declareCandidacy: (groupId: number | string, role: string) =>
    api.post(`/groups/${groupId}/committee/declare`, { role }) as Promise<{
      role: string;
      created: boolean;
    }>,

  voteCommittee: (
    groupId: number | string,
    role: string,
    candidate_id: string,
  ) =>
    api.post(`/groups/${groupId}/committee/vote`, {
      role,
      candidate_id,
    }) as Promise<{ role: string; candidate_id: string }>,

  closeCommittee: (groupId: number | string, role: string) =>
    api.post(`/groups/${groupId}/committee/close`, { role }) as Promise<ElectedMember>,

  pendingInvitations: () =>
    api.get("/groups/invitations/pending") as Promise<GroupInvitation[]>,

  invite: (groupId: number | string, email: string) =>
    api.post(`/groups/${groupId}/invite`, { email }) as Promise<GroupInvitation>,

  join: (groupId: number | string, token: string) =>
    api.post(`/groups/${groupId}/join`, { token }) as Promise<GroupDetail>,

  acceptInvite: (token: string) =>
    api.post("/groups/accept-invite", { token }) as Promise<GroupDetail>,

  buyShares: (groupId: number | string, data: BuySharesPayload) =>
    api.post(`/groups/${groupId}/shares`, data) as Promise<GroupShareRecord>,

  listContributions: (groupId: number | string) =>
    api.get(`/groups/${groupId}/contributions`) as Promise<GroupContribution[]>,

  addContribution: (
    groupId: number | string,
    data: AddContributionPayload,
  ) => api.post(`/groups/${groupId}/contributions`, data) as Promise<GroupContribution>,
};