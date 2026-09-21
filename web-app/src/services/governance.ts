import api from "@/lib/api";

// Governance & approval engine (Phase 4). The officer/committee inbox, request
// detail + decisions, the audit trail, and per-group withdrawal policies.

export type ApprovalStatus =
  | "PENDING"
  | "APPROVED"
  | "AUTO_APPROVED"
  | "PROCESSING"
  | "COMPLETED"
  | "REJECTED"
  | "CANCELLED"
  | "EXPIRED"
  | "FAILED";

export type ApprovalDecision = "AUTO_APPROVED" | "MANUAL_REVIEW" | "REJECTED" | null;

export type ApprovalActionName =
  | "submit"
  | "auto_approve"
  | "review_required"
  | "approve"
  | "reject"
  | "cancel"
  | "expire"
  | "mark_processing"
  | "complete"
  | "fail"
  | "policy_changed";

export interface ApprovalStep {
  level: number;
  role: string;
  status: string;
  approved_by: number | null;
  approved_by_name: string | null;
  approved_at: string | null;
  reason: string;
}

export interface ApprovalAction {
  action: ApprovalActionName | string;
  actor_type: "SYSTEM" | "HUMAN";
  actor_name: string;
  decision: ApprovalDecision;
  reason: string;
  from_status: string;
  to_status: string;
  ip_address: string | null;
  created_at: string;
}

export interface WithdrawalContext {
  reference: string;
  member_name: string;
  account_number: string;
  balance: string;
  status: string;
  decline_reason: string;
  requested_at: string;
  network: string;
}

export interface ApprovalRequest {
  id: number;
  request_type: string;
  resource_description: string;
  requester_id: number | null;
  requester_name: string;
  group: number | null;
  group_name: string | null;
  amount: string;
  currency: string;
  required_level: string;
  required_role: string;
  status: ApprovalStatus;
  status_label: string;
  decision: ApprovalDecision;
  decision_label?: string;
  decision_reason: string;
  rules_passed: string[];
  policy_version: string;
  steps: ApprovalStep[];
  metadata: Record<string, unknown>;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
  withdrawal: WithdrawalContext | null;
  can_act: boolean;
  can_cancel: boolean;
  is_requester: boolean;
}

export interface ApprovalFilters {
  status?: string;
  type?: string;
  group?: number | string;
}

export interface ApprovalActionPayload {
  action: "approve" | "reject" | "cancel";
  reason?: string;
}

export interface EffectivePolicy {
  auto_approve_limit: string;
  max_withdrawal_limit: string;
  min_withdrawal_amount: string;
  min_retained_ratio: string;
  review_levels: string;
  reviewer_role: string;
  policy_version: string;
}

export interface GroupWithdrawalPolicy {
  group: number;
  auto_approve_limit: string | null;
  max_withdrawal_limit: string | null;
  min_withdrawal_amount: string | null;
  weekly_withdrawal_limit: string | null;
  weekly_withdrawal_count: number | null;
  monthly_withdrawal_limit: string | null;
  min_retained_ratio: string | null;
  review_on_outstanding_loan: boolean;
  review_on_outstanding_penalty: boolean;
  review_levels: string;
  reviewer_role: string;
  updated_by: number | null;
  updated_at: string | null;
  effective: EffectivePolicy;
}

export interface GroupWithdrawalPolicyPayload {
  auto_approve_limit?: string | null;
  max_withdrawal_limit?: string | null;
  min_withdrawal_amount?: string | null;
  weekly_withdrawal_limit?: string | null;
  weekly_withdrawal_count?: number | null;
  monthly_withdrawal_limit?: string | null;
  min_retained_ratio?: string | null;
  review_on_outstanding_loan?: boolean;
  review_on_outstanding_penalty?: boolean;
  review_levels?: string;
  reviewer_role?: string;
}

const withApprovalFilters = (filters?: ApprovalFilters) =>
  Object.fromEntries(
    Object.entries(filters ?? {}).filter(([, value]) => value !== undefined && value !== ""),
  );

export const governanceService = {
  listApprovals: (filters?: ApprovalFilters) =>
    api.get("/governance/approvals/", {
      params: withApprovalFilters(filters),
    }) as Promise<ApprovalRequest[]>,

  getApproval: (approvalId: number | string) =>
    api.get(`/governance/approvals/${approvalId}/`) as Promise<ApprovalRequest>,

  actOnApproval: (approvalId: number | string, data: ApprovalActionPayload) =>
    api.post(`/governance/approvals/${approvalId}/action/`, data) as Promise<ApprovalRequest>,

  approvalHistory: (approvalId: number | string) =>
    api.get(`/governance/approvals/${approvalId}/history/`) as Promise<ApprovalAction[]>,

  getGroupWithdrawalPolicy: (groupId: number | string) =>
    api.get(`/governance/groups/${groupId}/withdrawal-policy/`) as Promise<GroupWithdrawalPolicy>,

  updateGroupWithdrawalPolicy: (groupId: number | string, data: GroupWithdrawalPolicyPayload) =>
    api.put(`/governance/groups/${groupId}/withdrawal-policy/`, data) as Promise<GroupWithdrawalPolicy>,
};