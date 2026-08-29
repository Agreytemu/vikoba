// PWA status helpers: detects whether the app is running as an installed
// Progressive Web App (standalone), a mobile browser, or desktop, and manages
// the install prompt state machine.
import { useCallback, useEffect, useRef, useState } from "react";

export const isStandalone = (): boolean =>
  typeof window !== "undefined" &&
  (window.matchMedia("(display-mode: standalone)").matches ||
    (window.navigator as unknown as { standalone?: boolean }).standalone === true);

/** True on phones/tablets (touch primary pointer) that are NOT standalone. */
export const isMobileBrowser = (): boolean =>
  typeof window !== "undefined" &&
  !isStandalone() &&
  window.matchMedia("(pointer: coarse)").matches;

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

interface RelatedApp {
  platform: string;
  url?: string;
  id?: string;
}

/**
 * Scans the device for an already-installed Vikoba PWA without opening anything.
 *
 * - In the installed PWA itself (standalone) it is trivially "present".
 * - In supported browsers (Chrome/Edge on Android & Windows) it asks the OS via
 *   `getInstalledRelatedApps()`.
 * - Everywhere else (iOS Safari mostly) it returns false — those platforms do
 *   not expose an installed-with check.
 * Never throws.
 */
export async function detectInstalledApp(): Promise<boolean> {
  if (isStandalone()) return true;
  try {
    const navigatorWithApi = navigator as Navigator & {
      getInstalledRelatedApps?: () => Promise<RelatedApp[]>;
    };
    if (typeof navigatorWithApi.getInstalledRelatedApps !== "function") return false;
    const apps = await navigatorWithApi.getInstalledRelatedApps();
    return apps.some(
      (app) =>
        app.platform === "web" &&
        (app.url?.includes("/manifest.webmanifest") ||
          (app.url ?? "").includes(window.location.hostname)),
    );
  } catch {
    return false;
  }
}

export interface PwaStatus {
  /** Running inside the installed PWA (windowed AppWindow / standalone mode). */
  standalone: boolean;
  /** A phone/tablet using the web browser rather than the installed app. */
  mobileBrowser: boolean;
  /** The browser supports (and has queued) an install prompt we can trigger. */
  canInstall: boolean;
  /** The PWA was installed in this session (appinstalled / standalone). */
  installed: boolean;
  /** detectInstalledApp() reports the PWA as already installed. */
  relatedInstalled: boolean;
  /** Triggers the browser install prompt (tap-to-install). */
  promptInstall: (onAccepted?: () => void, onDismissed?: () => void) => void;
}

export function usePwaStatus(): PwaStatus {
  const [standalone] = useState<boolean>(isStandalone);
  const [mobileBrowser] = useState<boolean>(isMobileBrowser);
  const [canInstall, setCanInstall] = useState(false);
  const [installed, setInstalled] = useState<boolean>(() => isStandalone());
  const [relatedInstalled, setRelatedInstalled] = useState(false);
  const deferred = useRef<InstallPromptEvent | null>(null);

  useEffect(() => {
    const onPrompt = (event: Event) => {
      event.preventDefault();
      deferred.current = event as InstallPromptEvent;
      setCanInstall(true);
    };
    const onInstalled = () => {
      deferred.current = null;
      setCanInstall(false);
      setInstalled(true);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  // Best-effort scan on mount (Chrome/Edge Android) — absence is "unknown".
  useEffect(() => {
    let cancelled = false;
    void detectInstalledApp().then((found) => {
      if (!cancelled) setRelatedInstalled(found);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const promptInstall = useCallback(
    (onAccepted?: () => void, onDismissed?: () => void) => {
      const prompt = deferred.current;
      if (!prompt) return;
      void prompt
        .prompt()
        .then(() => prompt.userChoice)
        .then((choice) => {
          deferred.current = null;
          setCanInstall(false);
          if (choice.outcome === "accepted") {
            setInstalled(true);
            onAccepted?.();
          } else {
            onDismissed?.();
          }
        });
    },
    [],
  );

  return {
    standalone,
    mobileBrowser,
    canInstall,
    installed,
    relatedInstalled,
    promptInstall,
  };
}