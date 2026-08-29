import { FC, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "react-toastify";

import MailSvg from "@/assets/authenticate.svg";
import { SYSTEM_NAME, LOGO_URL } from "@/lib/system";
import FormInput from "@/components/FormInput";
import OtpInput from "@/components/OtpInput";
import Button from "@/components/Button";
import Spinner from "@/components/Spinner";
import { useEmailVerify, useEmailVerifyRequest } from "@/hooks/api/auth";
import { getApiErrorMessage } from "@/lib/utils";

const RESEND_WAIT_SECONDS = 60;

/**
 * Email verification screen: the 6-digit code sent on registration (and
 * re-sendable) must be confirmed before the account can log in.
 */
const VerifyEmail: FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [email, setEmail] = useState(searchParams.get("email") || "");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState("");
  const [emailError, setEmailError] = useState("");
  const [cooldown, setCooldown] = useState(0);

  const { mutate: sendCode, isPending: isSending } = useEmailVerifyRequest();
  const { mutate: confirmCode, isPending: isConfirming } = useEmailVerify();

  useEffect(() => {
    if (searchParams.get("email")) setEmail(searchParams.get("email") || "");
  }, [searchParams]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const finish = (message: string) => {
    toast.success(message, { autoClose: 3000 });
    navigate("/login");
  };

  const handleSendCode = () => {
    if (!email) {
      toast.error("Enter your email address first.", { autoClose: 2500 });
      return;
    }
    sendCode(
      { email },
      {
        onSuccess: (data) => {
          setCooldown(RESEND_WAIT_SECONDS);
          setEmailError("");
          if (data.already_verified) {
            finish("Your email is already verified. You can log in now.");
            return;
          }
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
            toast.success("Verification code sent. Check your inbox.", { autoClose: 3000 });
          }
        },
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Could not send the code"), { autoClose: 3000 }),
      },
    );
  };

  const handleVerify = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || code.trim().length < 4) {
      toast.error("Enter the 6-digit code we sent to your email.", { autoClose: 2500 });
      return;
    }
    confirmCode(
      { email, code: code.trim() },
      {
        onSuccess: (data) => {
          if (data.already_verified) {
            finish("Your email is already verified. You can log in now.");
            return;
          }
          finish("Email verified. You can log in now.");
        },
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "That code is invalid or expired."), {
            autoClose: 3000,
          }),
      },
    );
  };

  const authRequiredNote = (
    <div className="mt-6 rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-900 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100">
      You'll be able to sign in as soon as your email is verified. Verification is
      one-time — after that, log in with your email and password as usual.
    </div>
  );

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-paper px-4 py-10 text-ink dark:bg-[#0d1117] dark:text-slate-100">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900 lg:grid-cols-2">
        <div className="hidden flex-col justify-between bg-blue-800 p-10 text-white dark:bg-blue-900 lg:flex">
          <div>
            <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-12 w-12 rounded-xl bg-white/10 p-1" />
            <h1 className="mt-8 font-display text-4xl font-semibold leading-tight">
              Verify your email
            </h1>
            <p className="mt-4 max-w-sm text-blue-100/90">
              We sent a 6-digit code to your inbox. Enter it here to confirm your
              email address before your first log in.
            </p>
          </div>
          <img src={MailSvg} alt="verify email" className="mt-10 w-56 opacity-90" />
        </div>

        <div className="flex flex-col items-center justify-center p-8 sm:p-10">
          <div className="w-full max-w-sm">
            <div className="mb-6 flex flex-col items-center text-center lg:hidden">
              <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-14 w-14 rounded-xl bg-blue-800/5 p-1" />
              <h3 className="mt-2 font-display text-2xl font-semibold">Verify your email</h3>
            </div>

            <form className="space-y-4" onSubmit={handleVerify}>
              <FormInput
                type="email"
                name="email"
                value={email}
                placeholder="Email"
                label="Email"
                onChange={(e) => setEmail(e.target.value)}
              />
              <div className="flex justify-center pt-1">
                <OtpInput value={code} onChange={setCode} length={6} autoFocus />
              </div>
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
                  <p className="mt-1.5">
                    Check your SMTP credentials (a Gmail <strong>App Password</strong>,
                    not your normal password) on Render, then resend. The demo code
                    above still lets you in for testing.
                  </p>
                </div>
              )}
              <Button
                text={isConfirming ? <Spinner /> : "Verify email"}
                type="submit"
                variant="primary"
                className="w-full"
              />
            </form>

            <div className="mt-4 text-center">
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

            {authRequiredNote}

            <div className="my-6 border-t border-slate-100 dark:border-slate-800" />
            <p className="text-center text-sm text-slate-600 dark:text-slate-400">
              Already verified?{" "}
              <Link className="font-medium text-blue-700 hover:underline dark:text-blue-300" to="/login">
                Go to login
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VerifyEmail;