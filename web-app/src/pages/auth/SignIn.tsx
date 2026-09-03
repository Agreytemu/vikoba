import React, { FC, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import LoginSvg from "@/assets/authenticate.svg";
import { SYSTEM_NAME, LOGO_URL } from "@/lib/system";

// components
import FormInput from "@/components/FormInput";
import Button from "@/components/Button";
import Spinner from "@/components/Spinner";
import OtpInput from "@/components/OtpInput";
import LucideIcon from "@/components/LucideIcon";
import { toast } from "react-toastify";
import { useLogin, usePinLogin } from "@/hooks/api/auth";
import { Auth } from "@/contexts/AuthContext";
import { getApiErrorMessage } from "@/lib/utils";

// interface LoginFormData{
//   email: string;
//   password: string
// }

const SignIn: FC = () => {
  const [mode, setMode] = useState<"email" | "pin">("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pinPhone, setPinPhone] = useState("");
  const [pin, setPin] = useState("");
  const [emailNotVerified, setEmailNotVerified] = useState(false);

  const { t } = useTranslation();
  const { mutate: userLogin, isPending: isRegisterPending } = useLogin();
  const { mutate: pinLogin, isPending: isPinPending } = usePinLogin();
  const { login } = Auth();

  // Friendly fallback increases UX when server is slow or network is unstable
  const friendlyLoginFallback =
    "Oops! Our server is having a tough moment or your connection is slow. Please refresh the page, check your internet, and try again.";

  // handle login
  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();

    userLogin(
      { email, password },
      {
        onSuccess: (data) => {
          setEmailNotVerified(false);
          login(data);
          toast.success("Login successful", { autoClose: 2000 });
        },
        onError: (error) => {
          const body = error as { email_not_verified?: boolean; detail?: string };
          setEmailNotVerified(Boolean(body?.email_not_verified));
          toast.error(getApiErrorMessage(error, friendlyLoginFallback), { autoClose: 4000 });
        },
      },
    );
  };

  const handlePinLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (pin.length !== 4) {
      toast.error("Enter your 4-digit secret PIN.", { autoClose: 2500 });
      return;
    }
    pinLogin(
      { phone_number: pinPhone.trim(), pin },
      {
        onSuccess: (data) => {
          login(data);
          toast.success("Login successful", { autoClose: 2000 });
        },
        onError: (error) => {
          const body = error as {
            pin_locked?: boolean;
            pin_not_set?: boolean;
            locked_seconds?: number;
            detail?: string;
          };
          if (body?.pin_not_set) {
            toast.info(body.detail || "Set up your secret PIN first.", { autoClose: 6000 });
          } else {
            toast.error(getApiErrorMessage(error, friendlyLoginFallback), { autoClose: 4000 });
          }
        },
      },
    );
  };

  const isBusy = isRegisterPending || isPinPending;

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-paper px-4 py-10 text-ink dark:bg-[#0d1117] dark:text-slate-100">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900 lg:grid-cols-2">
        {/* Brand panel */}
        <div className="hidden flex-col justify-between bg-blue-800 p-10 text-white dark:bg-blue-900 lg:flex">
          <div>
            <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-12 w-12 rounded-xl bg-white/10 p-1" />
            <h1 className="mt-8 font-display text-4xl font-semibold leading-tight">
              {t("auth.welcomeBack")}
            </h1>
            <p className="mt-4 max-w-sm text-blue-100/90">
              {t("auth.welcomeDescription")}
            </p>
          </div>
          <img src={LoginSvg} alt="login" className="mt-10 w-56 opacity-90" />
        </div>

        {/* Form panel */}
        <div className="flex flex-col items-center justify-center p-8 sm:p-10">
          <div className="w-full max-w-sm">
            <div className="mb-6 flex flex-col items-center text-center lg:hidden">
              <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-14 w-14 rounded-xl bg-blue-800/5 p-1" />
              <h3 className="mt-2 font-display text-2xl font-semibold">{t("auth.loginTitle")}</h3>
            </div>

            {/* Email / Quick PIN switcher */}
            <div className="mb-6 grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
              <button
                type="button"
                onClick={() => setMode("email")}
                className={`flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  mode === "email"
                    ? "bg-white text-blue-700 shadow-sm dark:bg-slate-900 dark:text-blue-300"
                    : "text-slate-600 hover:text-ink dark:text-slate-300"
                }`}
              >
                <LucideIcon name="Mail" size={16} /> {t("auth.emailTab")}
              </button>
              <button
                type="button"
                onClick={() => setMode("pin")}
                className={`flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  mode === "pin"
                    ? "bg-white text-blue-700 shadow-sm dark:bg-slate-900 dark:text-blue-300"
                    : "text-slate-600 hover:text-ink dark:text-slate-300"
                }`}
              >
                <LucideIcon name="KeyRound" size={16} /> {t("auth.quickLogin")}
              </button>
            </div>

            {import.meta.env.DEV && (
              <div className="mb-6 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-center text-xs text-amber-900 dark:border-amber-600/60 dark:bg-amber-950/40 dark:text-amber-200">
                <p className="font-medium">{t("auth.demoLogin")}</p>
                <p>
                  <span className="font-mono">admin@example.com</span> /{" "}
                  <span className="font-mono">admin12345</span>
                </p>
                <p className="mt-1 text-amber-800 dark:text-amber-300">
                  {t("auth.demoNote")}
                </p>
              </div>
            )}

            {mode === "email" ? (
              <form className="space-y-4" onSubmit={handleLogin}>
                {emailNotVerified && (
                  <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-xs text-blue-900 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100">
                    <p className="font-medium">Your email isn't verified yet.</p>
                    <p>
                      Enter the 6-digit code we emailed you, or{" "}
                      <Link
                        className="font-semibold underline"
                        to={`/verify-email?email=${encodeURIComponent(email)}`}
                      >
                        request a new code
                      </Link>.
                    </p>
                  </div>
                )}
                <FormInput
                  type="email"
                  name="email"
                  value={email}
                  placeholder={t("auth.email")}
                  label={t("auth.email")}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <FormInput
                  type="password"
                  name="password"
                  value={password}
                  placeholder={t("auth.password")}
                  label={t("auth.password")}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <div className="flex justify-end">
                  <Link className="text-xs text-blue-700 hover:underline dark:text-blue-300" to="/forgot-password">
                    {t("auth.forgotPassword")}
                  </Link>
                </div>
                <Button
                  text={isRegisterPending ? <Spinner /> : t("common.login")}
                  type="submit"
                  variant="primary"
                  className="w-full"
                />
                {isBusy && (
                  <p className="mt-3 text-center text-xs text-slate-500 dark:text-slate-400">
                    Taking longer than expected? Please check your internet and refresh the page, then try again.
                  </p>
                )}
              </form>
            ) : (
              <form className="space-y-4" onSubmit={handlePinLogin}>
                <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-xs text-blue-900 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100">
                  {t("auth.pinLoginHint")}
                </div>
                <FormInput
                  type="tel"
                  name="phone"
                  value={pinPhone}
                  placeholder="+254 7XX XXX XXX"
                  label={t("auth.phoneNumber")}
                  inputMode="tel"
                  autoComplete="tel"
                  onChange={(e) => setPinPhone(e.target.value.replace(/[^\d+\s]/g, ""))}
                />
                <div className="flex justify-center pt-1">
                  <OtpInput value={pin} onChange={setPin} length={4} autoComplete="off" />
                </div>
                <Button
                  text={isPinPending ? <Spinner /> : t("auth.pinLogin")}
                  type="submit"
                  variant="primary"
                  className="w-full"
                />
                {isBusy && (
                  <p className="mt-2 text-center text-xs text-slate-500 dark:text-slate-400">
                    Taking longer than expected? Please check your internet and refresh the page, then try again.
                  </p>
                )}
                <p className="text-center text-xs text-slate-600 dark:text-slate-400">
                  <Link
                    className="font-medium text-blue-700 hover:underline dark:text-blue-300"
                    to="/pin-setup"
                  >
                    {t("auth.setupPin")}
                  </Link>
                </p>
              </form>
            )}

            <div className="my-6 border-t border-slate-100 dark:border-slate-800" />
            <p className="text-center text-sm text-slate-600 dark:text-slate-400">
              {t("auth.dontHaveAccount")}{" "}
              <Link className="font-medium text-blue-700 hover:underline dark:text-blue-300" to="/register">
                {t("auth.signUp")}
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignIn;
