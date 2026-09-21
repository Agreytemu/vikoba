// Plan-subscription checkout (payment page) constants and helpers.
//
// Every plan and price comes from the backend (admin-managed MembershipPlan).
// The frontend never decides amounts; it only renders what the API returns and
// submits plan_id — the Django service derives the charge from the DB.

import { normalizeTzPhone, suggestNetwork, type SnippeNetworkId } from "@/lib/payments";

export type SubscriptionStage = "checkout" | "processing" | "success" | "failed" | "cancelled";

export interface CheckoutPaymentMethod {
  id: string;
  label: string;
  networkId: SnippeNetworkId | null;
  tagline: string;
  enabled: boolean;
  icon: string;
}

export const CHECKOUT_PAYMENT_METHODS: CheckoutPaymentMethod[] = [
  {
    id: "mpesa",
    label: "M-Pesa",
    networkId: "mpesa",
    tagline: "Vodacom · Pay via USSD push",
    enabled: true,
    icon: "Smartphone",
  },
  {
    id: "airtel_money",
    label: "Airtel Money",
    networkId: "airtel",
    tagline: "Airtel · Pay via USSD push",
    enabled: true,
    icon: "Smartphone",
  },
  {
    id: "mixx_by_yas",
    label: "Mixx by Yas",
    networkId: "mixx",
    tagline: "Airtel · Pay via USSD push",
    enabled: true,
    icon: "Smartphone",
  },
  {
    id: "halopesa",
    label: "Halotel",
    networkId: "halotel",
    tagline: "Halotel · Pay via USSD push",
    enabled: true,
    icon: "Smartphone",
  },
  {
    id: "card",
    label: "Card",
    networkId: null,
    tagline: "Debit / credit card",
    enabled: false,
    icon: "CreditCard",
  },
];

/** Map a Snippe network id → payment method id (only the phone-driven ones). */
const NETWORK_TO_METHOD: Record<SnippeNetworkId, string> = {
  mpesa: "mpesa",
  airtel: "airtel_money",
  mixx: "mixx_by_yas",
  halotel: "halopesa",
};

/** The method matching a phone number's likely operator, e.g. "mpesa". */
export function suggestMethod(phone: string): string | null {
  const network = suggestNetwork(phone);
  return NETWORK_TO_METHOD[network] ?? null;
}

export function methodLabel(id: string): string {
  return CHECKOUT_PAYMENT_METHODS.find((m) => m.id === id)?.label ?? "Mobile Money";
}

/** "TZS 50,000" — always the plan's own currency, never a hardcoded amount. */
export function formatPlanMoney(amount: string | number, currency = "TZS"): string {
  const n = Number(amount || 0);
  return `${currency} ${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function intervalLabel(interval?: string): string {
  switch ((interval || "monthly").toLowerCase()) {
    case "weekly":
      return "per week";
    case "daily":
      return "per day";
    case "yearly":
      return "per year";
    default:
      return "per month";
  }
}

/** Inline Tanzanian mobile-money validation (XX 0712-345-678 → 0625456789). */
export function tzPhoneError(raw: string): string | null {
  const cleaned = (raw || "").replace(/[^\d+]/g, "");
  if (!cleaned) return "Enter your mobile money number";
  const n = normalizeTzPhone(raw);
  const local = n.startsWith("255") ? n.slice(3) : n;
  if (local.length !== 9 || !/^[67]/.test(local)) {
    return "Enter a valid Tanzanian mobile number, e.g. 0712 345 678";
  }
  return null;
}

export function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value.trim());
}