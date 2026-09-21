export type AppModule =
  | "members"
  | "accounts"
  | "transactions"
  | "loans"
  | "users"
  | "expenses"
  | "communications"
  | "governance";

type UserRole = "AD" | "MA" | "OP" | "FI" | "LO" | "AC" | "ME";

const moduleAccess: Record<AppModule, UserRole[]> = {
  members: ["AD", "MA", "OP", "FI", "LO", "AC"],
  accounts: ["AD", "MA", "OP", "FI", "LO", "AC"],
  transactions: ["AD", "MA", "OP", "FI", "LO", "AC"],
  loans: ["AD", "MA", "OP", "LO"],
  users: ["AD", "MA"],
  expenses: ["AD", "MA", "OP", "FI"],
  communications: ["AD", "MA", "OP", "FI"],
  governance: ["AD", "MA", "OP", "FI", "AC"],
};

export const hasModuleAccess = (role: string | undefined, module: AppModule) =>
  moduleAccess[module].includes(role as UserRole);
