// Location helpers: reverse-geocoding coordinates into a human-readable place
// (country / region / area) so groups display real names instead of raw lat/lng.

export interface GeoPlace {
  country: string;
  region: string;
  area: string;
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

/** Clean verbose country names returned by geocoders down to short labels. */
function cleanCountryName(name: string): string {
  const map: Record<string, string> = {
    "Tanzania, the United Republic of": "Tanzania",
    "Tanzania, United Republic of": "Tanzania",
    "United Republic of Tanzania": "Tanzania",
    "Congo, The Democratic Republic of the": "DR Congo",
    "Congo, the Democratic Republic of the": "DR Congo",
    "Côte d'Ivoire": "Ivory Coast",
    "Russian Federation": "Russia",
    "South Korea": "South Korea",
    "Korea, Republic of": "South Korea",
    "Korea, Democratic People's Republic of": "North Korea",
    "Syrian Arab Republic": "Syria",
    "Bolivia, Plurinational State of": "Bolivia",
    "Venezuela, Bolivarian Republic of": "Venezuela",
    "United States of America": "United States",
  };
  const trimmed = name.trim();
  return map[trimmed] ?? trimmed;
}

/**
 * IP-based country lookup using a small fallback chain. No keys required and
 * every lookup is defensive — it never throws. Used when the browser denies
 * precise geolocation so groups still get a real country instead of nothing.
 */
export async function countryFromIp(): Promise<GeoPlace> {
  const candidates = [
    "https://ipinfo.io/json",
    "https://api.bigdatacloud.net/data/client-ip",
  ];
  for (const url of candidates) {
    const data = await fetchJson(url);
    const country = cleanCountryName(
      String(data?.country_name ?? data?.country ?? ""),
    );
    const region = String(data?.region ?? data?.principalSubdivision ?? "");
    const area = "";
    if (country) return { country, region, area };
  }
  return { country: "", region: "", area: "" };
}

/** Reverse-geocodes coordinates to { country, region, area } using the free
 *  BigDataCloud client API (no key). Every lookup is defensive and never throws;
 *  on failure a no-key IP lookup still provides the country/region.
 */
export async function reverseGeocodePlace(
  latitude: number,
  longitude: number,
): Promise<GeoPlace> {
  const data = await fetchJson(
    `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${latitude}&longitude=${longitude}&localityLanguage=en`,
  );
  const clean = (value: unknown): string =>
    typeof value === "string" && value.trim() ? value.trim() : "";

  const country = cleanCountryName(clean(data?.countryName));
  const region = normalizeRegion(
    clean(data?.principalSubdivision) ||
      clean(data?.province) ||
      clean(data?.region) ||
      clean(data?.state),
  );
  const area =
    clean(data?.locality) ||
    clean(data?.city) ||
    clean(data?.district) ||
    clean(data?.suburb) ||
    clean(data?.neighbourhood);

  if (country || region || area) {
    return { country, region, area };
  }

  // Reverse-geocode returned nothing usable (e.g. rural Tanzania): fall back to
  // a no-key IP lookup so the group still gets a real country/region.
  const ipFallback = await countryFromIp();
  if (ipFallback.country || ipFallback.region) return ipFallback;

  return {
    country: "",
    region: "",
    area: `(${latitude.toFixed(4)}, ${longitude.toFixed(4)})`,
  };
}

/** Maps a geocoder's free-text subdivision onto the standard Tanzanian region
 *  list so detected regions line up with the wizard's dropdown options. */
function normalizeRegion(raw: string): string {
  if (!raw) return "";
  const TANZANIA_REGIONS: Record<string, string> = {
    "Arusha Region": "Arusha",
    "Dar es Salaam Region": "Dar es Salaam",
    "Dodoma Region": "Dodoma",
    "Geita Region": "Geita",
    "Iringa Region": "Iringa",
    "Kagera Region": "Kagera",
    "Katavi Region": "Katavi",
    "Kigoma Region": "Kigoma",
    "Kilimanjaro Region": "Kilimanjaro",
    "Lindi Region": "Lindi",
    "Manyara Region": "Manyara",
    "Mara Region": "Mara",
    "Mbeya Region": "Mbeya",
    "Morogoro Region": "Morogoro",
    "Mtwara Region": "Mtwara",
    "Mwanza Region": "Mwanza",
    "Njombe Region": "Njombe",
    "Pwani Region": "Pwani",
    "Rukwa Region": "Rukwa",
    "Ruvuma Region": "Ruvuma",
    "Shinyanga Region": "Shinyanga",
    "Simiyu Region": "Simiyu",
    "Singida Region": "Singida",
    "Songwe Region": "Songwe",
    "Tabora Region": "Tabora",
    "Tanga Region": "Tanga",
  };
  const mapped = TANZANIA_REGIONS[raw];
  return mapped ?? raw.replace(/\s+Region$/i, "").trim();
}

/** Joins the parts into one display label, skipping the empty pieces. */
export function formatPlace(place: GeoPlace): string {
  return [place.area, place.region, place.country].filter(Boolean).join(", ");
}