import { FC, useState } from "react";
// import axios from "axios";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";

import LoginSvg from "@/assets/authenticate.svg";
import { SYSTEM_NAME, LOGO_URL } from "@/lib/system";
// import { apiBaseUrl } from "@/constants";
// components
import FormInput from "@/components/FormInput";
import Button from "@/components/Button";
import Spinner from "@/components/Spinner";
import CountryPhoneInput from "@/components/CountryPhoneInput";
import { useRegister } from "@/hooks/api/auth";
import { getApiErrorMessage } from "@/lib/utils";

const SignUp: FC = () => {
  // TODO: manage input type and icon state independently and validate form input
  // const [inputType, setInputType] = useState("password");
  // const [inputIcon, setInputIcon] = useState("EyeOff");
  // const [loading, setLoading] = useState(false);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");

  const navigate = useNavigate();
 const { mutate: register, isPending: isRegisterPending } = useRegister();
 

  const friendlyRegisterFallback =
    "Oops! Our server is having a tough moment or your connection is slow. Please refresh the page, check your internet, and try again.";

  const handleSignup = (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== password2) {
      toast.error("Passwords do not match", { autoClose: 2000 });
      return;
    }
    // setLoading(true);
   register(
      {
        first_name: firstName,
        last_name: lastName,
        phone_number: phoneNumber,
        email,
        password,
        confirm_password: password2,
      },
      {
        onSuccess: () => {
          toast.success("Account created. Check your inbox for the 6-digit code to verify your email.", { autoClose: 4000 });
          navigate(`/verify-email?email=${encodeURIComponent(email)}`);
        },
        onError: (error) => {
          // setLoading(false);
          toast.error(getApiErrorMessage(error, friendlyRegisterFallback), { autoClose: 4000 });
        },
      },
      )
  };
  
  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-paper px-4 py-10 text-ink dark:bg-[#0d1117] dark:text-slate-100">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-card dark:border-slate-800 dark:bg-slate-900 lg:grid-cols-2">
        <div className="hidden flex-col justify-between bg-blue-800 p-10 text-white dark:bg-blue-900 lg:flex">
          <div>
            <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-12 w-12 rounded-xl bg-white/10 p-1" />
            <h1 className="mt-8 font-display text-4xl font-semibold leading-tight">
              Create an account
            </h1>
            <p className="mt-4 max-w-sm text-blue-100/90">
              Ready to get started? Just a few steps away from joining our
              community. Complete the form to set up your account — after
              verifying your email you'll sign in, verify your phone, add a
              next of kin and upload your KYC documents to get fully verified.
            </p>
          </div>
          <img src={LoginSvg} alt="create account" className="mt-10 w-56 opacity-90" />
        </div>

        <div className="flex flex-col items-center justify-center p-8 sm:p-10">
          <div className="w-full max-w-sm">
            <div className="mb-6 flex flex-col items-center text-center lg:hidden">
              <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-14 w-14 rounded-xl bg-blue-800/5 p-1" />
              <h3 className="mt-2 font-display text-2xl font-semibold">Create account!</h3>
            </div>
            <form className="space-y-4" onSubmit={handleSignup}>
              <div className="grid grid-cols-2 gap-3">
                <FormInput
                  type="text"
                  name="firstName"
                  value={firstName}
                  placeholder="First name"
                  className=""
                  label="First name"
                  onChange={(e) => setFirstName(e.target.value)}
                />
                <FormInput
                  type="text"
                  name="lastName"
                  value={lastName}
                  placeholder="Last name"
                  className=""
                  label="Last name"
                  onChange={(e) => setLastName(e.target.value)}
                />
              </div>
              <CountryPhoneInput
                id="phoneNumber"
                label="Phone number"
                value={phoneNumber}
                onChange={setPhoneNumber}
                placeholder="712 345 678"
              />
              <FormInput
                type="email"
                name="email"
                value={email}
                placeholder="Email"
                label="Email"
                onChange={(e) => setEmail(e.target.value)}
              />
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
                value={password2}
                label="Confirm Password"
                onChange={(e) => setPassword2(e.target.value)}
              />
              <Button
                text={isRegisterPending ? <Spinner /> : "Sign Up"}
                type="submit"
                variant="primary"
                className="w-full"
              />
              {isRegisterPending && (
                <p className="mt-3 text-center text-xs text-slate-500 dark:text-slate-400">
                  Taking longer than expected? Please check your internet and refresh the page, then try again.
                </p>
              )}
            </form>
            <div className="my-6 border-t border-slate-100 dark:border-slate-800" />
            <p className="text-center text-sm text-slate-600 dark:text-slate-400">
              Don't have an account?{" "}
              <Link className="font-medium text-blue-700 hover:underline dark:text-blue-300" to="/login">
                Sign In
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignUp;
