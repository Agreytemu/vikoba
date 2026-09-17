import { FC, ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useGetMyMemberProfile } from "@/hooks/api/memberSelf";
import Spinner from "@/components/Spinner";

interface RequireVerifiedProps {
  children?: ReactNode;
}

/**
 * Gate for member-only routes.
 * - Members who have not finished the onboarding wizard (which includes phone
 *   verification, KYC and plan selection) are sent to the standalone /onboarding
 *   page. There is no dashboard or portal until onboarding is complete.
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
    if (children) return <>{children}</>;
    return <Outlet />;
  }

  // At this point profile exists and is a member (ME)
  const isOnboarded = Boolean(profile.is_onboarded);

  if (!isOnboarded) {
    return <Navigate to="/onboarding" state={{ from: location.pathname }} replace />;
  }

  if (children) return <>{children}</>;
  return <Outlet />;
};

export default RequireVerified;