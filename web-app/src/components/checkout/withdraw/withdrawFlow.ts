// Member withdrawal checkout (savings → mobile money via Snippe payout)
// constants and helpers.
//
// Withdrawals go ONLY to the member's verified phone number — the backend
// ignores any client-supplied number, so the page never asks for one. Amount
// limits match the backend (min 5,000 TZS per Snippe payouts; the 10m cap is
// the same sanity guard as deposits). The fee is always TZS 0 for member
// payouts — the platform absorbs Snippe's charge, matching the backend tx.fee.

import { MIN_PAYOUT_TZS } from "@/lib/payments";
import { MAX_DEPOSIT_TZS, formatDepositMoney } from "../deposit/depositFlow";

export type WithdrawStage = "checkout" | "processing" | "success" | "failed" | "review";

export const MAX_WITHDRAW_TZS = MAX_DEPOSIT_TZS;
export const WITHDRAW_FEE_TZS = 0;

/** Strip anything but digits and cap the length (max payout is 10 digits). */
export function normalizeWithdrawAmount(raw: string): string {
  return (raw || "").replace(/[^\d]/g, "").slice(0, 10);
}

/**
 * Inline amount validation. The max is the selected account's available
 * balance (the backend debits exactly that account), hard-capped at 10m TZS.
 */
export function withdrawAmountError(
  raw: string,
  availableBalance: number,
): string | null {
  const cleaned = (raw || "").replace(/[^\d]/g, "");
  const n = Number(cleaned);
  if (!cleaned || !Number.isSafeInteger(n) || n <= 0) {
    return "Enter the amount you want to withdraw.";
  }
  if (n < MIN_PAYOUT_TZS) {
    return `Minimum withdrawal is ${formatDepositMoney(MIN_PAYOUT_TZS)}.`;
  }
  if (Number.isFinite(availableBalance) && n > availableBalance) {
    return `Amount exceeds your available balance of ${formatDepositMoney(availableBalance)}.`;
  }
  if (n > MAX_WITHDRAW_TZS) {
    return `Maximum withdrawal is ${formatDepositMoney(MAX_WITHDRAW_TZS)}.`;
  }
  return null;
}