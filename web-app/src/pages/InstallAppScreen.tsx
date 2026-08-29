import { FC, useEffect, useState } from "react";
import { Download, ExternalLink, Home, Smartphone } from "lucide-react";
import { CURRENT_YEAR, LOGO_URL, SYSTEM_NAME, SYSTEM_TAGLINE } from "@/lib/system";
import { detectInstalledApp, usePwaStatus } from "@/hooks/usePwaStatus";

interface InstallAppScreenProps {
  /** Persists the browser-override flag and lets the user into the web app. */
  onContinueInBrowser: () => void;
}

/**
 * Shown to phone/tablet browsers when the Vikoba PWA is NOT running standalone.
 * The app UI is deliberately locked behind this screen on mobile so users get
 * the installed, native-like experience. Desktop never sees this.
 *
 * Flow: scan for an installed PWA -> if present offer to open it, otherwise the
 * one-tap install prompt (no step-by-step instructions).
 */
const InstallAppScreen: FC<InstallAppScreenProps> = ({ onContinueInBrowser }) => {
  const { canInstall, installed, promptInstall } = usePwaStatus();
  const [present, setPresent] = useState(() => installed);
  const [unsupported, setUnsupported] = useState(false);
  const [confirmContinue, setConfirmContinue] = useState(false);

  // Scan on mount so an already-installed PWA is recognised immediately.
  useEffect(() => {
    let cancelled = false;
    void detectInstalledApp().then((found) => {
      if (!cancelled) setPresent(found);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // A fresh install (appinstalled / accepted prompt) flips the view too.
  useEffect(() => {
    if (installed) setPresent(true);
  }, [installed]);

  const handleInstall = async () => {
    if (canInstall) {
      promptInstall();
      return;
    }
    // No one-tap prompt available — re-scan in case the app is actually
    // already on the device; otherwise admit we cannot auto-install here.
    const found = await detectInstalledApp();
    if (found) {
      setPresent(true);
    } else {
      setUnsupported(true);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-blue-800 px-5 py-10 text-white [padding-bottom:max(2rem,env(safe-area-inset-bottom))]">
      <div className="flex flex-col items-center text-center">
        <img
          src={LOGO_URL}
          alt={`${SYSTEM_NAME} logo`}
          className="h-16 w-16 rounded-2xl bg-white/10 p-2"
        />
        <h1 className="mt-5 font-display text-3xl font-semibold tracking-tight">
          {SYSTEM_NAME}
        </h1>
        <p className="mt-2 max-w-xs text-sm text-blue-100/90">{SYSTEM_TAGLINE}.</p>

        <div className="mt-8 w-full max-w-sm rounded-3xl bg-white p-6 text-left text-ink shadow-2xl">
          {present ? (
            <>
              <p className="flex items-center gap-2 font-display text-lg font-semibold text-blue-800">
                <Home size={20} /> Vikoba is installed
              </p>
              <p className="mt-2 text-sm text-slate-600">
                Open the Vikoba app from your Home screen — or continue right
                here.
              </p>
              <button
                type="button"
                onClick={() => window.location.assign("/login")}
                className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-800 px-5 py-3 text-sm font-semibold text-white shadow-soft transition hover:bg-blue-900"
              >
                <ExternalLink size={18} /> Open Vikoba
              </button>
            </>
          ) : (
            <>
              <p className="flex items-center gap-2 font-display text-lg font-semibold text-blue-800">
                <Smartphone size={20} /> Get the best experience
              </p>
              <p className="mt-2 text-sm text-slate-600">
                Install {SYSTEM_NAME} on this device — it opens instantly from
                your Home screen and shows amounts in your local currency.
              </p>
              <button
                type="button"
                onClick={() => void handleInstall()}
                className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-800 px-5 py-3 text-sm font-semibold text-white shadow-soft transition hover:bg-blue-900"
              >
                <Download size={18} /> Install the app
              </button>
              {unsupported && (
                <p className="mt-3 text-xs text-slate-500">
                  One-tap install isn’t supported in this browser. You can still
                  continue below.
                </p>
              )}
            </>
          )}

          <div className="mt-6 border-t border-slate-100 pt-4">
            {!confirmContinue ? (
              <button
                type="button"
                onClick={() => setConfirmContinue(true)}
                className="text-sm text-slate-500 underline decoration-slate-300 underline-offset-4 transition hover:text-slate-700"
              >
                Use in the browser instead
              </button>
            ) : (
              <div className="space-y-2">
                <p className="text-xs text-slate-500">
                  The browser version misses the offline shell and Home-screen
                  access. You can still sign in.
                </p>
                <button
                  type="button"
                  onClick={onContinueInBrowser}
                  className="text-sm font-semibold text-blue-700 hover:text-blue-900"
                >
                  Yes, continue in the browser
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmContinue(false)}
                  className="ml-4 text-sm text-slate-400 hover:text-slate-600"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>

        <p className="mt-8 text-xs text-blue-200/80">
          © {CURRENT_YEAR} {SYSTEM_NAME}
        </p>
      </div>
    </div>
  );
};

export default InstallAppScreen;