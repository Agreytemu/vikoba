import { FC } from "react";
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
// components
import LucideIcon from "./LucideIcon";
import { hasModuleAccess } from "@/lib/access-control";
import { sidebarItems } from "@/lib/navigation";
import { useUserProfileInfo } from "@/hooks/useUserProfile";
import { useApproverAccess } from "@/hooks/useApproverAccess";
import { Auth } from "@/contexts/AuthContext";
import { useLogout } from "@/hooks/api/auth";

interface SidebarLinksProps {
  onClick?: () => void;
}

const SidebarLinks: FC<SidebarLinksProps> = ({ onClick }) => {
  const { t } = useTranslation();
  const { profile } = useUserProfileInfo();
  const { logout } = Auth();
  const { mutate: endServerSession } = useLogout();
  const { canAccessApprovals } = useApproverAccess();
  const visibleItems = sidebarItems.filter(
    (item) =>
      (!item.module || hasModuleAccess(profile?.role, item.module)) &&
      // Member-only items (e.g. member loan applications) are hidden for staff.
      !(item.memberOnly && profile?.role !== "ME") &&
      // Officer + committee approvals workspace stays hidden otherwise.
      (!item.requiresApprovalAccess || canAccessApprovals),
  );
  const handleLogout = () => {
    // Local logout is the source of truth and must happen immediately. Ending
    // the server session afterwards is best-effort so a network failure can
    // never leave the user signed in on this device.
    logout();
    endServerSession();
    onClick?.();
  };

  return (
    <>
      {visibleItems.map((item) => (
        <li className="" key={item.key}>
          <NavLink
            to={item.to}
            onClick={onClick}
            className={({ isActive }) =>
              `flex gap-x-3 rounded-xl border px-3 py-2.5 text-sm font-medium transition duration-200 ease-in-out ${
                isActive
                  ? "border-blue-700/20 bg-blue-700 text-white shadow-soft dark:border-blue-400/30 dark:bg-blue-700 dark:text-white"
                  : "border-transparent text-slate-700 hover:bg-slate-200/70 hover:text-slate-950 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-50"
              }`
            }
          >
            <LucideIcon name={item.icon} /> {t(`nav.${item.key}`)}
          </NavLink>
          <div className="my-4 w-full border-t border-slate-200 dark:border-slate-800 max-md:my-3"></div>
        </li>
      ))}
      <li className="mt-auto mb-4 pt-4">
        <button
          type="button"
          onClick={handleLogout}
          className="flex w-full gap-x-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-left text-base text-red-700 transition hover:bg-red-100 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300 dark:hover:bg-red-950/70"
        >
          <LucideIcon name="LogOut" /> {t("nav.logout")}
        </button>
      </li>
    </>
  );
};

export default SidebarLinks;