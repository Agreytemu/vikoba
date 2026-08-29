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
  // Africa
  ["Tanzania", "TZ", "255"],
  ["Kenya", "KE", "254"],
  ["Uganda", "UG", "256"],
  ["Rwanda", "RW", "250"],
  ["Burundi", "BI", "257"],
  ["South Sudan", "SS", "211"],
  ["Ethiopia", "ET", "251"],
  ["Eritrea", "ER", "291"],
  ["Djibouti", "DJ", "253"],
  ["Somalia", "SO", "252"],
  ["Sudan", "SD", "249"],
  ["Egypt", "EG", "20"],
  ["Libya", "LY", "218"],
  ["Tunisia", "TN", "216"],
  ["Algeria", "DZ", "213"],
  ["Morocco", "MA", "212"],
  ["Mauritania", "MR", "222"],
  ["Senegal", "SN", "221"],
  ["Mali", "ML", "223"],
  ["Guinea", "GN", "224"],
  ["Côte d’Ivoire", "CI", "225"],
  ["Burkina Faso", "BF", "226"],
  ["Niger", "NE", "227"],
  ["Togo", "TG", "228"],
  ["Benin", "BJ", "229"],
  ["Nigeria", "NG", "234"],
  ["Ghana", "GH", "233"],
  ["Liberia", "LR", "231"],
  ["Sierra Leone", "SL", "232"],
  ["Guinea-Bissau", "GW", "245"],
  ["Gambia", "GM", "220"],
  ["Cameroon", "CM", "237"],
  ["Gabon", "GA", "241"],
  ["Congo", "CG", "242"],
  ["DR Congo", "CD", "243"],
  ["Angola", "AO", "244"],
  ["Zambia", "ZM", "260"],
  ["Zimbabwe", "ZW", "263"],
  ["Botswana", "BW", "267"],
  ["Namibia", "NA", "264"],
  ["South Africa", "ZA", "27"],
  ["Lesotho", "LS", "266"],
  ["Eswatini", "SZ", "268"],
  ["Mozambique", "MZ", "258"],
  ["Malawi", "MW", "265"],
  ["Madagascar", "MG", "261"],
  ["Mauritius", "MU", "230"],
  ["Seychelles", "SC", "248"],
  ["Comoros", "KM", "269"],
  ["Cabo Verde", "CV", "238"],
  ["São Tomé and Príncipe", "ST", "239"],
  ["Equatorial Guinea", "GQ", "240"],
  ["Chad", "TD", "235"],
  ["Central African Republic", "CF", "236"],

  // Europe
  ["United Kingdom", "GB", "44"],
  ["Ireland", "IE", "353"],
  ["France", "FR", "33"],
  ["Germany", "DE", "49"],
  ["Spain", "ES", "34"],
  ["Portugal", "PT", "351"],
  ["Italy", "IT", "39"],
  ["Netherlands", "NL", "31"],
  ["Belgium", "BE", "32"],
  ["Switzerland", "CH", "41"],
  ["Austria", "AT", "43"],
  ["Sweden", "SE", "46"],
  ["Norway", "NO", "47"],
  ["Denmark", "DK", "45"],
  ["Finland", "FI", "358"],
  ["Poland", "PL", "48"],
  ["Czechia", "CZ", "420"],
  ["Slovakia", "SK", "421"],
  ["Hungary", "HU", "36"],
  ["Romania", "RO", "40"],
  ["Bulgaria", "BG", "359"],
  ["Greece", "GR", "30"],
  ["Cyprus", "CY", "357"],
  ["Malta", "MT", "356"],
  ["Croatia", "HR", "385"],
  ["Slovenia", "SI", "386"],
  ["Serbia", "RS", "381"],
  ["Bosnia and Herzegovina", "BA", "387"],
  ["Albania", "AL", "355"],
  ["North Macedonia", "MK", "389"],
  ["Lithuania", "LT", "370"],
  ["Latvia", "LV", "371"],
  ["Estonia", "EE", "372"],
  ["Iceland", "IS", "354"],
  ["Luxembourg", "LU", "352"],
  ["Montenegro", "ME", "382"],
  ["Ukraine", "UA", "380"],
  ["Belarus", "BY", "375"],
  ["Russia", "RU", "7"],
  ["Moldova", "MD", "373"],
  ["Turkey", "TR", "90"],
  ["Georgia", "GE", "995"],
  ["Armenia", "AM", "374"],
  ["Azerbaijan", "AZ", "994"],
  ["Kazakhstan", "KZ", "7"],
  ["Uzbekistan", "UZ", "998"],

  // Asia
  ["India", "IN", "91"],
  ["Pakistan", "PK", "92"],
  ["Bangladesh", "BD", "880"],
  ["Sri Lanka", "LK", "94"],
  ["Nepal", "NP", "977"],
  ["Bhutan", "BT", "975"],
  ["Maldives", "MV", "960"],
  ["China", "CN", "86"],
  ["Hong Kong", "HK", "852"],
  ["Taiwan", "TW", "886"],
  ["Macau", "MO", "853"],
  ["Japan", "JP", "81"],
  ["South Korea", "KR", "82"],
  ["Mongolia", "MN", "976"],
  ["Thailand", "TH", "66"],
  ["Vietnam", "VN", "84"],
  ["Cambodia", "KH", "855"],
  ["Laos", "LA", "856"],
  ["Myanmar", "MM", "95"],
  ["Malaysia", "MY", "60"],
  ["Singapore", "SG", "65"],
  ["Indonesia", "ID", "62"],
  ["Philippines", "PH", "63"],
  ["Brunei", "BN", "673"],
  ["Timor-Leste", "TL", "670"],

  // Middle East
  ["Saudi Arabia", "SA", "966"],
  ["United Arab Emirates", "AE", "971"],
  ["Qatar", "QA", "974"],
  ["Kuwait", "KW", "965"],
  ["Bahrain", "BH", "973"],
  ["Oman", "OM", "968"],
  ["Iraq", "IQ", "964"],
  ["Iran", "IR", "98"],
  ["Israel", "IL", "972"],
  ["Jordan", "JO", "962"],
  ["Lebanon", "LB", "961"],
  ["Syria", "SY", "963"],
  ["Yemen", "YE", "967"],
  ["Palestine", "PS", "970"],

  // Americas
  ["United States", "US", "1"],
  ["Canada", "CA", "1"],
  ["Mexico", "MX", "52"],
  ["Brazil", "BR", "55"],
  ["Argentina", "AR", "54"],
  ["Chile", "CL", "56"],
  ["Colombia", "CO", "57"],
  ["Peru", "PE", "51"],
  ["Ecuador", "EC", "593"],
  ["Bolivia", "BO", "591"],
  ["Paraguay", "PY", "595"],
  ["Uruguay", "UY", "598"],
  ["Venezuela", "VE", "58"],
  ["Guyana", "GY", "592"],
  ["Suriname", "SR", "597"],
  ["Panama", "PA", "507"],
  ["Costa Rica", "CR", "506"],
  ["Nicaragua", "NI", "505"],
  ["Honduras", "HN", "504"],
  ["El Salvador", "SV", "503"],
  ["Guatemala", "GT", "502"],
  ["Belize", "BZ", "501"],
  ["Cuba", "CU", "53"],
  ["Dominican Republic", "DO", "1809"],
  ["Haiti", "HT", "509"],
  ["Jamaica", "JM", "1876"],
  ["Trinidad and Tobago", "TT", "1868"],
  ["Bahamas", "BS", "1242"],
  ["Barbados", "BB", "1246"],

  // Oceania
  ["Australia", "AU", "61"],
  ["New Zealand", "NZ", "64"],
  ["Fiji", "FJ", "679"],
  ["Papua New Guinea", "PG", "675"],
  ["Solomon Islands", "SB", "677"],
  ["Vanuatu", "VU", "678"],
  ["Samoa", "WS", "685"],
  ["Tonga", "TO", "676"],
];

/** Turn an ISO 3166-1 alpha-2 code into its flag emoji (regional indicators). */
export function flagEmoji(iso2: string): string {
  return iso2
    .toUpperCase()
    .replace(/./g, (c) => String.fromCodePoint(127397 + c.charCodeAt(0)));
}

/**
 * Best-effort guess of the user's country from the browser locale, so the
 * phone input can default to the right dial code ("from their location").
 */
export function detectCountry(): Country {
  const region =
    (typeof navigator !== "undefined" &&
      (navigator.language || "").split("-")[1]) ||
    "";
  const match = COUNTRIES.find((c) => c[1].toUpperCase() === region.toUpperCase());
  return (match ? { name: match[0], iso2: match[1], dial: match[2] } : COUNTRIES[0]) as Country;
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
