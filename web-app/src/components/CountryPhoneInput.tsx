import { FC, useMemo, useState } from "react";
import { flagEmoji, splitPhone } from "@/lib/countries";

interface Props {
  value: string;
  onChange: (value: string) => void;
  id?: string;
  label?: string;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

/**
 * Tanzania-only phone input. Locked to +255.
 * Stores full E.164 (+255XXXXXXXXX). Validates Tanzanian mobile format.
 */
const CountryPhoneInput: FC<Props> = ({ value, onChange, id, label, disabled, placeholder, className }) => {
  const initial = useMemo(() => splitPhone(value), []); // eslint-disable-line react-hooks/exhaustive-deps
  // Tanzania-only: COUNTRIES[0] is TZ 255
  const [national, setNational] = useState(initial.national);

  const onNationalChange = (raw: string) => {
    const digits = raw.replace(/\D/g, "").slice(0, 9);
    setNational(digits);
    onChange(`+255${digits}`);
  };

  const isValidTz = national.length === 9 && /^(6|7)\d{8}$/.test(national);

  return (
    <div className={className}>
      {label && (
        <label htmlFor={id} className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">
          {label} <span className="text-slate-400">(Tanzania +255)</span>
        </label>
      )}
      <div className="flex overflow-hidden rounded-xl border border-slate-300 bg-white focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-900">
        <span className="flex shrink-0 items-center gap-1.5 border-r border-slate-300 bg-slate-50 px-3 text-sm font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
          <span className="text-base leading-none">{flagEmoji("TZ")}</span>
          <span>+255</span>
        </span>
        <input
          id={id}
          type="tel"
          inputMode="numeric"
          disabled={disabled}
          value={national}
          placeholder={placeholder ?? "712 345 678"}
          onChange={(e) => onNationalChange(e.target.value)}
          className="min-w-0 flex-1 bg-transparent px-3 py-2.5 text-sm outline-none placeholder:text-slate-400 dark:text-slate-100"
        />
      </div>
      {national.length > 0 && !isValidTz && (
        <p className="mt-1 text-xs text-amber-600">Enter 9 digits starting with 6 or 7 (e.g. 712 345 678)</p>
      )}
      <p className="mt-1 text-[11px] text-slate-400">Tanzania numbers only. Example: +255 712 345 678</p>
    </div>
  );
};

export default CountryPhoneInput;
