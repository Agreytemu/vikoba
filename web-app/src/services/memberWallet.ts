import api from "@/lib/api";

export interface MemberTransaction {
  id: number;
  transaction_number: string;
  transaction_type: string;
  amount: string;
  reference: string;
  created_at: string;
  debit?: string | null;
  credit?: string | null;
  balance?: string | null;
}

export interface DepositRequest {
  id: number;
  account: number;
  account_number: string;
  product_name: string;
  amount: string;
  channel: string;
  transaction_code?: string;
  reference: string;
  status: string;
  status_display: string;
  requested_at: string;
  processed_at?: string | null;
  decline_reason?: string;
}

export interface WithdrawalRequest {
  id: number;
  account: number;
  account_number: string;
  product_name: string;
  amount: string;
  narration?: string;
  reference: string;
  status: string;
  status_display: string;
  requested_at: string;
  processed_at?: string | null;
  decline_reason?: string;
}

export interface AccountStatementResponse {
  account: {
    account_number: string;
    product_name: string;
    balance: string;
  };
  transactions: MemberTransaction[];
}

export interface CreateDepositPayload {
  account_number: string;
  amount: string;
  channel?: string;
  transaction_code?: string;
}

export interface CreateWithdrawalPayload {
  account_number: string;
  amount: string;
  narration?: string;
}

export const memberWalletService = {
  getStatement: (accountNumber: string) =>
    api.get(`/accounts/me/${accountNumber}/transactions/`) as Promise<AccountStatementResponse>,

  listDeposits: () => api.get("/accounts/me/deposits/") as Promise<DepositRequest[]>,

  createDeposit: (data: CreateDepositPayload) =>
    api.post("/accounts/me/deposits/", data) as Promise<DepositRequest>,

  listWithdrawals: () => api.get("/accounts/me/withdrawals/") as Promise<WithdrawalRequest[]>,

  createWithdrawal: (data: CreateWithdrawalPayload) =>
    api.post("/accounts/me/withdrawals/", data) as Promise<WithdrawalRequest>,
};