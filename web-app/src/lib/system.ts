// System name is resolved from the environment so it can be changed per
// deployment without touching code. Falls back to the default brand.
export const SYSTEM_NAME =
  (import.meta.env.VITE_APP_NAME as string | undefined)?.trim() ||
  "Vikoba Kidigitali";

// The present year, detected at runtime so the UI never shows a stale one.
export const CURRENT_YEAR = new Date().getFullYear();

// Single source of truth for the brand logo, served from /public so it is
// used identically as the favicon and across the app UI.
export const LOGO_URL = "/vikoba-kidigitali--logo.png";

export const SYSTEM_TAGLINE =
  (import.meta.env.VITE_APP_TAGLINE as string | undefined)?.trim() ||
  `Savings & credit, rebuilt for the communities of ${CURRENT_YEAR}`;
