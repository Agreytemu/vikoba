import { FC, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { Check, ChevronLeft, ChevronRight, Smartphone, ShieldCheck, CreditCard, UserRound } from "lucide-react";

import { Auth } from "@/contexts/AuthContext";
import {
  useGetMyMemberProfile,
  useGetMyKycDocuments,
  useGetMyNextOfKin,
  useGetPlans,
  useOnboarding,
  useRequestOtp,
  useSubmitForReview,
  useUploadKycDocument,
  useCreateNextOfKin,
  useVerifyOtp,
} from "@/hooks/api/memberSelf";
import { KycDocumentType } from "@/services/memberSelf";
import { getApiErrorMessage } from "@/lib/utils";
import FormInput from "@/components/FormInput";
import OtpInput from "@/components/OtpInput";
import Spinner from "@/components/Spinner";
import KycUploadButton from "@/components/KycUploadButton";
import { SYSTEM_NAME, LOGO_URL } from "@/lib/system";

const TANZANIAN_REGIONS = [
  "Arusha",
  "Dar es Salaam",
  "Dodoma",
  "Geita",
  "Iringa",
  "Kagera",
  "Katavi",
  "Kigoma",
  "Kilimanjaro",
  "Lindi",
  "Manyara",
  "Mara",
  "Mbeya",
  "Morogoro",
  "Mtwara",
  "Mwanza",
  "Njombe",
  "Pwani",
  "Rukwa",
  "Ruvuma",
  "Shinyanga",
  "Simiyu",
  "Singida",
  "Songwe",
  "Tabora",
  "Tanga",
] as const;

interface FormState {
  permanent_address: string;
  street: string;
  region: string;
  citizenship_type: "" | "BY_BIRTH" | "NATURALIZATION" | "MARRIAGE";
  gender: "" | "MALE" | "FEMALE";
  date_of_birth: string;
  occupation: string;
  preferred_currency: "TZS" | "USD";
  selected_plan: string | number | null;
}

const TOTAL_STEPS = 5;

const getMaxDob = () => {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 18);
  return d.toISOString().split("T")[0];
};

const isAtLeast18 = (dob: string) => {
  if (!dob) return false;
  const birth = new Date(dob);
  if (isNaN(birth.getTime())) return false;
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
  return age >= 18;
};

interface StepDef {
  label: string;
  icon: FC<{ size?: number | string; className?: string }>;
}

const STEPS: StepDef[] = [
  { label: "Phone", icon: Smartphone as FC },
  { label: "Address", icon: UserRound as FC },
  { label: "Profile", icon: UserRound as FC },
  { label: "Documents", icon: ShieldCheck as FC },
  { label: "Plan", icon: CreditCard as FC },
];

