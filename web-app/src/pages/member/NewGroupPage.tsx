import { FC, useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { Check, ChevronLeft, ChevronRight, MapPin, PenLine, UsersRound } from "lucide-react";

import { Auth } from "@/contexts/AuthContext";
import { useGetMyMemberProfile } from "@/hooks/api/memberSelf";
import { useCreateGroup, useGetMyGroupsSummary } from "@/hooks/api/groups";
import { useUserProfileInfo } from "@/hooks/useUserProfile";
import FormInput from "@/components/FormInput";
import Spinner from "@/components/Spinner";
import { Button } from "@/components/ui/button";
import LucideIcon from "@/components/LucideIcon";
import { getApiErrorMessage } from "@/lib/utils";
import { formatPlace, reverseGeocodePlace, countryFromIp } from "@/lib/geo";
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

interface StepDef {
  label: string;
  icon: FC<{ size?: number | string; className?: string }>;
}

const STEPS: StepDef[] = [
  { label: "Name", icon: PenLine as FC },
  { label: "Location", icon: MapPin as FC },
  { label: "Review", icon: UsersRound as FC },
];

const TOTAL_STEPS = 3;

const NewGroupPage: FC = () => {
  const { isAuthenticated } = Auth();
  const navigate = useNavigate();
  const { profile: userProfile } = useUserProfileInfo();

  const { data: profile, isLoading: profileLoading } = useGetMyMemberProfile(isAuthenticated);
  const { data: mySummary, isLoading: summaryLoading } = useGetMyGroupsSummary(isAuthenticated);
  const createGroup = useCreateGroup();

  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [detectingLocation, setDetectingLocation] = useState(false);
  const [locationLabel, setLocationLabel] = useState("");
  const [form, setForm] = useState({
    name: "",
    area: "",
    region: "",
    country: "Tanzania",
    description: "",
  });

  const isVerified = Boolean(profile?.is_verified);
  const groupLimit = isVerified ? 3 : 1;
  const createdCount = mySummary?.created_count ?? 0;
  const atGroupLimit = createdCount >= groupLimit;

  useEffect(() => {
    if (atGroupLimit) {
      toast.error(
        `You can only create ${groupLimit} group${groupLimit === 1 ? "" : "s"}.`,
        { autoClose: 3500 },
      );
      navigate("/groups", { replace: true });
    }
  }, [atGroupLimit, groupLimit, navigate]);

  if (!isAuthenticated || profileLoading || summaryLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#FDFBF7]">
        <Spinner />
      </div>
    );
  }

  if (!profile || userProfile?.role !== "ME" || !profile.is_onboarded) {
    return <Navigate to="/" replace />;
  }

  // Matches a detected region against the dropdown list when country is
  // Tanzania, so the select actually shows (not silently blank) the real place.
  const normalizeDetectedRegion = (region: string): string => {
    const trimmed = region.replace(/\s+Region$/i, "").trim();
    if (
      (form.country === "Tanzania" || form.country === "") &&
      trimmed &&
      TANZANIAN_REGIONS.some((r) => r === trimmed)
    ) {
      return trimmed;
    }
    return trimmed;
  };

  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      toast.error("Location not supported on this device. Please type the area manually.", { autoClose: 3000 });
      return;
    }
    setDetectingLocation(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        let place = await reverseGeocodePlace(latitude, longitude);
        // BigDataCloud often misses rural Tanzania: fall back to IP country.
        if (!place.country) {
          const ip = await countryFromIp();
          place = { ...place, ...ip };
        }
        const detectedRegion = normalizeDetectedRegion(place.region);
        setLocationLabel(formatPlace({ ...place, region: detectedRegion }));
        setForm((prev) => ({
          ...prev,
          area: prev.area.trim() ? prev.area : place.area || "",
          region: prev.region.trim() ? prev.region : detectedRegion,
          country: prev.country.trim() ? prev.country : place.country || "Tanzania",
        }));
        if (place.country || detectedRegion || place.area) {
          toast.success("Real place name added.", { autoClose: 2500 });
        }
        setDetectingLocation(false);
      },
      () => {
        toast.error("Location was denied. Please type the area manually.", { autoClose: 3000 });
        setDetectingLocation(false);
      },
      { enableHighAccuracy: false, timeout: 8000 },
    );
  };

  const handleNext = () => {
    if (step === 1 && !form.name.trim()) {
      toast.error("Give your group a name to continue.", { autoClose: 2500 });
      return;
    }
    setStep((prev) => Math.min(prev + 1, TOTAL_STEPS));
  };

  const handleBack = () => {
    setStep((prev) => Math.max(prev - 1, 1));
  };

  const handleCreate = async () => {
    setSubmitting(true);
    try {
      const group = await createGroup.mutateAsync({
        name: form.name.trim(),
        area: form.area.trim() || undefined,
        region: form.region.trim() || undefined,
        country: form.country.trim() || undefined,
        description: form.description.trim() || undefined,
      });
      toast.success("Group created.", { autoClose: 2500 });
      navigate(`/groups/${group.id}`);
    } catch (error) {
      setSubmitting(false);
      toast.error(getApiErrorMessage(error, "Could not create the group"), { autoClose: 3500 });
    }
  };

  const progressPct = (step / TOTAL_STEPS) * 100;

  return (
    <div className="min-h-screen bg-[#FDFBF7] px-4 py-6 sm:px-6">
      <div className="mx-auto max-w-3xl">
        {/* Brand header — no sidebar, no nav, just the wizard */}
        <div className="mb-6 text-center">
          <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="mx-auto h-12 w-12 rounded-xl bg-[#115036]/5 p-1" />
          <h1 className="mt-3 font-display text-[24px] font-semibold tracking-tight text-[#1A1A1A] sm:text-[28px]">
            Start a savings group
          </h1>
          <p className="mt-1 text-[14px] text-[#6B6B6B]">
            Answer a few questions and your VICOBA group will be ready in minutes.
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
          {/* STEP 1 — Name & purpose */}
          {step === 1 && (
            <div className="space-y-5">
              <div>
                <h2 className="font-display text-[18px] font-semibold text-[#1A1A1A]">Name your group</h2>
                <p className="mt-1 text-[13px] text-[#6B6B6B]">
                  Pick a clear name so members instantly know what it is.
                </p>
              </div>
              <FormInput
                type="text"
                name="group-name"
                value={form.name}
                placeholder="e.g. Upendo Savings Group"
                label="Group name"
                autoFocus
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
              <div>
                <label htmlFor="group-description" className="mb-1 block text-[13px] font-medium text-[#1A1A1A]">
                  Purpose <span className="font-normal text-[#6B6B6B]">(optional)</span>
                </label>
                <textarea
                  id="group-description"
                  className="w-full rounded-xl border border-[#E8E2D9] bg-white px-4 py-3 text-[14px] outline-none transition focus:border-[#115036] focus:ring-2 focus:ring-[#115036]/15 dark:border-slate-500 dark:bg-slate-900 dark:text-white"
                  rows={3}
                  value={form.description}
                  placeholder="Why is this group? Who is it for?"
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </div>
            </div>
          )}

          {/* STEP 2 — Location */}
          {step === 2 && (
            <div className="space-y-5">
              <div>
                <h2 className="font-display text-[18px] font-semibold text-[#1A1A1A]">Where is the group?</h2>
                <p className="mt-1 text-[13px] text-[#6B6B6B]">
                  Members usually meet in one area — give its name so neighbours can find it.
                </p>
              </div>

              {/* Auto-detect */}
              <button
                type="button"
                onClick={handleUseMyLocation}
                disabled={detectingLocation}
                className="inline-flex items-center gap-2 rounded-xl border border-[#115036]/25 bg-[#EEF6F0] px-4 py-2.5 text-[13px] font-medium text-[#115036] transition hover:bg-[#E2F0E7] disabled:opacity-60"
              >
                {detectingLocation ? (
                  <>
                    <Spinner /> Requesting permission…
                  </>
                ) : (
                  <>
                    <LucideIcon name="MapPin" size={15} /> Use my location (real place name)
                  </>
                )}
              </button>

              {locationLabel && (
                <div className="rounded-xl border border-[#115036]/20 bg-[#EEF6F0] px-4 py-3 text-[13px] text-[#115036]">
                  <span className="font-medium">Detected location: </span>
                  {locationLabel}
                </div>
              )}

              <FormInput
                type="text"
                name="group-area"
                value={form.area}
                placeholder="e.g. Kariakoo, Mwenge, Posta"
                label="Area"
                onChange={(e) => setForm({ ...form, area: e.target.value })}
              />
              <div>
                <label htmlFor="group-region" className="mb-1 block text-[13px] font-medium text-[#1A1A1A]">
                  Region
                </label>
                <select
                  id="group-region"
                  value={form.region}
                  onChange={(e) => setForm({ ...form, region: e.target.value })}
                  className="w-full rounded-xl border border-[#E8E2D9] bg-white px-4 py-3 text-[14px] outline-none transition focus:border-[#115036] focus:ring-2 focus:ring-[#115036]/15 dark:border-slate-500 dark:bg-slate-900 dark:text-white"
                >
                  <option value="">Select a region (optional)</option>
                  {TANZANIAN_REGIONS.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </div>
              <FormInput
                type="text"
                name="group-country"
                value={form.country}
                placeholder="Country"
                label="Country"
                onChange={(e) => setForm({ ...form, country: e.target.value })}
              />
            </div>
          )}

          {/* STEP 3 — Review & create */}
          {step === 3 && (
            <div className="space-y-5">
              <div>
                <h2 className="font-display text-[18px] font-semibold text-[#1A1A1A]">Looks good, one last check</h2>
                <p className="mt-1 text-[13px] text-[#6B6B6B]">
                  Confirm the details, then create your group.
                </p>
              </div>
              <dl className="overflow-hidden rounded-xl border border-[#E8E2D9]">
                <div className="flex flex-wrap justify-between gap-2 border-b border-[#F0ECE3] bg-[#FAF8F4] px-4 py-3">
                  <dt className="text-[12px] font-medium uppercase tracking-wide text-[#6B6B6B]">Group name</dt>
                  <dd className="text-[14px] font-semibold text-[#1A1A1A]">{form.name.trim() || "—"}</dd>
                </div>
                <div className="flex flex-wrap justify-between gap-2 border-b border-[#F0ECE3] bg-[#FAF8F4] px-4 py-3">
                  <dt className="text-[12px] font-medium uppercase tracking-wide text-[#6B6B6B]">Location</dt>
                  <dd className="text-[14px] font-medium text-[#1A1A1A]">
                    {[form.area, form.region, form.country].filter(Boolean).join(", ") || "Not set"}
                  </dd>
                </div>
                <div className="flex flex-wrap justify-between gap-2 bg-[#FAF8F4] px-4 py-3">
                  <dt className="text-[12px] font-medium uppercase tracking-wide text-[#6B6B6B]">Purpose</dt>
                  <dd className="max-w-[60%] text-right text-[14px] font-medium text-[#1A1A1A]">
                    {form.description.trim() || "Not set"}
                  </dd>
                </div>
              </dl>
              <p className="flex items-start gap-2 rounded-xl border border-[#115036]/15 bg-[#EEF6F0] px-4 py-3 text-[13px] text-[#115036]">
                <LucideIcon name="UsersRound" size={16} className="mt-0.5 shrink-0" />
                You'll be the first member — invite friends after launch. You can create up to {groupLimit} group
                {groupLimit === 1 ? "" : "s"} {isVerified ? "as a verified member" : "before verification"}.
              </p>
            </div>
          )}

          {/* Footer nav */}
          <div className="mt-8 flex items-center justify-between gap-3 border-t border-[#F0ECE3] pt-5">
            <Button type="button" variant="outline" onClick={step === 1 ? () => navigate("/groups") : handleBack}>
              <ChevronLeft size={16} className="mr-1" />
              {step === 1 ? "Cancel" : "Back"}
            </Button>
            {step < TOTAL_STEPS ? (
              <Button type="button" onClick={handleNext}>
                Continue
                <ChevronRight size={16} className="ml-1" />
              </Button>
            ) : (
              <Button type="button" variant="outline" onClick={handleCreate} disabled={submitting}>
                {submitting ? (
                  <Spinner />
                ) : (
                  <>
                    <Check size={16} className="mr-1" /> Create group
                  </>
                )}
              </Button>
            )}
          </div>
        </div>

        <p className="mt-4 text-center text-[11px] text-[#6B6B6B]">Step {step} of {TOTAL_STEPS}</p>
      </div>
    </div>
  );
};

export default NewGroupPage;