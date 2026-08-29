import { FC, FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";

import { SYSTEM_NAME, LOGO_URL } from "@/lib/system";
import OtpInput from "@/components/OtpInput";
import FormInput from "@/components/FormInput";
import Button from "@/components/Button";
import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";
import {
  usePinSetupConfirm,
  usePinSetupRequest,
} from "@/hooks/api/auth";
import { getApiErrorMessage } from "@/lib/utils";
import { useTranslation } from "react-i18next";

const RESEND_WAIT_SECONDS = 60;

/**
 * One-time quick-login setup: phone number identifies the account, a 6-digit
 * code is emailed to prove ownership, then the member picks a 4-digit secret
 * PIN ("namba za siri") for faster PWA logins.
 */
const PinSetup: FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const [step, setStep] = useState<"phone" | "code" | "pin">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [pin, setPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [devCode, setDevCode] = useState("");
  const [emailError, setEmailError] = useState("");
  const [cooldown, setCooldown] = useState(0);

  const { mutate: sendCode, isPending: isSending } = usePinSetupRequest();
  const { mutate: confirmPinSetup, isPending: isConfirming } = usePinSetupConfirm();

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const handleSendCode = () => {
    if (!phone.trim()) {
      toast.error("Enter your phone number first.", { autoClose: 2500 });
      return;
    }
    sendCode(
      { phone_number: phone.trim() },
      {
        onSuccess: (data) => {
          setCooldown(RESEND_WAIT_SECONDS);
          setEmailError("");
          setDevCode("");
          if (data.email_sent === false) {
            setEmailError(
              data.email_error ||
                "The code could not be emailed right now. Please retry in a moment.",
            );
          }
          if (data.dev_code) {
            setDevCode(data.dev_code);
            toast.success("Demo mode: code shown below.", { autoClose: 3000 });
          } else {
            toast.success(t("auth.codeSent"), { autoClose: 3000 });
          }
          setStep("code");
        },
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Could not send the code"), {
            autoClose: 3000,
          }),
      },
    );
  };

  const handleConfirm = (e: FormEvent) => {
    e.preventDefault();
    if (pin !== confirmPin) {
      toast.error("The two PINs do not match.", { autoClose: 2500 });
      return;
    }
    if (pin.length !== 4) {
      toast.error("Choose a 4-digit secret PIN.", { autoClose: 2500 });
      return;
    }
    confirmPinSetup(
      { phone_number: phone.trim(), code: code.trim(), pin },
      {
        onSuccess: (data) => {
          if (data.email_sent === false && data.email_error) {
            setEmailError(data.email_error);
          }
          toast.success(data.message || t("auth.pinSaved"), { autoClose: 3500 });
          navigate("/login");
        },
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "That code is invalid or expired."), {
            autoClose: 3000,
          }),
      },
    );
  };

  const inputPanel = (
    <div className="w-full max-w-sm">
      <div className="mb-6 flex flex-col items-center text-center lg:hidden">
        <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-14 w-14 rounded-xl bg-blue-800/5 p-1" />
        <h3 className="mt-2 font-display text-2xl font-semibold">{t("auth.setupPinTitle")}</h3>
      </div>

      {step === "phone" && (
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); handleSendCode(); }}>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            {t("auth.pinSteps")}
          </p>
          <FormInput
            type="tel"
            name="phone"
            value={phone}
            placeholder="+254 7XX XXX XXX"
            label={t("auth.phoneNumber")}
            inputMode="tel"
            autoComplete="tel"
            onChange={(e) => setPhone(e.target.value.replace(/[^\d+\s]/g, ""))}
          />
          <Button
            text={isSending ? <Spinner /> : t("auth.sendCode")}
            type="submit"
            variant="primary"
            className="w-full"
          />
        </form>
      )}

      {step === "code" && (
        <div className="space-y-4">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            We emailed a 6-digit confirmation code. Enter it below to continue.
          </p>
          <OtpInput value={code} onChange={setCode} length={6} autoFocus />
          {devCode && (
            <div className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-center text-xs text-amber-900 dark:border-amber-600/60 dark:bg-amber-950/40 dark:text-amber-200">
              <p className="font-medium">Demo mode — use this code:</p>
              <p className="font-mono text-base tracking-widest">{devCode}</p>
            </div>
          )}
          {emailError && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
              <p className="font-medium">The email could not be delivered right now.</p>
              <p className="mt-0.5 break-words">{emailError}</p>
            </div>
          )}
          <Button
            text="Continue"
            type="button"
            variant="primary"
            className="w-full"
            disabled={code.length !== 6}
            onClick={() => setStep("pin")}
          />
          <div className="text-center">
            <button
              type="button"
              disabled={isSending || cooldown > 0}
              onClick={handleSendCode}
              className="text-xs font-medium text-blue-700 hover:underline disabled:cursor-not-allowed disabled:opacity-60 dark:text-blue-300"
            >
              {isSending
                ? "Sending..."
                : cooldown > 0
                  ? `Resend code in ${cooldown}s`
                  : "I didn't get a code — resend it"}
            </button>
          </div>
        </div>
      )}

      {step === "pin" && (
        <form className="space-y-4" onSubmit={handleConfirm}>
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Choose a 4-digit secret PIN. You'll use it together with your phone
            number to log in quickly on this phone.
          </p>
          <div>
            <p className="mb-2 text-center text-xs font-medium text-slate-500 dark:text-slate-400">
              New secret PIN
            </p>
            <OtpInput value={pin} onChange={(v) => setPin(v)} length={4} autoFocus autoComplete="off" />
          </div>
          <div>
            <p className="mb-2 text-center text-xs font-medium text-slate-500 dark:text-slate-400">
              Confirm secret PIN
            </p>
            <OtpInput value={confirmPin} onChange={(v) => setConfirmPin(v)} length={4} autoComplete="off" />
          </div>
          <Button
            text={isConfirming ? <Spinner /> : t("auth.savePin")}
            type="submit"
            variant="primary"
            className="w-full"
          />
        </form>
      )}
    </div>
  );

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-paper px-4 py-10 text-ink dark:bg-[#0d1117] dark:text-slate-100">
      <div className="grid w-full max-w-lg overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-col items-center justify-center p-8 sm:p-10">
          <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="hidden h-12 w-12 rounded-xl bg-blue-800/5 p-1 lg:block" />
          <h1 className="mb-2 hidden font-display text-2xl font-semibold lg:block">
            {t("auth.setupPinTitle")}
          </h1>
          {inputPanel}
          <div className="my-6 w-full border-t border-slate-100 dark:border-slate-800" />
          <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            <LucideIcon name="Lock" size={14} />
            Your PIN unlocks 12 hours of access, then the app locks again for security.
          </div>
        </div>
      </div>
    </div>
  );
};

export default PinSetup;