const Onboarding: FC = () => {
  const { isAuthenticated } = Auth();
  const navigate = useNavigate();

  const { data: profile, isLoading: profileLoading } = useGetMyMemberProfile(isAuthenticated);
  const { data: kycDocs, isLoading: kycLoading } = useGetMyKycDocuments(isAuthenticated);
  const { data: nextOfKin, isLoading: nokLoading } = useGetMyNextOfKin(isAuthenticated);
  const { data: plans, isLoading: plansLoading, isError: plansError } = useGetPlans(isAuthenticated);

  const requestOtp = useRequestOtp();
  const verifyOtp = useVerifyOtp();
  const uploadKyc = useUploadKycDocument();
  const createNextOfKin = useCreateNextOfKin();
  const onboarding = useOnboarding();
  const submitForReview = useSubmitForReview();

  const [step, setStep] = useState(1);
  const [finishing, setFinishing] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [otpPhone, setOtpPhone] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [otpChannel, setOtpChannel] = useState<string | null>(null);
  const [otpSending, setOtpSending] = useState(false);

  const [form, setForm] = useState<FormState>({
    permanent_address: "",
    street: "",
    region: "",
    citizenship_type: "",
    gender: "",
    date_of_birth: "",
    occupation: "",
    preferred_currency: "TZS",
    selected_plan: null,
  });

  const [nok, setNok] = useState({
    name: "",
    relationship: "",
    phone_number: "",
    national_id: "",
  });

  const maxDob = useMemo(() => getMaxDob(), []);

  const phoneVerified = Boolean(profile?.phone_verified);

  // Prefill from existing profile data so a returning member resumes where they
  // left off instead of re-entering everything.
  useEffect(() => {
    if (!profile) return;
    setOtpPhone((p) => p || profile.phone_number || "");
    setForm((prev) => ({
      ...prev,
      permanent_address: prev.permanent_address || profile.permanent_address || "",
      street: prev.street || profile.street || "",
      region: prev.region || profile.region || "",
      citizenship_type: (prev.citizenship_type || profile.citizenship_type || "") as FormState["citizenship_type"],
      gender: (prev.gender || profile.gender || "") as FormState["gender"],
      date_of_birth: prev.date_of_birth || profile.date_of_birth || "",
      occupation: prev.occupation || profile.occupation || "",
      preferred_currency: profile.preferred_currency === "USD" ? "USD" : "TZS",
    }));
  }, [profile]);

  useEffect(() => {
    document.title = "Getting started — VICOBA kidigitali";
  }, []);

  // Jump to the first incomplete step when the wizard opens, so a returning
  // member resumes where they left off instead of re-entering everything.
  const startingStep = useMemo(() => {
    if (!profile) return null;
    if (!profile.phone_verified) return 1;
    if (!profile.permanent_address || !profile.street || !profile.region) return 2;
    if (!profile.citizenship_type || !profile.gender || !profile.date_of_birth || !profile.occupation)
      return 3;
    const uploaded = new Set((kycDocs ?? []).map((d) => d.document_type));
    const allDocs = ["NATIONAL_ID", "PASSPORT_PHOTO", "SIGNATURE"].every((t) =>
      uploaded.has(t as KycDocumentType),
    );
    if (!allDocs || (nextOfKin ?? []).length === 0) return 4;
    return 5;
  }, [profile, kycDocs, nextOfKin]);

  const hasJumped = useRef(false);
  useEffect(() => {
    if (startingStep && !hasJumped.current) {
      hasJumped.current = true;
      setStep(startingStep);
    }
  }, [startingStep, hasJumped]);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (profileLoading || kycLoading || nokLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#FDFBF7]">
        <Spinner />
      </div>
    );
  }

  if (profile?.is_onboarded) {
    return <Navigate to="/" replace />;
  }

  const handleSendOtp = async () => {
    if (!otpPhone) {
      toast.error("Enter your phone number first.", { autoClose: 2000 });
      return;
    }
    setOtpSending(true);
    try {
      const result = await requestOtp(otpPhone);
      setDevCode(result.dev_mode && result.dev_code ? result.dev_code : null);
      setOtpChannel(result.channel ?? null);
      if (result.channel === "whatsapp") {
        toast.success("Code sent to your WhatsApp.", { autoClose: 3000 });
      } else if (result.dev_mode && result.dev_code) {
        toast.info("Verification code sent (demo mode shows it below).", { autoClose: 3000 });
      } else {
        toast.success("Verification code sent to your phone.", { autoClose: 2000 });
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Could not send code"), { autoClose: 3000 });
    } finally {
      setOtpSending(false);
    }
  };

  const handleVerifyOtp = () => {
    if (!otpPhone || !otpCode) {
      toast.error("Enter the 6-digit code we sent.", { autoClose: 2000 });
      return;
    }
    verifyOtp.mutate(
      { phoneNumber: otpPhone, code: otpCode },
      {
        onSuccess: () => {
          setDevCode(null);
          setOtpCode("");
          toast.success("Phone number verified.", { autoClose: 2000 });
        },
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Verification failed"), { autoClose: 3000 }),
      },
    );
  };

  const validateStep = (s: number): boolean => {
    const e: Record<string, string> = {};
    if (s === 1) {
      if (!phoneVerified) e.phone = "Verify your phone number to continue";
    }
    if (s === 2) {
      if (!form.permanent_address.trim()) e.permanent_address = "Permanent address is required";
      if (!form.street.trim()) e.street = "Street is required";
      if (!form.region) e.region = "Region is required";
    }
    if (s === 3) {
      if (!form.citizenship_type) e.citizenship_type = "Citizenship type is required";
      if (!form.gender) e.gender = "Gender is required";
      if (!form.date_of_birth) e.date_of_birth = "Date of birth is required";
      else if (!isAtLeast18(form.date_of_birth)) e.date_of_birth = "You must be at least 18 years old";
      if (!form.occupation.trim()) e.occupation = "Occupation is required";
    }
    if (s === 4) {
      const uploaded = new Set((kycDocs ?? []).map((d) => d.document_type));
      const missing = ["NATIONAL_ID", "PASSPORT_PHOTO", "SIGNATURE"].filter(
        (t) => !uploaded.has(t as KycDocumentType),
      );
      if (missing.length > 0) e.kyc = `Upload all documents (missing: ${missing.join(", ")})`;
      if ((nextOfKin ?? []).length === 0) e.nok = "Add at least one next of kin";
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleNext = () => {
    if (!validateStep(step)) return;
    setErrors({});
    setStep((prev) => Math.min(prev + 1, TOTAL_STEPS));
  };

  const handleBack = () => {
    setErrors({});
    setStep((prev) => Math.max(prev - 1, 1));
  };

  const handleSubmit = async () => {
    setFinishing(true);
    try {
      const payload = {
        permanent_address: form.permanent_address.trim(),
        street: form.street.trim(),
        region: form.region,
        citizenship_type: form.citizenship_type as "BY_BIRTH" | "NATURALIZATION" | "MARRIAGE",
        gender: form.gender as "MALE" | "FEMALE",
        date_of_birth: form.date_of_birth,
        occupation: form.occupation.trim(),
        preferred_currency: form.preferred_currency,
        selected_plan: form.selected_plan,
      };
      await onboarding.mutateAsync(payload);
      // Kick off the staff KYC review pipeline automatically, best-effort.
      if (!profile?.verification?.submitted) {
        try {
          await submitForReview.mutateAsync();
        } catch {
          /* review submission is opportunistic */
        }
      }
      // Give the "Setting up your account..." screen a moment to breathe.
      setTimeout(() => navigate("/", { replace: true }), 2200);
    } catch (error) {
      setFinishing(false);
      toast.error(getApiErrorMessage(error, "Could not complete onboarding"), { autoClose: 3500 });
    }
  };

  const handleUploadKyc = (documentType: KycDocumentType, file: File) => {
    uploadKyc.mutate(
      { documentType, file },
      {
        onSuccess: () => {
          toast.success("Document uploaded.", { autoClose: 2000 });
          setErrors((prev) => {
            if (!prev.kyc) return prev;
            const { kyc, ...rest } = prev;
            void kyc;
            return rest;
          });
        },
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Upload failed"), { autoClose: 3000 }),
      },
    );
  };

  const handleAddNextOfKin = () => {
    if (!nok.name || !nok.relationship || !nok.phone_number) {
      toast.error("Name, relationship and phone are required.", { autoClose: 2500 });
      return;
    }
    createNextOfKin.mutate(
      { ...nok, national_id: nok.national_id || undefined },
      {
        onSuccess: () => {
          setNok({ name: "", relationship: "", phone_number: "", national_id: "" });
          toast.success("Next of kin added.", { autoClose: 2000 });
          setErrors((prev) => {
            if (!prev.nok) return prev;
            const { nok: _nok, ...rest } = prev;
            void _nok;
            return rest;
          });
        },
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Could not add next of kin"), { autoClose: 3000 }),
      },
    );
  };

  const uploadedSet = useMemo(
    () => new Set((kycDocs ?? []).map((doc) => doc.document_type)),
    [kycDocs],
  );

  const handleSkipPlan = () => {
    setForm((prev) => ({ ...prev, selected_plan: null }));
    handleSubmit();
  };

  const progressPct = (step / TOTAL_STEPS) * 100;

  const hasRealPlans = plans && Array.isArray(plans) && plans.length > 0 && !plansError;

  const placeholderPlans = [
    { id: "free", name: "Free", price: 0, currency: form.preferred_currency, interval: "forever", features: ["Basic VICOBA features", "Up to 1 group", "Community support"] },
    { id: "basic", name: "Basic", price: form.preferred_currency === "USD" ? 5 : 10000, currency: form.preferred_currency, interval: "monthly", features: ["Up to 3 groups", "Contributions & loans", "Email support"] },
    { id: "pro", name: "Pro", price: form.preferred_currency === "USD" ? 12 : 25000, currency: form.preferred_currency, interval: "monthly", features: ["Unlimited groups", "Advanced reports", "Priority support"] },
  ];

  const displayedPlans = hasRealPlans
    ? [{ id: "free", name: "Free", price: 0, currency: form.preferred_currency, interval: "forever", features: ["Free forever"] }, ...plans]
    : (placeholderPlans as unknown as { id: string | number; name: string; price: number | string; currency: string; interval: string; features: string[] }[]);

  const KYC_TYPES: { type: KycDocumentType; label: string }[] = [
    { type: "NATIONAL_ID", label: "National ID" },
    { type: "PASSPORT_PHOTO", label: "Passport photo" },
    { type: "SIGNATURE", label: "Signature" },
  ];

  // ---------- Full-screen "setting up your account" ----------
  if (finishing) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#115036] px-6 text-center text-white">
        <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="mb-6 h-16 w-16 rounded-2xl bg-white/10 p-2" />
        <div className="mb-5 h-10 w-10 animate-spin rounded-full border-[3px] border-white/25 border-t-white" />
        <h1 className="font-display text-2xl font-semibold">Setting up your account...</h1>
        <p className="mt-2 max-w-sm text-sm text-white/75">
          We're preparing your dashboard, groups and plan. This takes just a moment.
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FDFBF7] px-4 py-6 sm:px-6">
      <div className="mx-auto max-w-3xl">
        {/* Brand header — no sidebar, no nav, just the wizard */}
        <div className="mb-6 text-center">
          <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="mx-auto h-12 w-12 rounded-xl bg-[#115036]/5 p-1" />
          <h1 className="mt-3 font-display text-[24px] font-semibold tracking-tight text-[#1A1A1A] sm:text-[28px]">
            Welcome to VICOBA kidigitali
          </h1>
          <p className="mt-1 text-[14px] text-[#6B6B6B]">
            {step === 1
              ? "Step 1 — confirm your phone number. Your email is already verified."
              : "Let's get your account ready for your group."}
          </p>
        </div>

        {/* Stepper */}
        <div className="mb-8">
          <div className="mb-3 hidden items-center justify-between sm:flex">
            {STEPS.map((s, i) => {
              const n = i + 1;
              const Icon = s.icon;
              return (
                <div key={s.label} className="flex flex-1 items-center gap-2">
                  <div
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold transition ${
                      n < step
                        ? "bg-[#115036] text-white"
                        : n === step
                          ? "bg-[#115036] text-white ring-4 ring-[#115036]/15"
                          : "border border-[#E8E2D9] bg-white text-[#6B6B6B]"
                    }`}
                  >
                    {n < step ? <Check size={16} /> : <Icon size={15} />}
                  </div>
                  {n < TOTAL_STEPS && <div className={`h-[2px] flex-1 ${n < step ? "bg-[#115036]" : "bg-[#E8E2D9]"}`} />}
                </div>
              );
            })}
          </div>

          <div className="sm:hidden">
            <p className="mb-2 text-center text-[11px] font-semibold uppercase tracking-[0.08em] text-[#115036]">
              Step {step} of {TOTAL_STEPS} — {STEPS[step - 1].label}
            </p>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-[#E8E2D9]">
            <div className="h-full rounded-full bg-[#115036] transition-all duration-500" style={{ width: `${progressPct}%` }} />
          </div>
          <div className="mt-2 hidden justify-between text-[11px] font-medium uppercase tracking-[0.08em] text-[#6B6B6B] sm:flex">
            {STEPS.map((s, i) => (
              <span key={s.label} className={step === i + 1 ? "text-[#115036]" : ""}>
                {s.label}
              </span>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-[#E8E2D9] bg-white p-6 shadow-[0_8px_30px_rgba(0,0,0,0.04)] sm:p-8">
          {/* STEP 1 — Phone verification */}
          {step === 1 && (
            <div className="space-y-5">
              <h2 className="font-display text-[18px] font-semibold text-[#1A1A1A]">Verify your phone number</h2>
              <p className="text-[13px] text-[#6B6B6B]">
                Your email is already verified. Now confirm the phone number your group will use.
              </p>

              {phoneVerified ? (
                <div className="flex items-center gap-2 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm font-medium text-green-700">
                  <Check size={18} /> {otpPhone} is verified
                </div>
              ) : (
                <div className="space-y-4">
                  <FormInput
                    type="tel"
                    name="otpPhone"
                    value={otpPhone}
                    placeholder="+255712345678"
                    label="Phone number"
                    inputMode="tel"
                    onChange={(e) => setOtpPhone(e.target.value)}
                  />
                  <button
                    type="button"
                    disabled={otpSending}
                    onClick={handleSendOtp}
                    className="w-full rounded-xl border border-[#115036]/30 bg-[#EEF6F0] px-4 py-2.5 text-[14px] font-medium text-[#115036] hover:bg-[#E2F0E7] disabled:opacity-60"
                  >
                    {otpSending ? "Sending..." : "Send verification code"}
                  </button>

                  {otpChannel === "whatsapp" && (
                    <div className="flex items-start gap-2 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
                      <span>
                        The code was sent as a WhatsApp message. Check WhatsApp on {otpPhone} and enter it below.
                      </span>
                    </div>
                  )}
                  {devCode && (
                    <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                      Demo mode — use this code:{" "}
                      <span className="font-mono text-base font-semibold tracking-widest">{devCode}</span>
                    </div>
                  )}

                  <div className="flex flex-col items-center gap-3">
                    <OtpInput value={otpCode} onChange={setOtpCode} length={6} />
                    <button
                      type="button"
                      disabled={verifyOtp.isPending}
                      onClick={handleVerifyOtp}
                      className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#115036] px-6 py-2.5 text-[14px] font-semibold text-white hover:bg-[#0e442d] disabled:opacity-60"
                    >
                      {verifyOtp.isPending ? <Spinner /> : "Verify phone"}
                    </button>
                  </div>
                  {errors.phone && <p className="text-[12px] text-red-600">{errors.phone}</p>}
                </div>
              )}
            </div>
          )}

          {/* STEP 2 — Address */}
          {step === 2 && (
            <div className="space-y-5">
              <h2 className="font-display text-[18px] font-semibold text-[#1A1A1A]">Where do you live?</h2>
              <p className="text-[13px] text-[#6B6B6B]">This helps your group know your location and improves account recovery.</p>

              <div>
                <label htmlFor="permanent_address" className="mb-1.5 block text-[13px] font-medium text-[#1A1A1A]">
                  Permanent address <span className="text-red-600">*</span>
                </label>
                <input
                  id="permanent_address"
                  type="text"
                  value={form.permanent_address}
                  onChange={(e) => setForm({ ...form, permanent_address: e.target.value })}
                  placeholder="e.g. P.O. Box 123, Ilala"
                  className={`w-full rounded-xl border px-4 py-3 text-[14px] outline-none transition placeholder:text-[#9A9A9A] focus:border-[#115036] focus:ring-2 focus:ring-[#115036]/10 ${errors.permanent_address ? "border-red-300 bg-red-50/40" : "border-[#E8E2D9] bg-[#FDFBF7]"}`}
                />
                {errors.permanent_address && <p className="mt-1 text-[12px] text-red-600">{errors.permanent_address}</p>}
              </div>

              <div>
                <label htmlFor="street" className="mb-1.5 block text-[13px] font-medium text-[#1A1A1A]">
                  Street <span className="text-red-600">*</span>
                </label>
                <input
                  id="street"
                  type="text"
                  value={form.street}
                  onChange={(e) => setForm({ ...form, street: e.target.value })}
                  placeholder="e.g. Uhuru Street"
                  className={`w-full rounded-xl border px-4 py-3 text-[14px] outline-none transition placeholder:text-[#9A9A9A] focus:border-[#115036] focus:ring-2 focus:ring-[#115036]/10 ${errors.street ? "border-red-300 bg-red-50/40" : "border-[#E8E2D9] bg-[#FDFBF7]"}`}
                />
                {errors.street && <p className="mt-1 text-[12px] text-red-600">{errors.street}</p>}
              </div>

              <div>
                <label htmlFor="region" className="mb-1.5 block text-[13px] font-medium text-[#1A1A1A]">
                  Region <span className="text-red-600">*</span>
                </label>
                <select
                  id="region"
                  value={form.region}
                  onChange={(e) => setForm({ ...form, region: e.target.value })}
                  className={`w-full rounded-xl border px-4 py-3 text-[14px] outline-none transition focus:border-[#115036] focus:ring-2 focus:ring-[#115036]/10 ${errors.region ? "border-red-300 bg-red-50/40" : "border-[#E8E2D9] bg-[#FDFBF7]"}`}
                >
                  <option value="">Select region</option>
                  {TANZANIAN_REGIONS.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
                {errors.region && <p className="mt-1 text-[12px] text-red-600">{errors.region}</p>}
              </div>
            </div>
          )}

          {/* STEP 3 — Identity + Work */}
          {step === 3 && (
            <div className="space-y-5">
              <h2 className="font-display text-[18px] font-semibold text-[#1A1A1A]">Profile, your work & currency</h2>
              <p className="text-[13px] text-[#6B6B6B]">Required for verification and compliance.</p>

              <div>
                <label htmlFor="citizenship_type" className="mb-1.5 block text-[13px] font-medium text-[#1A1A1A]">
                  Citizenship type <span className="text-red-600">*</span>
                </label>
                <select
                  id="citizenship_type"
                  value={form.citizenship_type}
                  onChange={(e) => setForm({ ...form, citizenship_type: e.target.value as FormState["citizenship_type"] })}
                  className={`w-full rounded-xl border px-4 py-3 text-[14px] outline-none transition focus:border-[#115036] focus:ring-2 focus:ring-[#115036]/10 ${errors.citizenship_type ? "border-red-300 bg-red-50/40" : "border-[#E8E2D9] bg-[#FDFBF7]"}`}
                >
                  <option value="">Select citizenship</option>
                  <option value="BY_BIRTH">By birth</option>
                  <option value="NATURALIZATION">By naturalization / application</option>
                  <option value="MARRIAGE">By marriage</option>
                </select>
                {errors.citizenship_type && <p className="mt-1 text-[12px] text-red-600">{errors.citizenship_type}</p>}
              </div>

              <div>
                <p className="mb-1.5 block text-[13px] font-medium text-[#1A1A1A]">
                  Gender <span className="text-red-600">*</span>
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {(["MALE", "FEMALE"] as const).map((g) => (
                    <label
                      key={g}
                      className={`flex cursor-pointer items-center justify-center gap-2 rounded-xl border px-4 py-3 text-[14px] font-medium transition ${
                        form.gender === g ? "border-[#115036] bg-[#115036] text-white" : "border-[#E8E2D9] bg-[#FDFBF7] text-[#1A1A1A] hover:border-[#115036]/30"
                      }`}
                    >
                      <input type="radio" name="gender" value={g} checked={form.gender === g} onChange={(e) => setForm({ ...form, gender: e.target.value as FormState["gender"] })} className="sr-only" />
                      {g === "MALE" ? "Male" : "Female"}
                    </label>
                  ))}
                </div>
                {errors.gender && <p className="mt-1 text-[12px] text-red-600">{errors.gender}</p>}
              </div>

              <div>
                <label htmlFor="date_of_birth" className="mb-1.5 block text-[13px] font-medium text-[#1A1A1A]">
                  Date of birth <span className="text-red-600">*</span>
                </label>
                <input
                  id="date_of_birth"
                  type="date"
                  value={form.date_of_birth}
                  max={maxDob}
                  onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })}
                  className={`w-full rounded-xl border px-4 py-3 text-[14px] outline-none transition focus:border-[#115036] focus:ring-2 focus:ring-[#115036]/10 ${errors.date_of_birth ? "border-red-300 bg-red-50/40" : "border-[#E8E2D9] bg-[#FDFBF7]"}`}
                />
                {errors.date_of_birth ? (
                  <p className="mt-1 text-[12px] text-red-600">{errors.date_of_birth}</p>
                ) : (
                  <p className="mt-1 text-[11px] text-[#6B6B6B]">Must be 18 years or older.</p>
                )}
              </div>

              <div>
                <label htmlFor="occupation" className="mb-1.5 block text-[13px] font-medium text-[#1A1A1A]">
                  Occupation <span className="text-red-600">*</span>
                </label>
                <input
                  id="occupation"
                  type="text"
                  value={form.occupation}
                  onChange={(e) => setForm({ ...form, occupation: e.target.value })}
                  placeholder="e.g. Farmer, Teacher, Business owner"
                  className={`w-full rounded-xl border px-4 py-3 text-[14px] outline-none transition placeholder:text-[#9A9A9A] focus:border-[#115036] focus:ring-2 focus:ring-[#115036]/10 ${errors.occupation ? "border-red-300 bg-red-50/40" : "border-[#E8E2D9] bg-[#FDFBF7]"}`}
                />
                {errors.occupation && <p className="mt-1 text-[12px] text-red-600">{errors.occupation}</p>}
              </div>

              <div>
                <p className="mb-1.5 block text-[13px] font-medium text-[#1A1A1A]">
                  Preferred currency <span className="text-red-600">*</span>
                </p>
                <div className="grid grid-cols-2 gap-3">
                  {(["TZS", "USD"] as const).map((c) => (
                    <label
                      key={c}
                      className={`flex cursor-pointer items-center justify-center gap-2 rounded-xl border px-4 py-3 text-[14px] font-medium transition ${
                        form.preferred_currency === c ? "border-[#115036] bg-[#115036] text-white" : "border-[#E8E2D9] bg-[#FDFBF7] text-[#1A1A1A] hover:border-[#115036]/30"
                      }`}
                    >
                      <input type="radio" name="preferred_currency" value={c} checked={form.preferred_currency === c} onChange={(e) => setForm({ ...form, preferred_currency: e.target.value as "TZS" | "USD" })} className="sr-only" />
                      {c === "TZS" ? "TZS — Tanzanian Shilling" : "USD — US Dollar"}
                    </label>
                  ))}
                </div>
                {errors.preferred_currency && <p className="mt-1 text-[12px] text-red-600">{errors.preferred_currency}</p>}
              </div>
            </div>
          )}

          {/* STEP 4 — KYC + Next of kin */}
          {step === 4 && (
            <div className="space-y-5">
              <div className="rounded-xl border border-[#115036]/15 bg-[#EEF6F0] px-4 py-3">
                <p className="text-[13px] font-medium text-[#115036]">
                  Don't worry — only one step ahead after this!
                </p>
              </div>

              <div>
                <h2 className="font-display text-[18px] font-semibold text-[#1A1A1A]">Verify your identity</h2>
                <p className="mt-1 text-[13px] text-[#6B6B6B]">
                  Upload these three documents. Staff will review them to unlock loans and withdrawals.
                </p>
                <div className="mt-4 grid gap-4 sm:grid-cols-3">
                  {KYC_TYPES.map(({ type, label }) => (
                    <div key={type} className="rounded-xl border border-[#E8E2D9] bg-[#FDFBF7] p-4">
                      <div className="flex items-center justify-between">
                        <p className="text-[13px] font-medium text-[#1A1A1A]">{label}</p>
                        {uploadedSet.has(type) ? (
                          <Check size={18} className="text-green-600" />
                        ) : (
                          <span className="text-[11px] text-[#9A9A9A]">Not uploaded</span>
                        )}
                      </div>
                      <KycUploadButton
                        uploaded={uploadedSet.has(type)}
                        uploading={uploadKyc.isPending}
                        onUpload={(file) => handleUploadKyc(type, file)}
                      />
                    </div>
                  ))}
                </div>
                {errors.kyc && <p className="mt-2 text-[12px] text-red-600">{errors.kyc}</p>}
              </div>

              <div>
                <h2 className="font-display text-[18px] font-semibold text-[#1A1A1A]">Next of kin</h2>
                <p className="mt-1 text-[13px] text-[#6B6B6B]">Who should we contact if we can't reach you?</p>
                <div className="mt-4 space-y-3 rounded-xl border border-[#E8E2D9] bg-[#FDFBF7] p-4">
                  <FormInput
                    type="text"
                    name="nokName"
                    value={nok.name}
                    placeholder="Full name"
                    label="Name"
                    onChange={(e) => setNok({ ...nok, name: e.target.value })}
                  />
                  <div className="grid grid-cols-2 gap-3">
                    <FormInput
                      type="text"
                      name="nokRelationship"
                      value={nok.relationship}
                      placeholder="Spouse, sibling..."
                      label="Relationship"
                      onChange={(e) => setNok({ ...nok, relationship: e.target.value })}
                    />
                    <FormInput
                      type="tel"
                      name="nokPhone"
                      value={nok.phone_number}
                      placeholder="+255712345678"
                      label="Phone"
                      inputMode="tel"
                      onChange={(e) => setNok({ ...nok, phone_number: e.target.value })}
                    />
                  </div>
                  <FormInput
                    type="text"
                    name="nokNationalId"
                    value={nok.national_id}
                    placeholder="National ID (optional)"
                    label="National ID"
                    onChange={(e) => setNok({ ...nok, national_id: e.target.value })}
                  />
                  <button
                    type="button"
                    disabled={createNextOfKin.isPending}
                    onClick={handleAddNextOfKin}
                    className="w-full rounded-xl border border-[#115036]/30 bg-[#EEF6F0] px-4 py-2.5 text-[14px] font-medium text-[#115036] hover:bg-[#E2F0E7] disabled:opacity-60"
                  >
                    {createNextOfKin.isPending ? "Adding..." : "Add next of kin"}
                  </button>
                </div>
                {(nextOfKin ?? []).length > 0 && (
                  <ul className="mt-3 space-y-2">
                    {(nextOfKin ?? []).map((kin) => (
                      <li key={kin.id} className="flex items-start justify-between gap-2 rounded-xl bg-[#FDFBF7] px-4 py-2.5 text-[13px]">
                        <span className="font-medium text-[#1A1A1A]">{kin.name}</span>
                        <span className="text-[#6B6B6B]">{kin.relationship}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {errors.nok && <p className="mt-2 text-[12px] text-red-600">{errors.nok}</p>}
              </div>
            </div>
          )}

          {/* STEP 5 — Plan */}
          {step === 5 && (
            <div className="space-y-5">
              <h2 className="font-display text-[18px] font-semibold text-[#1A1A1A]">Choose your plan</h2>
              <p className="text-[13px] text-[#6B6B6B]">Select a plan to continue. You can skip and stay on Free.</p>

              {plansLoading ? (
                <div className="flex items-center justify-center py-10">
                  <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#E8E2D9] border-t-[#115036]" />
                </div>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {displayedPlans.map((plan: { id: string | number; name: string; price: string | number; currency: string; interval?: string; features?: string[] }, idx: number) => {
                    const isFree = String(plan.name).toLowerCase() === "free" || String(plan.id).toLowerCase() === "free";
                    const isSelected = form.selected_plan === plan.id || (form.selected_plan === null && isFree);
                    const priceDisplay = isFree ? "Free" : `${plan.price} ${plan.currency}`;
                    return (
                      <button
                        key={String(plan.id) + idx}
                        type="button"
                        onClick={() => setForm({ ...form, selected_plan: isFree ? null : plan.id })}
                        className={`text-left rounded-2xl border p-5 transition ${
                          isSelected ? "border-[#115036] bg-[#EEF6F0] shadow-[0_4px_16px_rgba(17,80,54,0.08)]" : "border-[#E8E2D9] bg-[#FDFBF7] hover:border-[#115036]/30 hover:bg-white"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <h3 className="text-[15px] font-semibold text-[#1A1A1A]">{plan.name}</h3>
                          {isSelected && (
                            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#115036] text-white">
                              <Check size={14} />
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-[14px] font-semibold text-[#115036]">
                          {priceDisplay}
                          {!isFree && plan.interval && <span className="text-[11px] font-medium text-[#6B6B6B]"> / {plan.interval}</span>}
                        </p>
                        {plan.features && plan.features.length > 0 && (
                          <ul className="mt-3 space-y-1">
                            {plan.features.slice(0, 3).map((f: string) => (
                              <li key={f} className="flex gap-1.5 text-[12px] leading-4 text-[#3D3D3D]">
                                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[#115036]" />
                                {f}
                              </li>
                            ))}
                          </ul>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={handleSkipPlan}
                  disabled={onboarding.isPending || finishing}
                  className="text-[13px] font-medium text-[#115036] hover:underline disabled:opacity-60"
                >
                  Skip → Free
                </button>
                <p className="text-[11px] text-[#6B6B6B]">Free plan is always available</p>
              </div>
            </div>
          )}

          {/* Navigation */}
          <div className="mt-8 flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={handleBack}
              disabled={step === 1}
              className="inline-flex items-center gap-1.5 rounded-xl border border-[#E8E2D9] bg-white px-5 py-2.5 text-[14px] font-medium text-[#1A1A1A] hover:bg-[#FDFBF7] disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft size={16} /> Back
            </button>

            {step < TOTAL_STEPS ? (
              <button
                type="button"
                onClick={handleNext}
                className="inline-flex items-center gap-1.5 rounded-xl bg-[#115036] px-6 py-2.5 text-[14px] font-semibold text-white hover:bg-[#0e442d]"
              >
                Next <ChevronRight size={16} />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={onboarding.isPending || finishing}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#115036] px-6 py-2.5 text-[14px] font-semibold text-white hover:bg-[#0e442d] disabled:opacity-60"
              >
                {onboarding.isPending || finishing ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> Finishing...
                  </>
                ) : (
                  "Finish setup"
                )}
              </button>
            )}
          </div>

          <p className="mt-4 text-center text-[11px] text-[#6B6B6B]">Step {step} of {TOTAL_STEPS}</p>
        </div>

        <p className="mt-6 text-center text-[12px] text-[#6B6B6B]">
          Need help?{" "}
          <a href="/help" className="font-medium text-[#115036] hover:underline">
            Contact support
          </a>
        </p>
      </div>
    </div>
  );
};

export default Onboarding;