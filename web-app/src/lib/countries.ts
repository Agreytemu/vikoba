/**
 * All dialing country codes, used by the phone input across the system.
 * Each entry is [country name, ISO 3166-1 alpha-2, dial code (no +)].
 * The flag emoji is derived from the ISO code at runtime (see flagEmoji),
 * so only the code + dial number are stored here — no emoji tables to drift.
 */
export type Country = {
  name: string;
  iso2: string;
  dial: string;
};

export const COUNTRIES: [string, string, string][] = [
  ["Tanzania", "TZ", "255"],
];

/** Turn an ISO 3166-1 alpha-2 code into its flag emoji (regional indicators). */
export function flagEmoji(iso2: string): string {
  return iso2
    .toUpperCase()
    .replace(/./g, (c) => String.fromCodePoint(127397 + c.charCodeAt(0)));
}

/**
 * Tanzania-only deployment: always return Tanzania regardless of locale.
 */
export function detectCountry(): Country {
  const tz = COUNTRIES[0];
  return { name: tz[0], iso2: tz[1], dial: tz[2] } as Country;
}

/** Parse a full number like "+254712345678" into { dial, national }. */
export function splitPhone(value: string): { dial: string; national: string } {
  const cleaned = value.trim();
  const m = cleaned.match(/^\+?(\d+)([\d\s-]+)$/);
  if (!m) return { dial: "", national: cleaned.replace(/\D/g, "") };
  const digits = (m[1] + m[2].replace(/\D/g, "")).replace(/^0+/, "");
  // Find the longest matching known dial code that is a prefix of the digits.
  const possible = COUNTRIES.map((c) => c[2]).filter((d) => digits.startsWith(d));
  possible.sort((a, b) => b.length - a.length);
  const dial = possible[0] || "";
  return { dial, national: dial ? digits.slice(dial.length) : digits };
}
