import { FC, useMemo, useState } from "react";
import { toast } from "react-toastify";

import {
  useCreateNextOfKin,
  useGetMyKycDocuments,
  useGetMyMemberProfile,
  useGetMyNextOfKin,
  useGetMyVerificationStatus,
  useRequestOtp,
  useSubmitForReview,
  useUploadKycDocument,
  useVerifyOtp,
} from "@/hooks/api/memberSelf";
import { KycDocumentType } from "@/services/memberSelf";
import Button from "@/components/Button";
import FormInput from "@/components/FormInput";
import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";
import KycUploadButton from "@/components/KycUploadButton";
import { getApiErrorMessage } from "@/lib/utils";

const KYC_LABELS: Record<KycDocumentType, string> = {
  NATIONAL_ID: "National ID",
  PASSPORT_PHOTO: "Passport photo",
  SIGNATURE: "Signature",
};

const KYC_TYPES = ["NATIONAL_ID", "PASSPORT_PHOTO", "SIGNATURE"] as const;

/**
 * The member verification workflow: status checklist, phone OTP, next of kin,
 * KYC uploads and the submit-for-review action. Lives on the member profile
 * page — the dashboard keeps only the overview.
 */
const VerificationWorkflow: FC = () => {
  const { data: profile, isLoading: isProfileLoading } = useGetMyMemberProfile();
  const {
    data: verification,
    isLoading: isVerificationLoading,
  } = useGetMyVerificationStatus();
  const { data: kycDocuments, isLoading: isKycLoading } = useGetMyKycDocuments();
  const { data: nextOfKin, isLoading: isNextOfKinLoading } =
    useGetMyNextOfKin();

  const requestOtp = useRequestOtp();
  const verifyOtp = useVerifyOtp();
  const createNextOfKin = useCreateNextOfKin();
  const uploadKyc = useUploadKycDocument();
  const submitForReview = useSubmitForReview();

  const [otpPhone, setOtpPhone] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [otpInput, setOtpInput] = useState("");
  const [otpSending, setOtpSending] = useState(false);

  const [nok, setNok] = useState({
    name: "",
    relationship: "",
    phone_number: "",
    national_id: "",
  });

  const uploadedTypes = useMemo(
    () => new Set((kycDocuments ?? []).map((doc) => doc.document_type)),
    [kycDocuments],
  );
  const verifiedTypes = useMemo(
    () =>
      new Set(
        (kycDocuments ?? [])
          .filter((doc) => doc.verified)
          .map((doc) => doc.document_type),
      ),
    [kycDocuments],
  );

  const isLoading =
    isProfileLoading || isVerificationLoading || isKycLoading || isNextOfKinLoading;

  const allDocsUploaded = KYC_TYPES.every((type) => uploadedTypes.has(type));
  const canSubmit =
    !verification?.is_verified &&
    !verification?.submitted &&
    !!verification?.phone_verified &&
    !!verification?.next_of_kin_added &&
    allDocsUploaded;

  const handleSendOtp = async () => {
    if (!otpPhone) {
      toast.error("Enter your phone number first.", { autoClose: 2000 });
      return;
    }
    setOtpSending(true);
    try {
      const result = await requestOtp(otpPhone);
      setDevCode(result.dev_mode && result.dev_code ? result.dev_code : null);
      if (result.dev_mode && result.dev_code) {
        toast.info("Verification code sent (demo mode shows it below).", { autoClose: 3000 });
      } else {
        toast.success("Verification code sent to your phone by SMS.", { autoClose: 2000 });
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Could not send code"), { autoClose: 3000 });
    } finally {
      setOtpSending(false);
    }
  };

  const handleVerifyOtp = () => {
    if (!otpPhone || !otpInput) return;
    verifyOtp.mutate(
      { phoneNumber: otpPhone, code: otpInput },
      {
        onSuccess: () => {
          setDevCode(null);
          setOtpInput("");
          toast.success("Phone number verified.", { autoClose: 2000 });
        },
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Verification failed"), { autoClose: 3000 }),
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
        },
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Could not add next of kin"), {
            autoClose: 3000,
          }),
      },
    );
  };

  const handleUploadKyc = (documentType: KycDocumentType, file: File) => {
    if (file.size > 10 * 1024 * 1024) {
      toast.error("File is too large — must be 10MB or less. Please compress the image or choose a smaller file.", { autoClose: 3500 });
      return;
    }
    uploadKyc.mutate(
      { documentType, file },
      {
        onSuccess: () => toast.success(`${KYC_LABELS[documentType]} uploaded.`, { autoClose: 2000 }),
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Upload failed"), { autoClose: 3000 }),
      },
    );
  };

  const handleSubmitForReview = () => {
    submitForReview.mutate(undefined, {
      onSuccess: () => toast.success("Submitted for verification.", { autoClose: 2500 }),
      onError: (error) =>
        toast.error(getApiErrorMessage(error, "Could not submit"), { autoClose: 3000 }),
    });
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
        No member profile is linked to this account. Contact support.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {profile.is_verified ? (
        <div className="rounded-2xl border border-green-200 bg-green-50 p-5 text-green-800 dark:border-green-900 dark:bg-green-950/40 dark:text-green-200">
          <div className="flex items-center gap-2 font-medium">
            <LucideIcon name="BadgeCheck" /> Account fully verified
          </div>
          <p className="mt-1 text-sm">
            You can take loans and request withdrawals. Groups, hisa, deposits and
            contributions are open to everyone already.
          </p>
        </div>
      ) : verification?.submitted ? (
        <div className="rounded-2xl border border-blue-200 bg-blue-50 p-5 text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-200">
          <div className="flex items-center gap-2 font-medium">
            <LucideIcon name="Hourglass" /> Under review
          </div>
          <p className="mt-1 text-sm">
            Your details have been submitted. A staff member will verify your KYC
            documents; verification unlocks loans and withdrawals.
          </p>
        </div>
      ) : (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          <div className="flex items-center gap-2 font-medium">
            <LucideIcon name="Info" /> Complete these steps to get verified
          </div>
          <ul className="mt-2 space-y-1 text-sm">
            {[
              { done: !!verification?.phone_verified, label: "Verify your phone number" },
              { done: !!verification?.next_of_kin_added, label: "Add a next of kin" },
              { done: allDocsUploaded, label: "Upload National ID, passport photo and signature" },
            ].map((step) => (
              <li key={step.label} className="flex items-center gap-2">
                <LucideIcon
                  name={step.done ? "CheckCircle2" : "Circle"}
                  size={16}
                  className={step.done ? "text-green-600" : "text-amber-400"}
                />
                {step.label}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <h2 className="mb-4 flex items-center gap-2 font-display text-lg font-semibold">
            <LucideIcon name="Smartphone" /> Phone verification
          </h2>
          {verification?.phone_verified ? (
            <div className="flex items-center gap-2 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm font-medium text-green-700 dark:border-green-900 dark:bg-green-950/40 dark:text-green-300">
              <LucideIcon name="CheckCircle2" size={18} /> {profile.phone_number} is verified
            </div>
          ) : (
            <div className="space-y-3">
              <FormInput
                type="tel"
                name="otpPhone"
                value={otpPhone}
                placeholder="+255712345678"
                label="Phone number"
                onChange={(e) => setOtpPhone(e.target.value)}
              />
              <Button
                text={otpSending ? <Spinner /> : "Send verification code by SMS"}
                type="button"
                variant="secondary"
                onClick={handleSendOtp}
                className="w-full"
              />
              {devCode && (
                <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-200">
                  Demo code: <span className="font-mono font-semibold">{devCode}</span>
                </div>
              )}
              <div className="flex gap-2">
                <FormInput
                  type="text"
                  name="otpCode"
                  value={otpInput}
                  placeholder="6-digit code"
                  label="Code"
                  onChange={(e) => setOtpInput(e.target.value)}
                />
                <div className="grid items-end">
                  <Button
                    text={verifyOtp.isPending ? <Spinner /> : "Verify"}
                    type="button"
                    variant="primary"
                    onClick={handleVerifyOtp}
                  />
                </div>
              </div>
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <h2 className="mb-4 flex items-center gap-2 font-display text-lg font-semibold">
            <LucideIcon name="UserRound" /> Next of kin
          </h2>
          <div className="space-y-3">
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
            <Button
              text={createNextOfKin.isPending ? <Spinner /> : "Add next of kin"}
              type="button"
              variant="secondary"
              onClick={handleAddNextOfKin}
              className="w-full"
            />
          </div>
          {(nextOfKin ?? []).length > 0 && (
            <ul className="mt-4 space-y-2 border-t border-slate-100 pt-4 dark:border-slate-800">
              {(nextOfKin ?? []).map((kin) => (
                <li
                  key={kin.id}
                  className="flex items-start justify-between gap-2 rounded-xl bg-slate-50 px-4 py-3 text-sm dark:bg-slate-800/60"
                >
                  <div>
                    <p className="font-medium">{kin.name}</p>
                    <p className="text-slate-500 dark:text-slate-400">
                      {kin.relationship} · {kin.phone_number}
                    </p>
                  </div>
                  <LucideIcon name="UserCheck" className="mt-1 text-green-600" size={18} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
        <h2 className="mb-4 flex items-center gap-2 font-display text-lg font-semibold">
          <LucideIcon name="FileCheck" /> KYC documents
        </h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {KYC_TYPES.map((type) => {
            const uploaded = uploadedTypes.has(type);
            const verified = verifiedTypes.has(type);
            return (
              <div
                key={type}
                className="rounded-xl border border-slate-200 p-4 dark:border-slate-800"
              >
                <div className="flex items-center justify-between">
                  <p className="font-medium">{KYC_LABELS[type]}</p>
                  {verified ? (
                    <LucideIcon name="BadgeCheck" className="text-green-600" size={20} />
                  ) : uploaded ? (
                    <LucideIcon name="Clock" className="text-amber-500" size={20} />
                  ) : (
                    <LucideIcon name="FileQuestion" className="text-slate-400" size={20} />
                  )}
                </div>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  {verified
                    ? "Verified by staff"
                    : uploaded
                      ? "Uploaded — awaiting review"
                      : "Not uploaded"}
                </p>
                <KycUploadButton
                  uploaded={uploaded}
                  uploading={uploadKyc.isPending}
                  onUpload={(file) => handleUploadKyc(type, file)}
                />
              </div>
            );
          })}
        </div>
      </section>

      {!profile.is_verified && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <h2 className="mb-3 font-display text-lg font-semibold">Submit for verification</h2>
          <Button
            text={submitForReview.isPending ? <Spinner /> : "Submit for review"}
            type="button"
            variant="primary"
            disabled={!canSubmit}
            onClick={handleSubmitForReview}
            className="w-full sm:w-auto"
          />
          {!canSubmit && (
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              Complete phone verification, add a next of kin and upload all three KYC
              documents first.
            </p>
          )}
        </section>
      )}
    </div>
  );
};

export default VerificationWorkflow;