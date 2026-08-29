import { useQuery } from "@tanstack/react-query";
import { communityService } from "@/services/community";

export const useGetAnnouncements = (enabled = true) =>
  useQuery({
    queryKey: ["announcements"],
    queryFn: communityService.listAnnouncements,
    enabled,
  });

export const useGetMeetings = (enabled = true) =>
  useQuery({
    queryKey: ["meetings"],
    queryFn: communityService.listMeetings,
    enabled,
  });