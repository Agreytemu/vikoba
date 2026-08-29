import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notificationsService } from "@/services/notifications";

const NOTIFICATIONS_KEYS = ["my-notifications"] as const;

export const useGetMyNotifications = (enabled = true) =>
  useQuery({
    queryKey: [...NOTIFICATIONS_KEYS],
    queryFn: notificationsService.list,
    enabled,
  });

export const useMarkNotificationsRead = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => notificationsService.markRead(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEYS }),
  });
};