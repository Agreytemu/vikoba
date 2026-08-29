import { FC, useEffect, useMemo, useRef, useState } from "react";
import LucideIcon from "@/components/LucideIcon";
import { COUNTRIES, Country, detectCountry, flagEmoji, splitPhone } from "@/lib/countries";

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
 * Phone entry with a searchable country/dial-code picker. The number is always
 * stored as full E.164 ("+254712345678"); the dial code and national part are
 * edited separately. The country list is searchable by name OR by dial code,
 * and defaults to the visitor's locale ("from their location").
 */
const CountryPhoneInput: FC<Props> = ({
  value,
  onChange,
  id,
  label,
  disabled,
  placeholder,
  className,
}) => {
  // Seed dial + national part once from the incoming value.
  const initial = useMemo(() => splitPhone(value), []); // eslint-disable-line react-hooks/exhaustive-deps
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState<Country>(() => {
    const found = COUNTRIES.find((c) => c[2] === initial.dial);
    return found
      ? { name: found[0], iso2: found[1], dial: found[2] }
      : detectCountry();
  });
  const [national, setNational] = useState(initial.national);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return COUNTRIES;
    const digits = q.replace(/\D/g, "");
    return COUNTRIES.filter(
      (c) => c[0].toLowerCase().includes(q) || (digits && c[2].startsWith(digits)),
    );
  }, [query]);

  const selectCountry = (c: Country) => {
    setCountry(c);
    setOpen(false);
    setQuery("");
    onChange(`+${c.dial}${national}`);
  };

  const onNationalChange = (raw: string) => {
    const digits = raw.replace(/\D/g, "");
    setNational(digits);
    onChange(`+${country.dial}${digits}`);
  };

  return (
    <div className={className}>
      {label && (
        <label htmlFor={id} className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">
          {label}
        </label>
      )}
      <div ref={wrapRef} className="relative">
        <div className="flex overflow-hidden rounded-xl border border-slate-300 bg-white focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-900">
          <button
            type="button"
            disabled={disabled}
            onClick={() => setOpen((o) => !o)}
            className="flex shrink-0 items-center gap-1.5 border-r border-slate-300 bg-slate-50 px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
          >
            <span className="text-base leading-none">{flagEmoji(country.iso2)}</span>
            <span>+{country.dial}</span>
            <LucideIcon name="ChevronDown" size={14} />
          </button>
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

        {open && (
          <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
            <div className="border-b border-slate-100 p-2 dark:border-slate-800">
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search country or dial code…"
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              />
            </div>
            <ul className="max-h-60 overflow-auto py-1">
              {filtered.length === 0 && (
                <li className="px-3 py-2 text-sm text-slate-400">No country found</li>
              )}
              {filtered.map((c) => (
                <li key={c[1]}>
                  <button
                    type="button"
                    onClick={() => selectCountry({ name: c[0], iso2: c[1], dial: c[2] })}
                    className="flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm transition hover:bg-blue-50 dark:hover:bg-slate-800"
                  >
                    <span className="text-base leading-none">{flagEmoji(c[1])}</span>
                    <span className="flex-1 text-slate-700 dark:text-slate-200">{c[0]}</span>
                    <span className="font-mono text-xs text-slate-400">+{c[2]}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default CountryPhoneInput;
