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

/**
 * Reverse-geocodes coordinates to { country, region, area } using the free
 * BigDataCloud client API (no key). Every lookup is defensive and never throws;
 * on failure the fallback still returns the rounded coordinates as readable text.
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

  const country = clean(data?.countryName);
  const region = clean(data?.principalSubdivision);
  const area = clean(data?.locality) || clean(data?.city) || clean(data?.district);

  if (!country && !region && !area) {
    return {
      country: "",
      region: "",
      area: `(${latitude.toFixed(4)}, ${longitude.toFixed(4)})`,
    };
  }
  return { country, region, area };
}

/** Joins the parts into one display label, skipping the empty pieces. */
export function formatPlace(place: GeoPlace): string {
  return [place.area, place.region, place.country].filter(Boolean).join(", ");
}