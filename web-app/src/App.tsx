import { FC, useEffect } from "react";
import { Outlet } from "react-router-dom";
// components
import NavBar from "./components/NavBar";
import SidebarLinks from "./components/SidebarLinks";
import MobileBottomNav from "./components/MobileBottomNav";

const STORAGE_ASKED_KEY = "vk_storage_persist_asked";

/**
 * App shell.
 * - Desktop / tablet (md and up): fixed top bar + persistent sidebar.
 * - Phones (<768px): pure native-style shell — top app bar + bottom tab bar.
 *   The sidebar never renders on phones; the hamburger menu is gone completely;
 *   navigation lives in the bottom tabs (plus a "More" sheet for the rest).
 */
const App: FC = () => {
  // One-time browser prompt to keep PWA storage persisted.
  useEffect(() => {
    if (localStorage.getItem(STORAGE_ASKED_KEY)) return;
    const timer = setTimeout(async () => {
      try {
        if (navigator.storage?.persist) {
          const ok = window.confirm("Keep data on this device so the app loads faster offline?");
          if (ok) await navigator.storage.persist();
        }
      } catch {}
      localStorage.setItem(STORAGE_ASKED_KEY, "1");
    }, 900);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="h-screen w-full flex flex-col overflow-hidden bg-paper text-ink dark:bg-[#0d1117] dark:text-slate-100">
      <NavBar />
      <div className="mt-16 min-h-0 flex-1 md:grid md:grid-cols-[260px_minmax(0,1fr)] md:gap-0">
        <div className="hidden h-full overflow-y-auto border-r border-slate-200 bg-white/70 p-4 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80 md:block">
          <ul className="flex h-full flex-col list-none p-0 m-0">
            <SidebarLinks />
          </ul>
        </div>

        <main className="h-full min-h-0 overflow-y-auto px-3 py-3 pb-24 sm:px-4 md:pb-6 lg:px-6 xl:px-8">
          <div className="mx-auto w-full max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Phone-only, native-style bottom navigation */}
      <MobileBottomNav />
    </div>
  );
};

export default App;