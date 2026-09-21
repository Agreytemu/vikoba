// Snippe payment constants shared by the member money flows (Deposit / Withdraw).
//
// Supported networks come from the Snippe API documentation (2026-01-25):
//   Collections   – Mobile Money: Airtel Money, M-Pesa, Mixx by Yas, Halotel.
//                   The customer's phone number determines the operator and the
//                   USSD push is sent to that number.
//   Disbursements – Mobile Money recipients on the same networks (plus banks).
//
// Only TZS is supported by Snippe. Minimums: collections 500 TZS,
// payouts 5,000 TZS. The app NEVER talks to Snippe directly — the Django
// backend initiates the payment and only a verified webhook marks money in/out.

export const SNIPPE_NETWORKS = [
  {
    id: "mpesa",
    name: "M-Pesa",
    operator: "Vodacom",
    icon: "Smartphone",
    brandColor: "#43B02A",
    brandText: "#FFFFFF",
    shortName: "M-PESA",
    tagline: "Vodacom",
  },
  {
    id: "airtel",
    name: "Airtel Money",
    operator: "Airtel",
    icon: "Smartphone",
    brandColor: "#ED1C24",
    brandText: "#FFFFFF",
    shortName: "airtel",
    tagline: "Money",
  },
  {
    id: "mixx",
    name: "Mixx by Yas",
    operator: "Yas",
    icon: "Smartphone",
    brandColor: "#FFC72C",
    brandText: "#111111",
    shortName: "MIXX",
    tagline: "by Yas",
  },
  {
    id: "halotel",
    name: "Halotel",
    operator: "Halotel",
    icon: "Smartphone",
    brandColor: "#E85D13",
    brandText: "#FFFFFF",
    shortName: "Halo",
    tagline: "tel",
  },
] as const;

export type SnippeNetworkId = (typeof SNIPPE_NETWORKS)[number]["id"];

const NETWORK_PREFIX_HINTS: Record<number, SnippeNetworkId> = {
  // Best-effort Tanzanian number prefixes -> network. Used only to pre-select
  // the suggested network; Snippe resolves the real operator from the phone.
  75: "mpesa", // Vodacom
  76: "mpesa", // Vodacom
  77: "mpesa", // Vodacom
  74: "mpesa", // Vodacom
  67: "airtel", // Airtel
  68: "mixx", // Mixx by Yas (Airtel's new brand)
  78: "airtel", // Airtel
  65: "halotel", // Halotel
  62: "halotel", // Halotel
};

/** Suggest which network most likely covers a (normalised 255…) phone number. */
export function suggestNetwork(phone: string): SnippeNetworkId {
  const p = normalizeTzPhone(phone);
  if (p.startsWith("255")) {
    const prefix = Number(p.slice(3, 5));
    return NETWORK_PREFIX_HINTS[prefix] ?? "mpesa";
  }
  return "mpesa";
}

export const MIN_PAYMENT_TZS = 500;
export const MIN_PAYOUT_TZS = 5000;

/** Normalise a phone number to the 255… form Snippe expects (e.g. 0754… → 255754…). */
export function normalizeTzPhone(raw: string): string {
  let p = (raw || "").replace(/[^\d+]/g, "");
  if (p.startsWith("+")) p = p.slice(1);
  if (p.startsWith("0")) p = `255${p.slice(1)}`;
  if (!p.startsWith("255")) p = `255${p}`;
  return p;
}

/** 2557***123 — mask everything but the end, for the "check your phone" step. */
export function maskPhone(raw: string): string {
  const p = normalizeTzPhone(raw);
  if (p.length < 8) return raw;
  const prefix = p.slice(0, 4);
  const suffix = p.slice(-4);
  return `${prefix}••••${suffix}`;
}

export const PAYMENT_STATUS_META: Record<string, { label: string; className: string }> = {
  PENDING: {
    label: "Pending",
    className: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-transparent",
  },
  PROCESSING: {
    label: "Processing",
    className: "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 border-transparent",
  },
  SUCCESS: {
    label: "Completed",
    className: "bg-green-100 text-green-800 dark:bg-green-950/60 dark:text-green-300 border-transparent",
  },
  FAILED: {
    label: "Failed",
    className: "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 border-transparent",
  },
  EXPIRED: {
    label: "Expired",
    className: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 border-transparent",
  },
  VOIDED: {
    label: "Voided",
    className: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 border-transparent",
  },
  CANCELLED: {
    label: "Cancelled",
    className: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 border-transparent",
  },
  RECONCILIATION_REQUIRED: {
    label: "Needs review",
    className: "bg-orange-100 text-orange-800 dark:bg-orange-950/60 dark:text-orange-300 border-transparent",
  },
};

export const WITHDRAWAL_STATUS_META: Record<string, { label: string; className: string }> = {
  PENDING: {
    label: "Pending approval",
    className: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-transparent",
  },
  APPROVED: {
    label: "Approved",
    className: "bg-green-100 text-green-800 dark:bg-green-950/60 dark:text-green-300 border-transparent",
  },
  SENT_TO_SNIPPE: {
    label: "Processing",
    className: "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300 border-transparent",
  },
  SUCCESS: {
    label: "Completed",
    className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-transparent",
  },
  FAILED: {
    label: "Failed",
    className: "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 border-transparent",
  },
  DECLINED: {
    label: "Declined",
    className: "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 border-transparent",
  },
  CANCELLED: {
    label: "Cancelled",
    className: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 border-transparent",
  },
};

export const PAYMENT_TYPE_LABEL: Record<string, string> = {
  CONTRIBUTION: "Deposit / Contribution",
  DEPOSIT: "Deposit",
  LOAN_REPAYMENT: "Loan repayment",
  WITHDRAWAL: "Withdrawal",
  LOAN_DISBURSEMENT: "Loan disbursement",
  OTHER: "Payment",
};