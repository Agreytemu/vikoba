import React, { FC, useState } from "react";
import { Link, useNavigate  } from "react-router-dom";
import { toast } from "react-toastify";

import LoginSvg from "@/assets/authenticate.svg";
import { SYSTEM_NAME, LOGO_URL } from "@/lib/system";
import FormInput from "@/components/FormInput";
import Spinner from "@/components/Spinner";
import Button from "@/components/Button";
// hooks
import { usePasswordReset } from "@/hooks/api/auth";
import { getApiErrorMessage } from "@/lib/utils";

const PasswordResetConfirm: FC = () => {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const searchParams = new URLSearchParams(window.location.search);
  const uid = searchParams.get("user") || "";
  const token = searchParams.get("token") || "";

  const navigate = useNavigate();

  const {mutate: passwordReset, isPending: isPasswordResetPending} = usePasswordReset()

  const handleSubmit =  (event: React.FormEvent) => {
    event.preventDefault();
    if (password !== confirmPassword) {
      toast.error("Passwords do not match", { autoClose: 3000 });
      return;
    }
    passwordReset(
      { uid, token, password },
      {
        onSuccess: (data) => {
          toast.success(data.message, { autoClose: 2000 });
          navigate("/login");
        },
        onError: (error) => {
          toast.error(getApiErrorMessage(error, "Unable to reset password"), { autoClose: 2000 });
        },
      },
    );
  }

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-paper px-4 py-10 text-ink dark:bg-[#0d1117] dark:text-slate-100">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900 lg:grid-cols-2">
        <div className="hidden flex-col justify-between bg-blue-800 p-10 text-white dark:bg-blue-900 lg:flex">
          <div>
            <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-12 w-12 rounded-xl bg-white/10 p-1" />
            <h1 className="mt-8 font-display text-4xl font-semibold leading-tight">
              Set new password
            </h1>
            <p className="mt-4 max-w-sm text-blue-100/90">
              Time to secure your account. Enter your new password to finalize the
              reset and get back to using your account.
            </p>
          </div>
          <img src={LoginSvg} alt="set password" className="mt-10 w-56 opacity-90" />
        </div>

        <div className="flex flex-col items-center justify-center p-8 sm:p-10">
          <div className="w-full max-w-sm">
            <div className="mb-6 flex flex-col items-center text-center lg:hidden">
              <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-14 w-14 rounded-xl bg-blue-800/5 p-1" />
              <h3 className="mt-2 font-display text-2xl font-semibold">Set new password</h3>
            </div>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <FormInput
                type="password"
                name="password"
                placeholder="Password"
                value={password}
                label="Password"
                onChange={(e) => setPassword(e.target.value)}
              />
              <FormInput
                type="password"
                name="confirmPassword"
                placeholder="Confirm Password"
                value={confirmPassword}
                label="ConfirmPassword"
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
              <Button
                text={isPasswordResetPending ? <Spinner /> : "Reset Password"}
                type="submit"
                variant="primary"
                className="w-full"
              />
            </form>
            <div className="my-6 border-t border-slate-100 dark:border-slate-800" />
            <p className="text-center text-sm text-slate-600 dark:text-slate-400">
              Request a new password reset?{" "}
              <Link className="font-medium text-blue-700 hover:underline dark:text-blue-300" to="/forgot-password">
                Reset now
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PasswordResetConfirm;
