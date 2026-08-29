export type PermissionKind = "camera" | "location" | "storage";

export type PermissionState = "granted" | "denied" | "prompt" | "unsupported";

export interface GeoResult {
  granted: boolean;
  coords?: { latitude: number; longitude: number; accuracy: number };
  message?: string;
}

/**
 * Read-only check of a browser permission. Works on modern Chromium/Firefox.
 * Safari does not support navigator.permissions for camera/geolocation.
 */
export function getPermissionState(kind: PermissionKind): Promise<PermissionState> {
  const name =
    kind === "camera"
      ? ("camera" as PermissionName)
      : kind === "location"
        ? ("geolocation" as PermissionName)
        : ("persistent-storage" as PermissionName);
  if (typeof navigator.permissions?.query !== "function") {
    return Promise.resolve("unsupported");
  }
  return navigator.permissions
    .query({ name })
    .then((status) => (status.state as PermissionState) ?? "prompt")
    .catch(() => "prompt");
}

/**
 * Requests camera access with a real getUserMedia call and releases the stream
 * immediately after. Resolves true only when the user grants access.
 */
export function requestCameraPermission(): Promise<boolean> {
  if (!navigator.mediaDevices?.getUserMedia) {
    return Promise.resolve(false);
  }
  return navigator.mediaDevices
    .getUserMedia({ video: { facingMode: "environment" }, audio: false })
    .then((stream) => {
      stream.getTracks().forEach((track) => track.stop());
      return true;
    })
    .catch(() => false);
}

/**
 * Requests the device location and resolves with coordinates when granted.
 * The browser shows its own system prompt on the first call.
 */
export function requestGeolocation(): Promise<GeoResult> {
  if (!("geolocation" in navigator)) {
    return Promise.resolve({ granted: false, message: "Geolocation is not supported." });
  }
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) =>
        resolve({
          granted: true,
          coords: {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
          },
        }),
      (err) =>
        resolve({
          granted: false,
          message:
            err.code === 1
              ? "Location permission was denied. You can still type the area manually."
              : "Could not determine your location.",
        }),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  });
}

/**
 * Asks the browser to keep this site's storage persistent (the app must be
 * installed as a PWA for the browser to honour it). Resolves the persisted flag.
 */
export async function requestStoragePersistence(): Promise<boolean> {
  if (!navigator.storage?.persist) {
    return false;
  }
  try {
    if (await navigator.storage.persisted()) return true;
    return await navigator.storage.persist();
  } catch {
    return false;
  }
}