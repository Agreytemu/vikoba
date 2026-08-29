import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import en from "./locales/en.json";
import sw from "./locales/sw.json";
import fr from "./locales/fr.json";
import es from "./locales/es.json";
import pt from "./locales/pt.json";
import de from "./locales/de.json";
import it from "./locales/it.json";
import ar from "./locales/ar.json";
import hi from "./locales/hi.json";
import zh from "./locales/zh.json";

/**
 * English is the default / fallback language. Visitors from specific countries
 * (see `countryLanguageMap`) are shown that country's language by default, but
 * they can always switch manually and we remember the choice.
 */
export const defaultLanguage = "en";

export const supportedLanguages = [
  { code: "en", label: "English" },
  { code: "sw", label: "Kiswahili" },
  { code: "fr", label: "Français" },
  { code: "es", label: "Español" },
  { code: "pt", label: "Português" },
  { code: "de", label: "Deutsch" },
  { code: "it", label: "Italiano" },
  { code: "ar", label: "العربية" },
  { code: "hi", label: "हिन्दी" },
  { code: "zh", label: "中文" },
] as const;

/**
 * Country/region code -> language shown by default for that country.
 * Covers many countries; anything not listed falls back to English.
 * (Zanzibar is part of Tanzania, so TZ also covers Zanzibar.)
 */
export const countryLanguageMap: Record<string, string> = {
  // English-speaking countries
  US: "en", GB: "en", AU: "en", IE: "en", NZ: "en",
  ZA: "en", NG: "en", GH: "en", LR: "en", SL: "en", GM: "en",
  ZM: "en", MW: "en", ZW: "en", NA: "en", BW: "en", SZ: "en", LS: "en",
  GG: "en", JE: "en", IM: "en", KY: "en", BM: "en", VC: "en", VG: "en",
  DM: "en", GD: "en", LC: "en", AG: "en", KN: "en", TT: "en", BS: "en",
  BB: "en", BZ: "en", GU: "en", FM: "en", MH: "en", PW: "en", WS: "en",
  TO: "en", FJ: "en", VU: "en", PG: "en", SB: "en", KI: "en", TV: "en",
  NR: "en", CK: "en", NU: "en",
  // Swahili-speaking countries (East Africa; TZ includes Zanzibar)
  TZ: "sw", KE: "sw", UG: "sw", RW: "sw", BI: "sw",
  // French-speaking countries
  FR: "fr", BE: "fr", CH: "fr", MC: "fr", LU: "fr", CA: "fr",
  SN: "fr", CI: "fr", ML: "fr", BF: "fr", NE: "fr", TG: "fr", BJ: "fr",
  GA: "fr", CG: "fr", CD: "fr", CM: "fr", CF: "fr", TD: "fr", DJ: "fr",
  KM: "fr", MU: "fr", GQ: "fr", RE: "fr", YT: "fr", GF: "fr", PF: "fr",
  NC: "fr", WF: "fr",
  // Spanish-speaking countries
  ES: "es", MX: "es", CO: "es", AR: "es", CL: "es", PE: "es", EC: "es",
  BO: "es", PY: "es", UY: "es", VE: "es", CR: "es", PA: "es", GT: "es",
  HN: "es", SV: "es", NI: "es", DO: "es", CU: "es", PR: "es",
  // Portuguese-speaking countries
  PT: "pt", BR: "pt", AO: "pt", MZ: "pt", CV: "pt", GW: "pt", ST: "pt", TL: "pt",
  // German-speaking countries
  DE: "de", AT: "de", LI: "de",
  // Italian-speaking countries
  IT: "it", SM: "it", VA: "it",
  // Arabic-speaking countries
  SA: "ar", EG: "ar", AE: "ar", MA: "ar", DZ: "ar", TN: "ar", LY: "ar",
  JO: "ar", LB: "ar", SY: "ar", IQ: "ar", KW: "ar", QA: "ar", BH: "ar",
  OM: "ar", YE: "ar", PS: "ar", SD: "ar", MR: "ar",
  // Hindi
  IN: "hi",
  // Chinese
  CN: "zh", TW: "zh", HK: "zh", MO: "zh", SG: "zh",
};

/** Timezone -> country, used when the browser locale does not include a region. */
const timezoneCountryMap: Record<string, string> = {
  "America/New_York": "US",
  "America/Chicago": "US",
  "America/Denver": "US",
  "America/Los_Angeles": "US",
  "America/Argentina/Buenos_Aires": "AR",
  "America/Bogota": "CO",
  "America/Santiago": "CL",
  "America/Lima": "PE",
  "America/Mexico_City": "MX",
  "America/Sao_Paulo": "BR",
  "America/Montevideo": "UY",
  "America/Caracas": "VE",
  "Europe/London": "GB",
  "Europe/Paris": "FR",
  "Europe/Brussels": "BE",
  "Europe/Berlin": "DE",
  "Europe/Zurich": "CH",
  "Europe/Madrid": "ES",
  "Europe/Rome": "IT",
  "Europe/Lisbon": "PT",
  "Europe/Vienna": "AT",
  "Africa/Kinshasa": "CD",
  "Africa/Lagos": "NG",
  "Africa/Nairobi": "KE",
  "Africa/Dar_es_Salaam": "TZ",
  "Africa/Cairo": "EG",
  "Africa/Casablanca": "MA",
  "Africa/Algiers": "DZ",
  "Africa/Johannesburg": "ZA",
  "Asia/Kolkata": "IN",
  "Asia/Shanghai": "CN",
  "Asia/Riyadh": "SA",
  "Asia/Dubai": "AE",
  "Australia/Sydney": "AU",
  "Pacific/Auckland": "NZ",
};

function detectCountry(): string | undefined {
  if (typeof window === "undefined") return undefined;

  const locale =
    window.navigator.language ||
    (window.navigator as unknown as { userLanguage?: string }).userLanguage ||
    "";

  const region = locale.split(/[-_]/)[1];
  if (region && region.length === 2) return region.toUpperCase();

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
  return timezoneCountryMap[timezone];
}

/**
 * Resolves the default language for a visitor:
 * 1. a manual selection they previously made (localStorage)
 * 2. their country's language when we recognise it
 * 3. otherwise English
 */
function resolveDefaultLanguage(): string {
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem("i18nextLng");
    if (stored) return stored;
  }

  const country = detectCountry();
  if (country && countryLanguageMap[country]) {
    return countryLanguageMap[country];
  }
  return defaultLanguage;
}

const countryDetector = new LanguageDetector();
countryDetector.addDetector({
  name: "countryBased",
  lookup() {
    return resolveDefaultLanguage();
  },
});

i18n
  .use(countryDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      sw: { translation: sw },
      fr: { translation: fr },
      es: { translation: es },
      pt: { translation: pt },
      de: { translation: de },
      it: { translation: it },
      ar: { translation: ar },
      hi: { translation: hi },
      zh: { translation: zh },
    },
    fallbackLng: defaultLanguage,
    supportedLngs: supportedLanguages.map((l) => l.code),
    nonExplicitSupportedLngs: true,
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["countryBased", "localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "i18nextLng",
    },
  });

export default i18n;
