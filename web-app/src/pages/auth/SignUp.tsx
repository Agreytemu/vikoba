import { FC, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import Reveal from "@/components/landing/Reveal";
import LoginSvg from "@/assets/authenticate.svg";
import { SYSTEM_NAME, LOGO_URL } from "@/lib/system";
import FormInput from "@/components/FormInput";
import Button from "@/components/Button";
import Spinner from "@/components/Spinner";
import CountryPhoneInput from "@/components/CountryPhoneInput";
import { useRegister } from "@/hooks/api/auth";
import { getApiErrorMessage } from "@/lib/utils";

function generateStrongPassword(): string {
  const caps = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const lowers = "abcdefghijklmnopqrstuvwxyz";
  const nums = "0123456789";
  const syms = "@#$%&*";
  const pick = (s: string) => s[Math.floor(Math.random() * s.length)];
  let pw = "";
  pw += pick(caps);
  for (let i = 0; i < 4; i++) pw += pick(lowers);
  pw += pick(nums);
  pw += pick(syms) + pick(syms);
  for (let i = 0; i < 3; i++) pw += pick(lowers + nums);
  return pw
    .split("")
    .sort(() => Math.random() - 0.5)
    .join("");
}

function isStrongPassword(pw: string, email: string): { ok: boolean; msg?: string } {
  if (pw.length < 10) return { ok: false, msg: "Password must be at least 10 characters." };
  if (!/[A-Z]/.test(pw)) return { ok: false, msg: "Include at least one capital letter (A-Z)." };
  const lowers = (pw.match(/[a-z]/g) || []).length;
  if (lowers < 3) return { ok: false, msg: "Include at least three lowercase letters." };
  if (!/[0-9]/.test(pw)) return { ok: false, msg: "Include at least one number." };
  const symbols = (pw.match(/[^A-Za-z0-9]/g) || []).length;
  if (symbols < 2) return { ok: false, msg: "Include at least two symbols (e.g. @ # $ % & *)." };
  if (email && pw.toLowerCase().includes(email.toLowerCase().split("@")[0])) {
    return { ok: false, msg: "Password must not contain your email name." };
  }
  if (email && pw.toLowerCase() === email.toLowerCase()) return { ok: false, msg: "Password must not be the same as email." };
  return { ok: true };
}

const SignUp: FC = () => {
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

  const pwCheck = useMemo(() => (password ? isStrongPassword(password, email) : null), [password, email]);
  const showPwGuide = password.length > 0;
  const suggestPassword = () => {
    const s = generateStrongPassword();
    setPassword(s);
    setPassword2(s);
    toast.info(`Suggested password filled. You can copy it: ${s}`, { autoClose: 6000 });
  };

  const handleSignup = (e: React.FormEvent) => {
    e.preventDefault();
    if (!firstName.trim() || !lastName.trim()) {
      toast.error("First and last name are required.", { autoClose: 2500 });
      return;
    }
    if (!phoneNumber || !/^\+255[67]\d{8}$/.test(phoneNumber)) {
      toast.error("Enter a valid Tanzania number (+255 6xx/7xx xxx xxx).", { autoClose: 3000 });
      return;
    }
    const strong = isStrongPassword(password, email);
    if (!strong.ok) {
      toast.error(strong.msg, { autoClose: 3500 });
      return;
    }
    if (password !== password2) {
      toast.error("Passwords do not match", { autoClose: 2500 });
      return;
    }
    register(
      {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        phone_number: phoneNumber,
        email: email.trim(),
        password,
        confirm_password: password2,
      },
      {
        onSuccess: () => {
          toast.success("Account created. Check your inbox for the 6-digit code to verify your email.", { autoClose: 4000 });
          navigate(`/verify-email?email=${encodeURIComponent(email.trim())}`);
        },
        onError: (error) => {
          toast.error(getApiErrorMessage(error, friendlyRegisterFallback), { autoClose: 4000 });
        },
      },
    );
  };

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-[#FDFBF7] px-4 py-6 text-[#1A1A1A] dark:bg-[#0d1117] dark:text-slate-100 sm:py-10">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-[20px] border border-[#E8E2D9] bg-white shadow-[0_8px_30px_rgba(0,0,0,0.06)] dark:border-slate-800 dark:bg-slate-900 lg:grid-cols-2">
        <div className="hidden flex-col justify-between bg-[#115036] p-8 text-white lg:flex lg:p-10">
          <Reveal>
            <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-10 w-10 rounded-xl bg-white/10 p-1" />
            <h1 className="mt-8 font-display text-[32px] font-semibold leading-tight">Create an account</h1>
            <p className="mt-3 max-w-sm text-[13px] leading-6 text-white/80">
              Join your VICOBA in Tanzania. One account for contributions, loans and your group ledger — verified step by step.
            </p>
            <p className="mt-4 text-[11px] uppercase tracking-[0.1em] text-white/60">Tanzania · English · TZS</p>
          </Reveal>
          <Reveal delay={120}>
            <img src={LoginSvg} alt="" className="mt-8 w-56 opacity-90" />
          </Reveal>
        </div>

        <div className="flex flex-col items-center justify-center p-6 sm:p-8 lg:p-10">
          <div className="w-full max-w-sm">
            <Reveal>
              <div className="mb-6 flex flex-col items-center text-center lg:hidden">
                <img src={LOGO_URL} alt={`${SYSTEM_NAME} logo`} className="h-12 w-12 rounded-xl bg-[#115036]/5 p-1" />
                <h3 className="mt-3 font-display text-2xl font-semibold">Create account</h3>
                <p className="mt-1 text-xs text-slate-500">Tanzania · +255 only · English</p>
              </div>
            </Reveal>

            <Reveal delay={80}>
              <form className="space-y-4" onSubmit={handleSignup}>
                <div className="grid grid-cols-2 gap-3">
                  <FormInput type="text" name="firstName" value={firstName} placeholder="First name" label="First name" onChange={(e) => setFirstName(e.target.value)} />
                  <FormInput type="text" name="lastName" value={lastName} placeholder="Last name" label="Last name" onChange={(e) => setLastName(e.target.value)} />
                </div>
                <CountryPhoneInput id="phoneNumber" label="Phone number" value={phoneNumber} onChange={setPhoneNumber} placeholder="712 345 678" />
                <FormInput type="email" name="email" value={email} placeholder="you@example.com" label="Email" onChange={(e) => setEmail(e.target.value)} />
                <div>
                  <div className="flex items-end justify-between gap-2">
                    <div className="flex-1">
                      <FormInput
                        type="password"
                        name="password"
                        placeholder="Strong password"
                        value={password}
                        label="Password"
                        onChange={(e) => setPassword(e.target.value)}
                      />
                    </div>
                    <button
                      type="button"
                      onClick={suggestPassword}
                      className="mb-1 shrink-0 rounded-lg border border-[#E8E2D9] bg-white px-3 py-2 text-xs font-medium text-[#115036] hover:bg-[#FDFBF7]"
                    >
                      Suggest
                    </button>
                  </div>
                  {showPwGuide && (
                    <div className="mt-2 rounded-lg border border-[#F0EBE0] bg-[#FDFBF7] px-3 py-2 dark:border-slate-800 dark:bg-slate-800/50">
                      <p className="text-[11px] font-medium text-[#3D3D3D] dark:text-slate-300">Password must have:</p>
                      <ul className="mt-1 space-y-0.5 text-[11px] leading-4">
                        <li className={password.length >= 10 ? "text-green-700" : "text-slate-500"}>• At least 10 characters</li>
                        <li className={/[A-Z]/.test(password) ? "text-green-700" : "text-slate-500"}>• One capital letter</li>
                        <li className={(password.match(/[a-z]/g) || []).length >= 3 ? "text-green-700" : "text-slate-500"}>• Three lowercase letters</li>
                        <li className={/[0-9]/.test(password) ? "text-green-700" : "text-slate-500"}>• One number</li>
                        <li className={(password.match(/[^A-Za-z0-9]/g) || []).length >= 2 ? "text-green-700" : "text-slate-500"}>• Two symbols (@ # $ % & *)</li>
                        <li className={password && email && password.toLowerCase() === email.toLowerCase() ? "text-red-600" : "text-slate-500"}>• Not same as email</li>
                      </ul>
                    </div>
                  )}
                  {showPwGuide && pwCheck && !pwCheck.ok && password.length > 0 && <p className="mt-1 text-xs text-amber-600">{pwCheck.msg}</p>}
                </div>
                <FormInput
                  type="password"
                  name="confirmPassword"
                  placeholder="Confirm Password"
                  value={password2}
                  label="Confirm Password"
                  onChange={(e) => setPassword2(e.target.value)}
                />
                <Button text={isRegisterPending ? <Spinner /> : "Create account"} type="submit" variant="primary" className="w-full" />
                {isRegisterPending && (
                  <p className="mt-3 text-center text-xs text-slate-500">Taking longer than expected? Check internet and refresh.</p>
                )}
                <p className="text-center text-[11px] text-slate-400">By creating an account you agree to our Terms. Tanzania only.</p>
              </form>
            </Reveal>
            <Reveal delay={160}>
              <div className="my-6 border-t border-slate-100 dark:border-slate-800" />
              <p className="text-center text-sm text-slate-600 dark:text-slate-400">
                Already have an account?{" "}
                <Link className="font-medium text-[#115036] hover:underline" to="/login">
                  Sign In
                </Link>
              </p>
            </Reveal>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignUp;
