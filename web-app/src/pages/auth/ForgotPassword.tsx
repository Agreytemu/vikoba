import React, { FC, useState } from "react";
import { Link } from "react-router-dom";
import Spinner from "@/components/Spinner";
import { toast } from "react-toastify";

import ForgotPasswordSvg from "@/assets/forgot-password.png";
import { SYSTEM_NAME, LOGO_URL } from "@/lib/system";

// components
import FormInput from "@/components/FormInput";
import Button from "@/components/Button";

// Hooks
import { useRequestPasswordReset } from "@/hooks/api/auth";
import { getApiErrorMessage } from "@/lib/utils";

const ForgotPassword: FC = () => {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState("");

  const {
    mutate: requestPasswordReset,
    isPending: isRequestPasswordResetPending,
  } = useRequestPasswordReset();

  const handleEmailSubmit =  (e: React.FormEvent) => {
    e.preventDefault();
    requestPasswordReset(
      { email },
      {
        onSuccess: (data) => {
          const body = data as {
            message?: string;
            email_sent?: boolean;
            email_error?: string;
          };
          setEmail("");
          setEmailError("");
          if (body.email_sent === false) {
            setEmailError(
              body.email_error ||
                "The reset email could not be sent right now. Check SMTP settings on the server, then retry.",
            );
            return;
          }
          toast.success(body.message || "Password reset email sent", { autoClose: 3000 });
        },
        onError: (error) => {
          toast.error(getApiErrorMessage(error, "Unable to send password reset email"), {
            autoClose: 2000,
          });
        },
      },
    );
  };

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-paper px-4 py-10 text-ink dark:bg-[#0d1117] dark:text-slate-100">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900 lg:grid-cols-2">
        <div className="hidden flex-col justify-between bg-blue-800 p-10 text-white dark:bg-blue-900 lg:flex">
          <div>
            <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-12 w-12 rounded-xl bg-white/10 p-1" />
            <h1 className="mt-8 font-display text-4xl font-semibold leading-tight">
              Recover your account
            </h1>
            <p className="mt-4 max-w-sm text-blue-100/90">
              Need to recover your account? Simply provide your email, and we'll
              send you instructions to reset your password in your email.
            </p>
          </div>
          <img src={ForgotPasswordSvg} alt="recover account" className="mt-10 w-56 opacity-90" />
        </div>

        <div className="flex flex-col items-center justify-center p-8 sm:p-10">
          <div className="w-full max-w-sm">
            <div className="mb-6 flex flex-col items-center text-center lg:hidden">
              <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-14 w-14 rounded-xl bg-blue-800/5 p-1" />
              <h3 className="mt-2 font-display text-2xl font-semibold">Recover your account</h3>
            </div>
            <form className="space-y-4" onSubmit={handleEmailSubmit}>
              <FormInput
                type="email"
                name="email"
                value={email}
                placeholder="Email"
                label="Email"
                onChange={(e) => setEmail(e.target.value)}
              />
              {emailError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
                  <p className="font-medium">The email could not be delivered right now.</p>
                  <p className="mt-0.5 break-words">{emailError}</p>
                  <p className="mt-1.5">
                    Check your SMTP credentials (a Gmail <strong>App Password</strong>, not your
                    normal password) on Render, then send the reset again.
                  </p>
                </div>
              )}
              <Button
                text={isRequestPasswordResetPending ? <Spinner /> : "Send Email"}
                type="submit"
                variant="primary"
                className="w-full"
              />
            </form>
            <div className="my-6 border-t border-slate-100 dark:border-slate-800" />
            <p className="text-center text-sm text-slate-600 dark:text-slate-400">
              Remembered your password?{" "}
              <Link className="font-medium text-blue-700 hover:underline dark:text-blue-300" to="/login">
                back to login
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
