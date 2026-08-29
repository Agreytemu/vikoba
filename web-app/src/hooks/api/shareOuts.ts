import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

export interface ShareOutRecord {
  id: number;
  share_out: number;
  group_id: number;
  group_name: string;
  cycle_label: string;
  declared_at: string;
  share_out_status: string;
  amount: string;
  is_paid: boolean;
  paid_at?: string | null;
}

export const shareOutsService = {
  listMyShareOuts: () => api.get("/groups/me/share-outs") as Promise<ShareOutRecord[]>,
};

export const useGetMyShareOuts = (enabled = true) =>
  useQuery({
    queryKey: ["my-share-outs"],
    queryFn: shareOutsService.listMyShareOuts,
    enabled,
  });