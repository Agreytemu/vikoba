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
  is_verified?: boolean;
  member_status?: string;
  contribution_total?: string;
  pending_contribution_total?: string;
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

export interface PaginatedResponse<T> {
  count: number;
  page: number;
  page_size: number;
  results: T[];
}

export interface GroupWorkspaceOverview {
  group: {
    id: number;
    code: string;
    name: string;
    area: string;
    region: string;
    country: string;
    description: string;
    status: string;
    member_count: number;
    my_role: string;
    total_shares: number;
    created_at: string;
  };
  permissions: {
    can_manage: boolean;
    can_invite: boolean;
    can_view_financials: boolean;
  };
  contribution_summary: {
    total_amount: string;
    total_count: number;
    confirmed_amount: string;
    confirmed_count: number;
    pending_amount: string;
    pending_count: number;
  };
  loan_summary: {
    loan_count: number;
    active_count: number;
    outstanding_total: string;
    next_due_count: number;
  };
  recent_ledger: GroupLedgerEntry[];
  recent_activity: GroupActivity[];
  pending_items: {
    pending_contributions: number;
    pending_invitations: number;
  };
}

export interface GroupLoanProjection {
  loan_number: string;
  borrower: MemberBrief;
  product: string;
  principal_amount: string;
  outstanding_amount: string;
  status: string;
  next_repayment_amount: string | null;
  next_due_date: string | null;
  repayment_status: string;
}

export interface GroupRepaymentProjection {
  id: number;
  borrower: MemberBrief;
  loan_reference: string;
  amount: string;
  date: string;
  status: string;
  transaction_reference: string;
  description: string;
}

export interface GroupLedgerEntry {
  id: string;
  date: string;
  transaction_type: string;
  member: MemberBrief | null;
  amount: string;
  status: string;
  reference: string;
  internal_reference: string;
  provider_reference: string | null;
  related_contribution: number | null;
  related_loan: string;
  description: string;
}

export interface GroupActivity {
  id: number;
  event_type: string;
  event_type_display: string;
  title: string;
  description: string;
  actor: MemberBrief | null;
  metadata: Record<string, unknown>;
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

export interface GroupListParams {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  role?: string;
  type?: string;
  event_type?: string;
  month?: string;
  date_from?: string;
  date_to?: string;
}

const withParams = (params?: GroupListParams) => ({
  params: Object.fromEntries(
    Object.entries(params ?? {}).filter(([, value]) => value !== undefined && value !== ""),
  ),
});

export const groupsService = {
  listMyGroups: () =>
    api.get("/groups") as Promise<GroupSummary[]>,

  mySummary: () =>
    api.get("/groups/me/summary") as Promise<GroupSummaryStats>,

  getGroup: (groupId: number | string) =>
    api.get(`/groups/${groupId}`) as Promise<GroupDetail>,

  overview: (groupId: number | string) =>
    api.get(`/groups/${groupId}/overview`) as Promise<GroupWorkspaceOverview>,

  members: (groupId: number | string, params?: GroupListParams) =>
    api.get(`/groups/${groupId}/members`, withParams(params)) as Promise<PaginatedResponse<GroupMembershipInfo>>,

  loans: (groupId: number | string, params?: GroupListParams) =>
    api.get(`/groups/${groupId}/loans`, withParams(params)) as Promise<PaginatedResponse<GroupLoanProjection>>,

  repayments: (groupId: number | string, params?: GroupListParams) =>
    api.get(`/groups/${groupId}/repayments`, withParams(params)) as Promise<PaginatedResponse<GroupRepaymentProjection>>,

  ledger: (groupId: number | string, params?: GroupListParams) =>
    api.get(`/groups/${groupId}/ledger`, withParams(params)) as Promise<PaginatedResponse<GroupLedgerEntry>>,

  activity: (groupId: number | string, params?: GroupListParams) =>
    api.get(`/groups/${groupId}/activity`, withParams(params)) as Promise<PaginatedResponse<GroupActivity>>,

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
    api.get(`/groups/${groupId}/contributions`) as Promise<PaginatedResponse<GroupContribution>>,

  listContributionsFiltered: (groupId: number | string, params?: GroupListParams) =>
    api.get(`/groups/${groupId}/contributions`, withParams(params)) as Promise<PaginatedResponse<GroupContribution>>,

  addContribution: (
    groupId: number | string,
    data: AddContributionPayload,
  ) => api.post(`/groups/${groupId}/contributions`, data) as Promise<GroupContribution>,
};
