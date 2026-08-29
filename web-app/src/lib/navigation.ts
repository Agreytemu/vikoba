// Shared navigation registry for the desktop sidebar and the mobile bottom bar.
import { AppModule } from "@/lib/access-control";

export type SidebarKey =
  | "dashboard"
  | "members"
  | "accounts"
  | "transactions"
  | "loans"
  | "expenses"
  | "settings"
  | "help"
  | "users"
  | "sms"
  | "emails"
  | "whatsapp"
  | "groups"
  | "my-loans"
  | "my-wallet"
  | "notifications"
  | "community"
  | "share-outs"
  | "profile";

export interface SidebarItem {
  key: SidebarKey;
  icon: string;
  to: string;
  module?: AppModule;
  /** Show only to members (role ME). */
  memberOnly?: boolean;
}

export const sidebarItems: SidebarItem[] = [
  { key: "dashboard", icon: "BarChart4", to: "/" },
  { key: "members", icon: "Users", to: "/members", module: "members" },
  { key: "accounts", icon: "PiggyBank", to: "/accounts", module: "accounts" },
  { key: "transactions", icon: "ArrowRightLeft", to: "/transactions", module: "transactions" },
  { key: "loans", icon: "HandCoins", to: "/loans", module: "loans" },
  { key: "expenses", icon: "ReceiptText", to: "/expenses", module: "expenses" },
  { key: "groups", icon: "Boxes", to: "/groups" },
  { key: "my-loans", icon: "HandCoins", to: "/loans-me", memberOnly: true },
  { key: "my-wallet", icon: "Wallet", to: "/wallet", memberOnly: true },
  { key: "notifications", icon: "Bell", to: "/notifications", memberOnly: true },
  { key: "community", icon: "Megaphone", to: "/community", memberOnly: true },
  { key: "share-outs", icon: "Coins", to: "/share-outs", memberOnly: true },
  { key: "profile", icon: "User", to: "/profile", memberOnly: true },
  { key: "settings", icon: "Settings", to: "/settings" },
  { key: "help", icon: "CircleHelp", to: "/help" },
  { key: "users", icon: "Users", to: "/users", module: "users" },
  { key: "sms", icon: "MessageCircle", to: "/sms", module: "communications" },
  { key: "emails", icon: "Mail", to: "/emails", module: "communications" },
  { key: "whatsapp", icon: "MessageSquare", to: "/whatsapp", module: "communications" },
];

/**
 * Primary sections shown directly in the mobile bottom bar (in order).
 * Members get their own native order: dashboard, wallet, groups, profile and
 * "More" for everything else. Staff/ops keep the operations-oriented tabs.
 */
export const bottomNavPrimaryOrder: SidebarKey[] = [
  "dashboard",
  "members",
  "accounts",
  "transactions",
  "loans",
];

export const memberBottomNavPrimaryOrder: SidebarKey[] = [
  "dashboard",
  "my-wallet",
  "groups",
  "profile",
];