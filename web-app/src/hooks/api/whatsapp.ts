import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CreateWhatsAppSessionPayload,
  whatsappService,
} from "@/services/whatsapp";

const WHATSAPP_KEYS = ["whatsapp"] as const;

export const useGetWhatsAppSessions = (enabled = true) =>
  useQuery({
    queryKey: [...WHATSAPP_KEYS, "sessions"],
    queryFn: whatsappService.listSessions,
    enabled,
  });

export const useSessionStatus = (
  sessionId?: string,
  refetchInterval?: number,
) =>
  useQuery({
    queryKey: [...WHATSAPP_KEYS, "sessions", sessionId],
    queryFn: () => whatsappService.sessionStatus(sessionId as string),
    enabled: Boolean(sessionId),
    refetchInterval: (query) => {
      const status = (query.state.data as { status?: string } | undefined)?.status;
      const isDone = status === "connected" || status === "logged_out";
      return isDone ? false : (refetchInterval ?? 2000);
    },
  });

export const useCreateWhatsAppSession = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateWhatsAppSessionPayload) =>
      whatsappService.createSession(payload),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: [...WHATSAPP_KEYS, "sessions"] }),
  });
};

export const useSetPrimarySession = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sessionId, isPrimary }: { sessionId: string; isPrimary: boolean }) =>
      whatsappService.setPrimary(sessionId, isPrimary),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: [...WHATSAPP_KEYS, "sessions"] }),
  });
};

export const useRemoveSession = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => whatsappService.removeSession(sessionId),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: [...WHATSAPP_KEYS, "sessions"] }),
  });
};

export const usePairWhatsAppSession = (sessionId?: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (phone: string) =>
      whatsappService.pairSession(sessionId as string, phone),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: [...WHATSAPP_KEYS, "sessions", sessionId],
        exact: false,
      }),
  });
};

export const useSendTestMessage = (sessionId?: string) =>
  useMutation({
    mutationFn: ({ to, text }: { to: string; text: string }) =>
      whatsappService.sendTest(sessionId as string, to, text),
  });

export const useBulkSendMessage = (sessionId?: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { text: string; group_id?: number; phones?: string[] }) =>
      whatsappService.bulkSend(sessionId as string, payload),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: [...WHATSAPP_KEYS, "sessions"],
        exact: false,
      }),
  });
};