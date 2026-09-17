import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  KycDocumentType,
  memberSelfService,
  NextOfKinPayload,
  OnboardingPayload,
  UpdateProfilePayload,
} from "@/services/memberSelf";

export const useGetMyMemberProfile = (enabled = true) =>
  useQuery({
    queryKey: ["member", "me"],
    queryFn: memberSelfService.me,
    enabled,
  });

export const useGetMyVerificationStatus = (enabled = true) =>
  useQuery({
    queryKey: ["member", "me", "verification"],
    queryFn: memberSelfService.verificationStatus,
    enabled,
  });

export const useUpdateMyProfile = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateProfilePayload) => memberSelfService.updateMe(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["member", "me"] });
      queryClient.invalidateQueries({ queryKey: ["member", "me", "verification"] });
    },
  });
};

export const useRequestOtp = () => {
  const { mutateAsync } = useMutation({
    mutationFn: (phoneNumber: string) => memberSelfService.requestOtp(phoneNumber),
  });
  return mutateAsync;
};

export const useVerifyOtp = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ phoneNumber, code }: { phoneNumber: string; code: string }) =>
      memberSelfService.verifyOtp(phoneNumber, code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["member", "me"] });
      queryClient.invalidateQueries({ queryKey: ["member", "me", "verification"] });
    },
  });
};

export const useGetMyNextOfKin = (enabled = true) =>
  useQuery({
    queryKey: ["member", "me", "next-of-kin"],
    queryFn: memberSelfService.listNextOfKin,
    enabled,
  });

export const useCreateNextOfKin = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: NextOfKinPayload) => memberSelfService.createNextOfKin(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["member", "me"] });
      queryClient.invalidateQueries({ queryKey: ["member", "me", "next-of-kin"] });
      queryClient.invalidateQueries({ queryKey: ["member", "me", "verification"] });
    },
  });
};

export const useGetMyKycDocuments = (enabled = true) =>
  useQuery({
    queryKey: ["member", "me", "kyc"],
    queryFn: memberSelfService.listKycDocuments,
    enabled,
  });

export const useUploadKycDocument = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      documentType,
      file,
    }: {
      documentType: KycDocumentType;
      file: File;
    }) => memberSelfService.uploadKycDocument(documentType, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["member", "me", "kyc"] });
      queryClient.invalidateQueries({ queryKey: ["member", "me", "verification"] });
    },
  });
};

export const useSubmitForReview = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => memberSelfService.submitForReview(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["member", "me"] });
      queryClient.invalidateQueries({ queryKey: ["member", "me", "verification"] });
    },
  });
};

export const useOnboarding = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: OnboardingPayload) => memberSelfService.onboarding(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["member", "me"] });
      queryClient.invalidateQueries({ queryKey: ["member", "me", "verification"] });
    },
  });
};

export const useGetPlans = (enabled = true) =>
  useQuery({
    queryKey: ["accounts", "plans"],
    queryFn: memberSelfService.getPlans,
    enabled,
    retry: false,
  });