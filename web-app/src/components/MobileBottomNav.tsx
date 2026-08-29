import { FC, useMemo, useState } from "react";
import { NavLink, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import LucideIcon from "./LucideIcon";
import BottomSheet from "@/components/ui/BottomSheet";
import {
  bottomNavPrimaryOrder,
  memberBottomNavPrimaryOrder,
  sidebarItems,
  type SidebarItem,
} from "@/lib/navigation";
import { hasModuleAccess } from "@/lib/access-control";
import { useUserProfileInfo } from "@/hooks/useUserProfile";
import { Auth } from "@/contexts/AuthContext";
import { useLogout } from "@/hooks/api/auth";

type BottomTab = SidebarItem | { key: "more"; icon: string; to: string };

/**
 * Native-app-style bottom tab navigation for phones (screens under 768px).
 * Replaces the desktop sidebar entirely on mobile — the sidebar never renders
 * below the md breakpoint. Members see Dashboard / Wallet / Groups / Profile
 * plus a "More" sheet for the rest; staff see the operations tabs.
 */
const MobileBottomNav: FC = () => {
  const { t } = useTranslation();
  const { profile } = useUserProfileInfo();
  const { logout } = Auth();
  const { mutate: endServerSession } = useLogout();
  const [moreOpen, setMoreOpen] = useState(false);

  const { tabs, moreItems } = useMemo(() => {
    const primaryOrder =
      profile?.role === "ME" ? memberBottomNavPrimaryOrder : bottomNavPrimaryOrder;
    const allowed = sidebarItems.filter(
      (item) =>
        (!item.module || hasModuleAccess(profile?.role, item.module)) &&
        // Member-only items (e.g. member loan applications) are hidden for staff.
        !(item.memberOnly && profile?.role !== "ME"),
    );
    const primary = allowed
      .filter((item) => primaryOrder.includes(item.key))
      .slice(0, 4);
    const more = allowed.filter((item) => !primary.some((p) => p.key === item.key));
    const tabs: BottomTab[] =
      more.length > 0
        ? [...primary, { key: "more", icon: "Ellipsis", to: "#" }]
        : primary;
    return { tabs, moreItems: more };
  }, [profile?.role]);

  const handleLogout = () => {
    setMoreOpen(false);
    // Local logout is the source of truth and must happen immediately. Ending
    // the server session afterwards is best-effort so a network failure can
    // never leave the user signed in on this device.
    logout();
    endServerSession();
  };

  return (
    <>
      <nav className="safe-bottom fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 shadow-[0_-4px_16px_rgba(0,0,0,0.06)] backdrop-blur md:hidden dark:border-slate-800 dark:bg-slate-950/95">
        <div className="grid h-16" style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }}>
          {tabs.map((item) =>
            item.key === "more" ? (
              <button
                key="more"
                type="button"
                onClick={() => setMoreOpen(true)}
                className="flex min-h-0 flex-col items-center justify-center gap-1 text-slate-600 dark:text-slate-300"
              >
                <span className="rounded-full p-1.5">
                  <LucideIcon name="Ellipsis" size={24} />
                </span>
                <span className="text-[10px] font-medium">{t("nav.more")}</span>
              </button>
            ) : (
              <NavLink
                key={item.key}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `flex min-h-0 flex-col items-center justify-center gap-1 transition ${
                    isActive
                      ? "text-blue-700 dark:text-blue-300"
                      : "text-slate-600 dark:text-slate-300"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={`rounded-full p-1.5 transition ${
                        isActive ? "bg-blue-100 dark:bg-blue-950/50" : ""
                      }`}
                    >
                      <LucideIcon name={item.icon} size={24} />
                    </span>
                    <span className="text-[10px] font-medium">{t(`nav.${item.key}`)}</span>
                  </>
                )}
              </NavLink>
            ),
          )}
        </div>
      </nav>

      {/* "More" bottom sheet */}
      <BottomSheet isOpen={moreOpen} onClose={() => setMoreOpen(false)} title={t("nav.more")}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {moreItems.map((item) => (
            <Link
              key={item.key}
              to={item.to}
              onClick={() => setMoreOpen(false)}
              className="flex flex-col items-center gap-2 rounded-2xl border border-slate-200 p-4 text-center transition hover:border-blue-300 hover:bg-blue-50/50 dark:border-slate-800 dark:hover:bg-blue-950/20"
            >
              <LucideIcon name={item.icon} size={22} />
              <span className="text-xs font-medium">{t(`nav.${item.key}`)}</span>
            </Link>
          ))}
          <button
            type="button"
            onClick={handleLogout}
            className="flex flex-col items-center gap-2 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700 transition hover:bg-red-100 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300 dark:hover:bg-red-950/70"
          >
            <LucideIcon name="LogOut" size={22} />
            <span className="text-xs font-medium">{t("nav.logout")}</span>
          </button>
        </div>
      </BottomSheet>
    </>
  );
};

export default MobileBottomNav;