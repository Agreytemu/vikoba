import api from "@/lib/api";

export interface AppNotification {
  id: number;
  title: string;
  body: string;
  kind: string;
  link?: string | null;
  read: boolean;
  created_at: string;
}

export const notificationsService = {
  list: () => api.get("/auth/notifications/") as Promise<AppNotification[]>,

  markRead: () => api.post("/auth/notifications/read/") as Promise<AppNotification[]>,
};