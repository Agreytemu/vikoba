// Location-based currency detection & formatting.
//
// Tanzania-first product: the member's onboarding currency choice (TZS/USD)
// wins whenever it is known; detection below only fills the gap for guests.
// Detection order, from most accurate to most convenient:
//   1. Browser geolocation (explicit permission prompt on the Dashboard)
//      -> reverse-geocoded to a country via BigDataCloud (free, no API key)
//   2. IP-based country lookup (no permission needed) as a fallback
//   3. Browser locale/timezone region as a final offline fallback
//   4. The system's primary currency (TZS) when everything else fails
//
// The whole detection chain is defensive: it can never throw, so the app keeps
// working even on offline/geoblocked/denied setups.

export const DEFAULT_CURRENCY = "TZS";

export type CurrencySource = "manual" | "geo" | "ip" | "locale" | "default" | "profile";

export interface CurrencyState {
  currency: string;
  countryCode: string;
  countryName: string;
  source: CurrencySource;
}

export interface CurrencyChoice {
  code: string;
  label: string;
  country: string;
}

/** ISO alpha-2 country code -> ISO 4217 currency code. */
export const countryCurrencyMap: Record<string, string> = {
  // East Africa & Horn
  KE: "KES", TZ: "TZS", UG: "UGX", RW: "RWF", BI: "BIF", ET: "ETB",
  SO: "SOS", SS: "SSP", DJ: "DJF", ER: "ERN", KM: "KMF",
  // Central Africa (CFA franc, Atlantic/Central)
  CD: "CDF", CG: "XAF", CM: "XAF", GA: "XAF", GQ: "XAF", CF: "XAF", TD: "XAF",
  // West Africa (CFA franc, West)
  SN: "XOF", CI: "XOF", ML: "XOF", BF: "XOF", NE: "XOF", TG: "XOF",
  BJ: "XOF", GW: "XOF", GN: "GNF",
  // West & Central Africa
  NG: "NGN", GH: "GHS", LR: "LRD", SL: "SLE", GM: "GMD",
  // Southern Africa
  ZA: "ZAR", NA: "NAD", BW: "BWP", ZM: "ZMW", MW: "MWK", MZ: "MZN",
  ZW: "ZWL", SZ: "SZL", LS: "LSL", MU: "MUR", MG: "MGA", SC: "SCR", AO: "AOA",
  // North Africa
  EG: "EGP", MA: "MAD", DZ: "DZD", TN: "TND", LY: "LYD", SD: "SDG", MR: "MRU",
  // Major international currencies
  US: "USD", GB: "GBP", CA: "CAD", AU: "AUD", NZ: "NZD", CH: "CHF", SE: "SEK",
  NO: "NOK", DK: "DKK", JP: "JPY", CN: "CNY", IN: "INR", SA: "SAR", AE: "AED",
  RU: "RUB", BR: "BRL", MX: "MXN", TR: "TRY",
  // Eurozone
  DE: "EUR", FR: "EUR", IT: "EUR", ES: "EUR", PT: "EUR", NL: "EUR", BE: "EUR",
  AT: "EUR", IE: "EUR", FI: "EUR", GR: "EUR", LU: "EUR", SI: "EUR", LT: "EUR",
  LV: "EUR", SK: "EUR", EE: "EUR", MT: "EUR", CY: "EUR", HR: "EUR",
};

/** Currencies offered in the manual picker (curated, human-friendly list). */
export const currencyOptions: CurrencyChoice[] = [
  { code: "KES", label: "Kenyan Shilling", country: "Kenya" },
  { code: "TZS", label: "Tanzanian Shilling", country: "Tanzania" },
  { code: "UGX", label: "Ugandan Shilling", country: "Uganda" },
  { code: "RWF", label: "Rwandan Franc", country: "Rwanda" },
  { code: "BIF", label: "Burundian Franc", country: "Burundi" },
  { code: "ETB", label: "Ethiopian Birr", country: "Ethiopia" },
  { code: "SOS", label: "Somali Shilling", country: "Somalia" },
  { code: "SSP", label: "South Sudanese Pound", country: "South Sudan" },
  { code: "CDF", label: "Congolese Franc", country: "DR Congo" },
  { code: "NGN", label: "Nigerian Naira", country: "Nigeria" },
  { code: "GHS", label: "Ghanaian Cedi", country: "Ghana" },
  { code: "ZAR", label: "South African Rand", country: "South Africa" },
  { code: "MWK", label: "Malawian Kwacha", country: "Malawi" },
  { code: "ZMW", label: "Zambian Kwacha", country: "Zambia" },
  { code: "MZN", label: "Mozambican Metical", country: "Mozambique" },
  { code: "EGP", label: "Egyptian Pound", country: "Egypt" },
  { code: "USD", label: "US Dollar", country: "United States" },
  { code: "GBP", label: "British Pound", country: "United Kingdom" },
  { code: "EUR", label: "Euro", country: "European Union" },
];

export const findCurrencyChoice = (code: string): CurrencyChoice | undefined =>
  currencyOptions.find((option) => option.code === code);

