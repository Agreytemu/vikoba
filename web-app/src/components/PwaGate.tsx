import { FC, ReactNode, useState } from "react";
import { usePwaStatus } from "@/hooks/usePwaStatus";
import InstallAppScreen from "@/pages/InstallAppScreen";

const ALLOW_KEY = "vikoba_allow_browser";

/**
 * Enforces the installed PWA on mobile devices.
 *
 * - Desktop: never gated (desktop experience completely unchanged).
 * - Installed PWA (display-mode: standalone): full access (native mobile UI).
 * - Phone/tablet web browser: the app UI is locked behind the install screen
 *   until the PWA is installed (or the user opts into the browser once).
 */
const PwaGate: FC<{ children: ReactNode }> = ({ children }) => {
  const { standalone, mobileBrowser } = usePwaStatus();
  const [allowBrowser, setAllowBrowser] = useState<boolean>(() => {
    try {
      return localStorage.getItem(ALLOW_KEY) === "1";
    } catch {
      return false;
    }
  });

  if (!mobileBrowser || standalone || allowBrowser) return <>{children}</>;

  return (
    <InstallAppScreen
      onContinueInBrowser={() => {
        try {
          localStorage.setItem(ALLOW_KEY, "1");
        } catch {
          /* storage unavailable — fall back to in-memory override */
        }
        setAllowBrowser(true);
      }}
    />
  );
};

export default PwaGate;