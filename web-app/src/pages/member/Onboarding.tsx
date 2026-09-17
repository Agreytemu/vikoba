import { FC, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { Check, ChevronLeft, ChevronRight } from "lucide-react";
import { useGetPlans, useOnboarding } from "@/hooks/api/memberSelf";
import { getApiErrorMessage } from "@/lib/utils";

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

const Onboarding: FC = () => {
  const navigate = useNavigate();
  const { data: plans, isLoading: plansLoading, isError: plansError } = useGetPlans();
  const onboarding = useOnboarding();

  const [step, setStep] = useState(1);
  const [errors, setErrors] = useState<Record<string, string>>({});

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

  const maxDob = useMemo(() => getMaxDob(), []);

  useEffect(() => {
    document.title = "Onboarding — VICOBA kidigitali";
  }, []);

  const validateStep = (s: number): boolean => {
    const e: Record<string, string> = {};
    if (s === 1) {
      if (!form.permanent_address.trim()) e.permanent_address = "Permanent address is required";
      if (!form.street.trim()) e.street = "Street is required";
      if (!form.region) e.region = "Region is required";
    }
    if (s === 2) {
      if (!form.citizenship_type) e.citizenship_type = "Citizenship type is required";
      if (!form.gender) e.gender = "Gender is required";
      if (!form.date_of_birth) e.date_of_birth = "Date of birth is required";
      else if (!isAtLeast18(form.date_of_birth)) e.date_of_birth = "You must be at least 18 years old";
    }
    if (s === 3) {
      if (!form.occupation.trim()) e.occupation = "Occupation is required";
      if (!form.preferred_currency) e.preferred_currency = "Preferred currency is required";
    }
    // step 4 plan is optional (Skip -> Free)
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleNext = () => {
    if (!validateStep(step)) return;
    setStep((prev) => Math.min(prev + 1, 4));
  };

  const handleBack = () => {
    setErrors({});
    setStep((prev) => Math.max(prev - 1, 1));
  };

  const handleSubmit = async () => {
    if (!validateStep(1) || !validateStep(2) || !validateStep(3)) {
      // find first failing step and go there
      if (!form.permanent_address.trim() || !form.street.trim() || !form.region) {
        setStep(1);
        validateStep(1);
        return;
      }
      if (!form.citizenship_type || !form.gender || !form.date_of_birth || !isAtLeast18(form.date_of_birth)) {
        setStep(2);
        validateStep(2);
        return;
      }
      if (!form.occupation.trim()) {
        setStep(3);
        validateStep(3);
        return;
      }
    }

    try {
      await onboarding.mutateAsync({
        permanent_address: form.permanent_address.trim(),
        street: form.street.trim(),
        region: form.region,
        citizenship_type: form.citizenship_type as "BY_BIRTH" | "NATURALIZATION" | "MARRIAGE",
        gender: form.gender as "MALE" | "FEMALE",
        date_of_birth: form.date_of_birth,
        occupation: form.occupation.trim(),
        preferred_currency: form.preferred_currency,
        selected_plan: form.selected_plan,
      });
      toast.success("Onboarding completed successfully!", { autoClose: 2000 });
      navigate("/", { replace: true });
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Could not complete onboarding"), { autoClose: 3000 });
    }
  };

  const handleSkipPlan = async () => {
    setForm((prev) => ({ ...prev, selected_plan: null }));
    // directly submit with Free plan
    try {
      await onboarding.mutateAsync({
        permanent_address: form.permanent_address.trim(),
        street: form.street.trim(),
        region: form.region,
        citizenship_type: form.citizenship_type as "BY_BIRTH" | "NATURALIZATION" | "MARRIAGE",
        gender: form.gender as "MALE" | "FEMALE",
        date_of_birth: form.date_of_birth,
        occupation: form.occupation.trim(),
        preferred_currency: form.preferred_currency,
        selected_plan: null,
      });
      toast.success("Onboarding completed — Free plan selected.", { autoClose: 2000 });
      navigate("/", { replace: true });
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Could not complete onboarding"), { autoClose: 3000 });
    }
  };

  const progressPct = (step / 4) * 100;

  const hasRealPlans = plans && Array.isArray(plans) && plans.length > 0 && !plansError;

  const placeholderPlans = [
    { id: "free", name: "Free", price: 0, currency: form.preferred_currency, interval: "forever", features: ["Basic VICOBA features", "Up to 1 group", "Community support"] },
    { id: "basic", name: "Basic", price: form.preferred_currency === "USD" ? 5 : 10000, currency: form.preferred_currency, interval: "monthly", features: ["Up to 3 groups", "Contributions & loans", "Email support"] },
    { id: "pro", name: "Pro", price: form.preferred_currency === "USD" ? 12 : 25000, currency: form.preferred_currency, interval: "monthly", features: ["Unlimited groups", "Advanced reports", "Priority support"] },
  ];

  const displayedPlans = hasRealPlans
    ? [{ id: "free", name: "Free", price: 0, currency: form.preferred_currency, interval: "forever", features: ["Free forever"] } as never, ...(plans as never[])]
    : (placeholderPlans as unknown as { id: string | number; name: string; price: number | string; currency: string; interval: string; features: string[] }[]);

  return (
    <div className="min-h-screen bg-[#FDFBF7] px-4 py-8 sm:px-6">
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 text-center">
          <h1 className="font-display text-[24px] font-semibold tracking-tight text-[#1A1A1A] sm:text-[28px]">Complete your profile</h1>
          <p className="mt-1 text-[14px] text-[#6B6B6B]">Just a few more details to get you started with VICOBA kidigitali.</p>
        </div>

        {/* Progress bar */}
        <div className="mb-8">
          <div className="mb-3 flex items-center justify-between">
            {[1, 2, 3, 4].map((s) => (
              <div key={s} className="flex flex-1 items-center gap-2">
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold transition ${
                    s < step
                      ? "bg-[#115036] text-white"
                      : s === step
                        ? "bg-[#115036] text-white ring-4 ring-[#115036]/15"
                        : "border border-[#E8E2D9] bg-white text-[#6B6B6B]"
                  }`}
                >
                  {s < step ? <Check size={16} /> : s}
                </div>
                {s < 4 && <div className={`h-[2px] flex-1 ${s < step ? "bg-[#115036]" : "bg-[#E8E2D9]"}`} />}
              </div>
            ))}
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-[#E8E2D9]">
            <div className="h-full rounded-full bg-[#115036] transition-all duration-500" style={{ width: `${progressPct}%` }} />
          </div>
          <div className="mt-2 flex justify-between text-[11px] font-medium uppercase tracking-[0.08em] text-[#6B6B6B]">
            <span className={step === 1 ? "text-[#115036]" : ""}>Address</span>
            <span className={step === 2 ? "text-[#115036]" : ""}>Identity</span>
            <span className={step === 3 ? "text-[#115036]" : ""}>Work & Currency</span>
            <span className={step === 4 ? "text-[#115036]" : ""}>Plan</span>
          </div>
        </div>

        <div className="rounded-2xl border border-[#E8E2D9] bg-white p-6 shadow-[0_8px_30px_rgba(0,0,0,0.04)] sm:p-8">
          {/* Step 1 Address */}
          {step === 1 && (
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

          {/* Step 2 Citizenship / Gender / DOB */}
          {step === 2 && (
            <div className="space-y-5">
              <h2 className="font-display text-[18px] font-semibold text-[#1A1A1A]">Identity details</h2>
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
                  <p className="mt-1 text-[11px] text-[#6B6B6B]">Must be 18 years or older. Calendar picker will limit to eligible dates.</p>
                )}
              </div>
            </div>
          )}

          {/* Step 3 Occupation / Currency */}
          {step === 3 && (
            <div className="space-y-5">
              <h2 className="font-display text-[18px] font-semibold text-[#1A1A1A]">Work & currency</h2>
              <p className="text-[13px] text-[#6B6B6B]">Tell us what you do and your preferred currency.</p>

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
                      <input
                        type="radio"
                        name="preferred_currency"
                        value={c}
                        checked={form.preferred_currency === c}
                        onChange={(e) => setForm({ ...form, preferred_currency: e.target.value as "TZS" | "USD" })}
                        className="sr-only"
                      />
                      {c}
                    </label>
                  ))}
                </div>
                {errors.preferred_currency && <p className="mt-1 text-[12px] text-red-600">{errors.preferred_currency}</p>}
              </div>
            </div>
          )}

          {/* Step 4 Plans */}
          {step === 4 && (
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
                    const isSelected = form.selected_plan === plan.id || (form.selected_plan === null && plan.id === "free");
                    // Normalize free plan handling: when real plans include free, its id may be number; we treat null as free
                    const isFree = String(plan.name).toLowerCase() === "free" || String(plan.id).toLowerCase() === "free";
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
                  disabled={onboarding.isPending}
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

            {step < 4 ? (
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
                disabled={onboarding.isPending}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#115036] px-6 py-2.5 text-[14px] font-semibold text-white hover:bg-[#0e442d] disabled:opacity-60"
              >
                {onboarding.isPending ? (
                  <>
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> Completing...
                  </>
                ) : (
                  "Complete onboarding"
                )}
              </button>
            )}
          </div>

          <p className="mt-4 text-center text-[11px] text-[#6B6B6B]">Step {step} of 4</p>
        </div>

        <p className="mt-6 text-center text-[12px] text-[#6B6B6B]">
          Need help? <a href="/help" className="font-medium text-[#115036] hover:underline">Contact support</a>
        </p>
      </div>
    </div>
  );
};

export default Onboarding;
