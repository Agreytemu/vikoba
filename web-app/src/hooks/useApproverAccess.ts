import { hasModuleAccess } from "@/lib/access-control";
import { useGetMyGroups } from "@/hooks/api/groups";
import { useUserProfileInfo } from "@/hooks/useUserProfile";

/** Committee offices that can approve group financial requests (backend mirror). */
export const COMMITTEE_ROLES = ["CHAIRPERSON", "SECRETARY", "TREASURER"] as const;

export interface ApproverAccess {
  /** Officer roles (AD/MA/OP/FI/AC) OR any active committee membership. */
  canAccessApprovals: boolean;
  isOfficer: boolean;
  isCommitteeMember: boolean;
  isLoading: boolean;
}

/**
 * Authorisation for the approvals workspace, mirroring the backend
 * (`governance.workflow.can_review`): platform officers supersede committee
 * roles; committee members must hold an active office in at least one group.
 */
export const useApproverAccess = (): ApproverAccess => {
  const { profile } = useUserProfileInfo();
  const isMember = profile?.role === "ME";
  const { data: groups, isLoading: groupsLoading } = useGetMyGroups(isMember);

  const isOfficer = Boolean(profile?.role) && hasModuleAccess(profile?.role, "governance");
  const isCommitteeMember = Boolean(
    isMember &&
      groups?.some((group) =>
        COMMITTEE_ROLES.includes((group.my_role ?? "") as (typeof COMMITTEE_ROLES)[number]),
      ),
  );

  return {
    canAccessApprovals: isOfficer || isCommitteeMember,
    isOfficer,
    isCommitteeMember,
    // A member's committee status is async (groups query); officers are sync.
    isLoading: isMember && groupsLoading,
  };
};