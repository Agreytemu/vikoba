import { FC } from "react";

interface MobileMoneyNumberInputProps {
  id?: string;
  value: string;
  error: string | null;
  onChange: (raw: string) => void;
}

/**
 * The mobile-money number that will approve this deposit. It is the member's
 * own number by default but is fully editable — the USSD push goes to this
 * number and the operator is resolved from it.
 */
const MobileMoneyNumberInput: FC<MobileMoneyNumberInputProps> = ({
  id = "deposit-phone",
  value,
  error,
  onChange,
}) => {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={id} className="block text-sm font-medium text-slate-900 dark:text-white">
          Mobile money number
        </label>
        <span className="inline-flex items-center gap-1 text-[11px] text-slate-400">
          +255 · Tanzania
        </span>
      </div>

      <div className="relative mt-2">
        <span
          className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-sm font-semibold text-slate-500 dark:text-slate-400"
          aria-hidden
        >
          +255
        </span>
        <input
          id={id}
          name="deposit-phone"
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="712 345 678"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : hintId}
          className={`h-12 w-full rounded-xl border bg-white pl-14 pr-4 text-[16px] text-slate-900 outline-none transition placeholder:text-slate-300 focus:ring-2 dark:bg-slate-950 dark:text-white dark:placeholder:text-slate-600 ${
            error
              ? "border-red-300 focus:border-red-400 focus:ring-red-100 dark:border-red-800 dark:focus:ring-red-950"
              : "border-slate-200 focus:border-[#115036] focus:ring-[#115036]/15 dark:border-slate-700 dark:focus:ring-emerald-500/20"
          }`}
        />
      </div>

      {error ? (
        <p id={errorId} role="alert" className="mt-2 flex items-center gap-1.5 text-[12px] font-medium text-red-600 dark:text-red-400">
          <span aria-hidden>!</span> {error}
        </p>
      ) : (
        <p id={hintId} className="mt-2 text-[11px] text-slate-400">
          Enter the mobile-money number that will approve this deposit — the push is sent here.
        </p>
      )}
    </section>
  );
};

export default MobileMoneyNumberInput;