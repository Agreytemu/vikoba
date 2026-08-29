import { FC, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import LucideIcon from "@/components/LucideIcon";
import { Button } from "@/components/ui/button";
import Spinner from "@/components/Spinner";
import {
  getPermissionState,
  requestCameraPermission,
  requestGeolocation,
  requestStoragePersistence,
  type PermissionKind,
  type GeoResult,
} from "@/lib/permissions";

interface PermissionSheetProps {
  isOpen: boolean;
  kind: PermissionKind;
  onClose: () => void;
  onGranted?: () => void;
  /** Called with coordinates when a location permission is granted. */
  onLocationResult?: (result: GeoResult) => void;
}

const COPY: Record<
  PermissionKind,
  { icon: string; title: string; body: string; allow: string; denied: string }
> = {
  camera: {
    icon: "Camera",
    title: "Allow camera access?",
    body: "Vikoba Kidigitali needs your camera so you can capture your ID, passport photo or signature clearly. Nothing is stored until you upload it.",
    allow: "Allow camera",
    denied: "Camera access was denied. Enable the camera in your browser settings, then retry — or choose Gallery instead.",
  },
  location: {
    icon: "MapPin",
    title: "Allow location access?",
    body: "Vikoba Kidigitali uses your location to fill in the area of your group. Your precise position is never shared.",
    allow: "Allow location",
    denied: "Location access was denied. Enable location in your browser settings, then retry — or just type the area manually.",
  },
  storage: {
    icon: "HardDrive",
    title: "Keep data on this device?",
    body: "Vikoba Kidigitali may store small files on this device so the app loads faster and works offline. Granting keeps your saved files safe from automatic cleanup.",
    allow: "Allow storage",
    denied: "Storage persistence is not available on this browser. The app still works fully — your uploads will simply use normal browser storage.",
  },
};

/**
 * System-style permission prompt shown right where a capability is first
 * needed (camera, location, storage). The real browser/system permission is
 * only requested after the user taps the allow button, so no permissions is
 * ever asked without a clear reason.
 */
const PermissionSheet: FC<PermissionSheetProps> = ({
  isOpen,
  kind,
  onClose,
  onGranted,
  onLocationResult,
}) => {
  const { t } = useTranslation();
  const copy = COPY[kind];
  const [phase, setPhase] = useState<"ask" | "working" | "denied">("ask");
  const [geoMessage, setGeoMessage] = useState<string | null>(null);
  // Remember the coords so the caller can read them on "granted".
  const grantedPayload = useRef<GeoResult | null>(null);

  useEffect(() => {
    if (isOpen) {
      setPhase("ask");
      grantedPayload.current = null;
      getPermissionState(kind).then((state) => {
        if (state === "denied") setPhase("denied");
      });
    }
  }, [isOpen, kind]);

  const handleAllow = () => {
    setPhase("working");
    const run =
      kind === "camera"
        ? requestCameraPermission()
        : kind === "location"
          ? requestGeolocation().then((result) => {
              grantedPayload.current = result;
              return result.granted;
            })
          : requestStoragePersistence();

    run.then((granted) => {
      if (granted) {
        if (kind === "location" && grantedPayload.current) {
          onLocationResult?.(grantedPayload.current);
        }
        onGranted?.();
        onClose();
      } else if (kind === "location" && grantedPayload.current?.message) {
        setGeoMessage(grantedPayload.current.message);
        setPhase("denied");
      } else {
        setPhase("denied");
      }
    });
  };

  const retry = () => {
    grantedPayload.current = null;
    getPermissionState(kind).then((state) => {
      if (state === "granted") {
        onGranted?.();
        onClose();
      } else {
        setPhase("ask");
      }
    });
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div
        role="dialog"
        aria-label={copy.title}
        className="relative z-10 w-full max-w-md rounded-t-3xl bg-white p-6 shadow-2xl sm:rounded-3xl dark:bg-slate-900"
      >
        <div className="mx-auto mb-4 h-1.5 w-10 rounded-full bg-slate-300 dark:bg-slate-700 sm:hidden" />
        <div className="flex items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
            <LucideIcon name={copy.icon} size={24} />
          </span>
          <div className="min-w-0 flex-1">
            {phase === "denied" ? (
              <>
                <h2 className="font-display text-lg font-semibold text-slate-900 dark:text-slate-100">
                  Permission blocked
                </h2>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                  {geoMessage ?? copy.denied}
                </p>
                <div className="mt-4 flex justify-end gap-2">
                  <Button type="button" variant="outline" onClick={onClose}>
                    {t("common.cancel")}
                  </Button>
                  <Button type="button" onClick={retry}>
                    Retry
                  </Button>
                </div>
              </>
            ) : (
              <>
                <h2 className="font-display text-lg font-semibold text-slate-900 dark:text-slate-100">
                  {copy.title}
                </h2>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{copy.body}</p>
                <div className="mt-4 flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={onClose}
                    disabled={phase === "working"}
                  >
                    Not now
                  </Button>
                  <Button type="button" onClick={handleAllow} disabled={phase === "working"}>
                    {phase === "working" ? (
                      <>
                        <Spinner /> Requesting…
                      </>
                    ) : (
                      copy.allow
                    )}
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PermissionSheet;