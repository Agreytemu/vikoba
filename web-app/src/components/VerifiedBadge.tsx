import { FC } from "react";
import LucideIcon from "@/components/LucideIcon";
import { useGetMyMemberProfile } from "@/hooks/api/memberSelf";
import { useUserProfileInfo } from "@/hooks/useUserProfile";

interface VerifiedBadgeProps {
  size?: number;
  className?: string;
  showLabel?: boolean;
}

/**
 * Green, Instagram-style verified badge shown next to a member's name once
 * their identity KYC verification is complete. Hidden for staff accounts.
 */
const VerifiedBadge: FC<VerifiedBadgeProps> = ({ size = 16, className = "", showLabel = false }) => {
  const { profile } = useUserProfileInfo();
  const { data: me } = useGetMyMemberProfile(profile?.role === "ME");

  if (profile?.role !== "ME" || !me?.is_verified) return null;

  return (
    <span
      title="Verified member"
      className={`inline-flex items-center gap-1 text-emerald-500 ${className}`}
    >
      <LucideIcon name="BadgeCheck" size={size} />
      {showLabel && <span className="text-xs font-medium">Verified</span>}
    </span>
  );
};

export default VerifiedBadge;