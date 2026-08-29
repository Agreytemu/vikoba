import api from "@/lib/api";

export interface Announcement {
  id: number;
  title: string;
  body: string;
  status: string;
  status_display: string;
  pinned: boolean;
  author_name: string;
  created_at: string;
}

export interface Meeting {
  id: number;
  title: string;
  description: string;
  starts_at: string;
  ends_at?: string | null;
  location: string;
  created_by_name: string;
  created_at: string;
}

export const communityService = {
  listAnnouncements: () =>
    api.get("/announcements/") as Promise<Announcement[]>,

  listMeetings: () => api.get("/meetings/") as Promise<Meeting[]>,
};