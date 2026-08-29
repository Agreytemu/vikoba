import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

export interface MyAccount {
  id: number;
  account_number: string;
  product: number;
  product_name: string;
  product_code: string;
  balance: string;
  is_active: boolean;
  opened_at: string;
}

export interface MyAccountsResponse {
  accounts: MyAccount[];
  total_balance: string;
}

export const myAccountsService = {
  listMyAccounts: () => api.get("/accounts/me/") as Promise<MyAccountsResponse>,
};

export const useGetMyAccounts = (enabled = true) =>
  useQuery({
    queryKey: ["my-accounts"],
    queryFn: myAccountsService.listMyAccounts,
    enabled,
  });