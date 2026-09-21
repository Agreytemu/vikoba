import { FC } from "react";

import FormInput from "@/components/FormInput";
import LucideIcon from "@/components/LucideIcon";

export interface CustomerDetails {
  fullName: string;
  email: string;
  phone: string;
}

export type CustomerFieldErrors = Partial<Record<keyof CustomerDetails, string>>;

interface CustomerPaymentFormProps {
  value: CustomerDetails;
  errors: CustomerFieldErrors;
  maxLengths?: { phone?: number };
  onChange: (field: keyof CustomerDetails, value: string) => void;
  onBlur?: (field: keyof CustomerDetails) => void;
}

/**
 * Full Name / Email / Mobile Money Number. The number shows a +255 prefix and
 * validates against Tanzanian operator prefixes with inline errors.
 */
const CustomerPaymentForm: FC<CustomerPaymentFormProps> = ({ value, errors, onChange, onBlur, maxLengths }) => {
  return (
    <div>
      <h2 className="font-display text-[16px] font-semibold">Customer details</h2>
      <p className="mt-0.5 text-[12px] text-slate-500 dark:text-slate-400">
        Used for the payment receipt sent to your phone.
      </p>

      <div className="mt-3 space-y-4">
        <div>
          <FormInput
            type="text"
            name="full_name"
            label="Full name"
            placeholder="e.g. Neema Joseph"
            autoComplete="name"
            value={value.fullName}
            onChange={(e) => onChange("fullName", e.target.value)}
          />
          {errors.fullName && <p className="mt-1 text-[11px] text-red-600 dark:text-red-400">{errors.fullName}</p>}
        </div>

        <div>
          <FormInput
            type="email"
            name="email"
            label="Email address"
            placeholder="e.g. neema@example.com"
            inputMode="email"
            autoComplete="email"
            value={value.email}
            onChange={(e) => onChange("email", e.target.value)}
          />
          {errors.email && <p className="mt-1 text-[11px] text-red-600 dark:text-red-400">{errors.email}</p>}
        </div>

        <div>
          <div className="mb-1 flex items-center justify-between">
            <label htmlFor="phone" className="block text-sm font-medium">
              Mobile money number
            </label>
            <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
              <LucideIcon name="ShieldCheck" size={13} /> via Snippe
            </span>
          </div>
          <div
            className={`flex items-stretch overflow-hidden rounded-md border bg-white transition dark:bg-slate-900 ${
              errors.phone
                ? "border-red-400 dark:border-red-500"
                : "border-gray-300 focus-within:border-[#115036] dark:border-slate-600"
            }`}
          >
            <span className="flex items-center gap-1 border-r border-gray-200 bg-slate-50 px-3 text-sm font-medium text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
              +255
            </span>
            <input
              id="phone"
              name="phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel-national"
              placeholder="712 345 678"
              value={value.phone}
              onChange={(e) => onChange("phone", e.target.value.replace(/\D/g, "").slice(0, maxLengths?.phone ?? 9))}
              onBlur={() => onBlur?.("phone")}
              className="w-full px-4 py-2 text-sm outline-none placeholder:text-slate-400"
            />
          </div>
          {errors.phone ? (
            <p className="mt-1 text-[11px] text-red-600 dark:text-red-400">{errors.phone}</p>
          ) : (
            <p className="mt-1 text-[11px] text-slate-400">
              A mobile money push will be sent here — approve it with your PIN.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default CustomerPaymentForm;