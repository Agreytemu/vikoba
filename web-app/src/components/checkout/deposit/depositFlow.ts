// Member wallet-deposit checkout (mobile money → savings) constants and helpers.
//
// Snippe only supports TZS. Amount limits match the backend (min 500 TZS per
// Snippe collections; the 10m cap is a sanity guard so a typo cannot create a
// giant USSD push). The fee is always TZS 0 for member collections — the
// platform absorbs Snippe's collections charge, matching the backend tx.fee.
// Every amount rendered is derived from the member's own input; the page never
// invents fees or totals.

import { MIN_PAYMENT_TZS, normalizeTzPhone } from "@/lib/payments";

export type DepositStage = "checkout" | "processing" | "success" | "failed";

export const MAX_DEPOSIT_TZS = 10_000_000;
export const DEPOSIT_FEE_TZS = 0;

/** "TZS 50,000" — integer TZS currency formatting for the deposit flows. */
export function formatDepositMoney(amount: string | number, currency = "TZS"): string {
  const n = Math.trunc(Number(amount || 0));
  if (!Number.isFinite(n)) return `${currency} 0`;
  return `${currency} ${n.toLocaleString("en-US")}`;
}

/** "+255 712 345 678" — readable rendering of an (un)normalised TZ number. */
export function displayTzPhone(raw: string): string {
  const n = normalizeTzPhone((raw || "").replace(/[^\d+]/g, ""));
  const local = n.startsWith("255") ? n.slice(3) : n;
  if (local.length !== 9) return `+${n}`;
  return `+255 ${local.slice(0, 2)} ${local.slice(2, 5)} ${local.slice(5)}`;
}

/** Strip anything but digits and cap the length (max deposit is 10 digits). */
export function normalizeDepositAmount(raw: string): string {
  return (raw || "").replace(/[^\d]/g, "").slice(0, 10);
}

/** Inline amount validation — returns a message or null when the value is ok. */
export function depositAmountError(raw: string): string | null {
  const cleaned = (raw || "").replace(/[^\d]/g, "");
  const n = Number(cleaned);
  if (!cleaned || !Number.isSafeInteger(n) || n <= 0) {
    return "Enter the amount you want to deposit.";
  }
  if (n < MIN_PAYMENT_TZS) {
    return `Minimum deposit is ${formatDepositMoney(MIN_PAYMENT_TZS)}.`;
  }
  if (n > MAX_DEPOSIT_TZS) {
    return `Maximum deposit is ${formatDepositMoney(MAX_DEPOSIT_TZS)}.`;
  }
  return null;
}