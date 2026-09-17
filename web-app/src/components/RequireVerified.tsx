import { FC, ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useGetMyMemberProfile } from "@/hooks/api/memberSelf";
import Spinner from "@/components/Spinner";

interface RequireVerifiedProps {
  children?: ReactNode;
}

/**
 * Gate for member-only routes.
 * - If member is not verified, redirect to /profile (verification workflow).
 * - If member is verified but not onboarded, redirect to /onboarding.
 * - Staff / non-ME users without a member profile are allowed through.
 * - While loading, show a spinner to avoid flicker.
 */
const RequireVerified: FC<RequireVerifiedProps> = ({ children }) => {
  const location = useLocation();
  const { data: profile, isLoading, isError } = useGetMyMemberProfile();

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner />
      </div>
    );
  }

  // If there is no member profile (staff, or error like 400 "No member profile linked")
  // we should not block - allow through. Check error detail.
  const hasNoProfile = isError || !profile;
  if (hasNoProfile) {
    // Inspect error to ensure it's "No member profile linked" case
    // For staff users, profile is absent; allow.
    // We treat any error as no-profile and allow, to avoid locking staff.
    if (children) return <>{children}</>;
    return <Outlet />;
  }

  // At this point profile exists and is a member (ME)
  const isVerified = Boolean(profile.is_verified);
  const isOnboarded = Boolean(profile.is_onboarded);

  if (!isVerified) {
    return <Navigate to="/profile" state={{ from: location.pathname }} replace />;
  }

  if (isVerified && !isOnboarded) {
    // Avoid redirect loop if already on onboarding page (should not happen because onboarding is outside gate)
    if (location.pathname === "/onboarding") {
      if (children) return <>{children}</>;
      return <Outlet />;
    }
    return <Navigate to="/onboarding" state={{ from: location.pathname }} replace />;
  }

  if (children) return <>{children}</>;
  return <Outlet />;
};

export default RequireVerified;
