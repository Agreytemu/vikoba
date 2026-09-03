import { FC, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import ProfilePlaceholder from "@/assets/profile-placeholder.png";
// components
import LucideIcon from "./LucideIcon";
import LanguageSwitcher from "./LanguageSwitcher";
import VerifiedBadge from "./VerifiedBadge";
import { Button } from "@/components/ui/button";
import Modal from "@/components/ui/Modal";
// context and custom hook
import { Theme } from "@/contexts/ThemeContext";
import { Auth } from "@/contexts/AuthContext";
import { useUserProfileInfo } from "@/hooks/useUserProfile";
import { useLogout } from "@/hooks/api/auth";
import { SYSTEM_NAME, LOGO_URL } from "@/lib/system";
import { resolveMediaUrl } from "@/constants";

/**
 * Fixed top app bar. On phones it acts as the native app bar (no hamburger,
 * no sidebar traces); navigation on phones is handled by MobileBottomNav.
 */
const NavBar: FC = () => {
  const [showDropdown, setShowDropdown] = useState(false);
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  // dark mode context consumer
  const { toggleDarkTheme, darkTheme } = Theme();
  const { t } = useTranslation();

  // custom hook for user profile
  const { profile } = useUserProfileInfo();
  const { logout } = Auth();
  const { mutate: endServerSession } = useLogout();

  const rawImage = profile?.profile?.profile_image;
  const profileImage =
    typeof rawImage === "string" && rawImage
      ? resolveMediaUrl(rawImage)
      : ProfilePlaceholder;

  const handleShowDropdown = () => {
    setShowDropdown((value) => !value);
  };

  // close dropdown when user clicks outside the dropdown
  const dropdownRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current?.contains(event.target as Node)
      ) {
        setShowDropdown(false);
      }
    }
    // Bind the event listener
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      // Unbind the event listener on clean up
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const confirmLogout = () => {
    setShowLogoutModal(false);
    setShowDropdown(false);
    // Local logout is the source of truth and must happen immediately. Ending
    // the server session afterwards is best-effort: a network failure there
    // must never leave the user signed in on this device.
    logout();
    endServerSession();
  };

  return (
    <div className="fixed left-0 top-0 z-40 flex h-16 w-full items-center justify-between border-b border-green-800/40 bg-green-800 px-3 text-white shadow-soft dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100">
      <div className="flex items-center gap-x-2">
        <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-10 w-10 shrink-0 rounded-md bg-white/10 p-0.5 sm:h-12 sm:w-12" />
        <span className="hidden font-display text-xl font-semibold tracking-tight sm:inline">
          {SYSTEM_NAME}
        </span>
      </div>

      <div className="flex gap-x-3 items-center sm:gap-x-5">
        <LanguageSwitcher />
        <div className="cursor-pointer" onClick={toggleDarkTheme}>
          {darkTheme ? (
            <LucideIcon name="Sun" size={24} />
          ) : (
            <LucideIcon name="Moon" size={24} />
          )}
        </div>
        <div className="relative">
          <img
            className="h-10 w-10 cursor-pointer rounded-full border-2 border-white/40 bg-white/10 object-cover"
            src={profileImage}
            alt={profile?.username || "Profile"}
            onClick={handleShowDropdown}
          />
          {/* dropdown menu start here */}
          <div
            ref={dropdownRef}
            className={`${
              showDropdown ? "block" : "hidden"
            } absolute right-0 z-20 mt-3 min-w-56 rounded-2xl border border-slate-200 bg-white p-1.5 text-slate-900 shadow-card dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100`}
          >
            <div className="p-4">
              <p className="font-medium flex items-center gap-1.5 flex-wrap">
                {profile?.username}
                {profile?.profile?.role_display && (
                  <small className="ml-2 rounded-md bg-green-700 p-0.5 text-xs text-white dark:bg-slate-700">
                    {profile.profile.role_display}
                  </small>
                )}
                <VerifiedBadge size={15} />
              </p>
              <p className="pb-2 text-sm text-slate-500 dark:text-slate-400">{profile?.email}</p>
              <Link
                to="/profile"
                className="flex rounded-md p-2 hover:bg-slate-100 dark:hover:bg-slate-800"
                onClick={handleShowDropdown}
              >
                {t("common.profile")}
              </Link>
              <div
                className="my-2 flex cursor-pointer items-center gap-x-1 rounded-md p-2 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
                onClick={() => {
                  setShowDropdown(false);
                  setShowLogoutModal(true);
                }}
              >
                <LucideIcon name="LogOut" size={16} /> {t("nav.logout")}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Logout confirmation dialog */}
      <Modal
        isOpen={showLogoutModal}
        onClose={() => setShowLogoutModal(false)}
        title="Log out"
      >
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Are you sure you want to log out{" "}
          <span className="font-semibold">{profile?.email}</span>? You will need
          to sign in again to continue.
        </p>
        <div className="mt-6 flex justify-end gap-x-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => setShowLogoutModal(false)}
          >
            Cancel
          </Button>
          <Button type="button" onClick={confirmLogout}>
            Log out
          </Button>
        </div>
      </Modal>
    </div>
  );
};

export default NavBar;