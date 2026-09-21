import api from "@/lib/api";

export type KycDocumentType = "NATIONAL_ID" | "PASSPORT_PHOTO" | "SIGNATURE";

export interface VerificationStatus {
  membership_number: string;
  is_verified: boolean;
  phone_verified: boolean;
  kyc_complete: boolean;
  next_of_kin_added: boolean;
  submitted: boolean;
}

export interface MyNextOfKin {
  id: string;
  name: string;
  relationship: string;
  phone_number: string;
  national_id?: string | null;
}

export interface MyEmployment {
  employment_type: string;
  employer_name?: string | null;
  job_title?: string | null;
  monthly_income?: number | null;
  business_name?: string | null;
  business_type?: string | null;
}

export interface MyKycDocument {
  id: string;
  document_type: KycDocumentType;
  file: string;
  verified: boolean;
  verified_by?: string | null;
}

export interface MyMemberProfile {
  membership_number: string;
  salutation: string;
  first_name: string;
  middle_name?: string | null;
  last_name: string;
  phone_number: string;
  email: string;
  date_of_birth?: string | null;
  national_id?: string | null;
  kra_pin?: string | null;
  country: string;
  county: string;
  city: string;
  permanent_address?: string | null;
  street?: string | null;
  region?: string | null;
  citizenship_type?: string | null;
  gender?: string | null;
  occupation?: string | null;
  preferred_currency?: string | null;
  selected_plan?: MembershipPlan | null;
  is_onboarded?: boolean;
  onboarded_at?: string | null;
  status: string;
  phone_verified: boolean;
  is_verified: boolean;
  verification: VerificationStatus;
  next_of_kin: MyNextOfKin[];
  employment?: MyEmployment | null;
}

export interface OtpRequestResult {
  phone_number: string;
  expires_in_minutes: number;
  dev_mode: boolean;
  dev_code?: string;
  /** Delivery channel (currently only SMS; present for forward-compat). */
  channel?: string;
}

export interface NextOfKinPayload {
  name: string;
  relationship: string;
  phone_number: string;
  national_id?: string;
}

export interface UpdateProfilePayload {
  salutation?: string;
  first_name?: string;
  middle_name?: string;
  last_name?: string;
  phone_number?: string;
  date_of_birth?: string;
  national_id?: string;
  kra_pin?: string;
  country?: string;
  county?: string;
  city?: string;
}

export interface OnboardingPayload {
  permanent_address: string;
  street: string;
  region: string;
  citizenship_type: "BY_BIRTH" | "NATURALIZATION" | "MARRIAGE";
  gender: "MALE" | "FEMALE";
  date_of_birth: string;
  occupation: string;
  preferred_currency: "TZS" | "USD";
  selected_plan?: number | string | null;
}

export interface MembershipPlan {
  id: number | string;
  name: string;
  price: string | number;
  currency: string;
  interval?: string;
  features?: string[];
  is_active?: boolean;
}

export const memberSelfService = {
  me: () => api.get("/members/me") as Promise<MyMemberProfile>,

  updateMe: (data: UpdateProfilePayload) =>
    api.patch("/members/me", data) as Promise<MyMemberProfile>,

  onboarding: (data: OnboardingPayload) =>
    api.post("/members/me/onboarding/", data) as Promise<MyMemberProfile>,

  getPlans: () => api.get("/accounts/plans/") as Promise<MembershipPlan[]>,

  verificationStatus: () =>
    api.get("/members/me/verification-status") as Promise<VerificationStatus>,

  requestOtp: (phoneNumber: string) =>
    api.post("/members/me/request-otp", { phone_number: phoneNumber }) as Promise<OtpRequestResult>,

  verifyOtp: (phoneNumber: string, code: string) =>
    api.post("/members/me/verify-otp", {
      phone_number: phoneNumber,
      code,
    }) as Promise<VerificationStatus>,

  listNextOfKin: () =>
    api.get("/members/me/next-of-kin") as Promise<MyNextOfKin[]>,

  createNextOfKin: (data: NextOfKinPayload) =>
    api.post("/members/me/next-of-kin", data) as Promise<MyNextOfKin>,

  listKycDocuments: () =>
    api.get("/members/me/kyc-documents") as Promise<MyKycDocument[]>,

  uploadKycDocument: (documentType: KycDocumentType, file: File) => {
    const data = new FormData();
    data.append("document_type", documentType);
    data.append("file", file);
    return api.post("/members/me/kyc-documents", data) as Promise<MyKycDocument>;
  },

  submitForReview: () =>
    api.post("/members/me/submit-for-review") as Promise<VerificationStatus>,
};