/** Returns a clean ISO alpha-2 country code from the browser locale/timezone. */
function countryFromLocale(): string | undefined {
  const language =
    typeof navigator !== "undefined" ? navigator.language || "" : "";
  const region = language.split(/[-_]/)[1];
  if (region && region.length === 2) return region.toUpperCase();

  const timezoneCountryMap: Record<string, string> = {
    "Africa/Nairobi": "KE", "Africa/Dar_es_Salaam": "TZ", "Africa/Kampala": "UG",
    "Africa/Kigali": "RW", "Africa/Bujumbura": "BI", "Africa/Addis_Ababa": "ET",
    "Africa/Mogadishu": "SO", "Africa/Juba": "SS", "Africa/Lagos": "NG",
    "Africa/Accra": "GH", "Africa/Johannesburg": "ZA", "Africa/Cairo": "EG",
    "Africa/Casablanca": "MA", "Africa/Kinshasa": "CD", "Africa/Luanda": "AO",
    "Europe/London": "GB", "Europe/Paris": "FR", "America/New_York": "US",
    "America/Chicago": "US", "America/Los_Angeles": "US", "Europe/Berlin": "DE",
  };
  return timezoneCountryMap[Intl.DateTimeFormat().resolvedOptions().timeZone || ""];
}

/** Point-in-browser geolocation (may trigger the browser permission prompt). */
function getCurrentPosition(): Promise<{ latitude: number; longitude: number }> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new Error("geolocation unsupported"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) =>
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        }),
      (error) => reject(error),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 15 * 60_000 },
    );
  });
}

async function fetchJson(url: string): Promise<Record<string, unknown> | null> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8_000);
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    if (!response.ok) return null;
    const data = await response.json();
    return data && typeof data === "object" ? (data as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

/** Free reverse-geocoding: lat/lng -> country (BigDataCloud, no API key). */
async function reverseGeocode(
  latitude: number,
  longitude: number,
): Promise<{ countryCode: string; countryName: string } | null> {
  const data = await fetchJson(
    `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${latitude}&longitude=${longitude}&localityLanguage=en`,
  );
  const countryCode = data?.countryCode as string | undefined;
  if (!countryCode) return null;
  return {
    countryCode,
    countryName: cleanCountryName((data?.countryName as string | undefined) || countryCode),
  };
}

/** IP-based country lookup, no permission required. Tries a no-key chain and
 *  never throws — Returns null only when every provider fails. */
async function countryFromIp(): Promise<{ countryCode: string; countryName: string } | null> {
  const candidates = [
    "https://ipinfo.io/json",
    "https://api.bigdatacloud.net/data/client-ip",
  ];
  for (const url of candidates) {
    const data = await fetchJson(url);
    const countryCode = (data?.country as string | undefined) ||
      (data?.countryCode as string | undefined);
    if (!countryCode) continue;
    return {
      countryCode,
      countryName: cleanCountryName(
        (data?.country_name as string | undefined) ||
          (data?.region as string | undefined) ||
          countryCode,
      ),
    };
  }
  return null;
}

/** Clean verbose country names up to short labels. */
function cleanCountryName(name: string): string {
  const map: Record<string, string> = {
    "Tanzania, the United Republic of": "Tanzania",
    "Tanzania, United Republic of": "Tanzania",
    "United Republic of Tanzania": "Tanzania",
    "Congo, The Democratic Republic of the": "DR Congo",
    "Russian Federation": "Russia",
    "Bolivia, Plurinational State of": "Bolivia",
  };
  return map[name] ?? name;
}

function buildState(
  info: { countryCode: string; countryName: string },
  source: CurrencySource,
): CurrencyState {
  return {
    currency: countryCurrencyMap[info.countryCode] ?? "TZS",
    countryCode: info.countryCode,
    countryName: info.countryName,
    source,
  };
}

/**
 * Runs the full detection chain. Never throws — always returns a usable state.
 */
export async function detectCurrency(): Promise<CurrencyState> {
  // 1. Geolocation (permission required) -> country
  try {
    const position = await getCurrentPosition();
    const info = await reverseGeocode(position.latitude, position.longitude);
    if (info) return buildState(info, "geo");
  } catch {
    // permission denied / unsupported / reverse-geocode failure -> fall through
  }

  // 2. IP-based lookup
  const ip = await countryFromIp();
  if (ip) return buildState(ip, "ip");

  // 3. Browser locale/timezone (offline-safe)
  const localeCountry = countryFromLocale();
  if (localeCountry) {
    return buildState(
      { countryCode: localeCountry, countryName: localeCountry },
      "locale",
    );
  }

  // 4. Primary currency
  return { currency: DEFAULT_CURRENCY, countryCode: "", countryName: "", source: "default" };
}

/** Formats a number with the given currency using the passed browser language. */
export function formatCurrency(
  amount: number,
  currency: string,
  language: string,
  options?: { maxFractionDigits?: number },
): string {
  const value = Number(amount || 0);
  const locale = language && language.trim() ? language : navigator?.language || "en";
  const isInteger = Number.isInteger(value);
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: currency || DEFAULT_CURRENCY,
    currencyDisplay: isInteger ? "symbol" : "symbol",
    maximumFractionDigits:
      options?.maxFractionDigits ?? (isInteger ? 0 : 2),
    minimumFractionDigits:
      options?.maxFractionDigits === undefined && isInteger ? 0 : undefined,
  }).format(value);
}