import { FC, useRef } from "react";

interface OtpInputProps {
  value: string;
  onChange: (value: string) => void;
  length?: number;
  autoFocus?: boolean;
  autoComplete?: "one-time-code" | "off";
}

/**
 * Phone-style split code entry: one real (invisible) input with
 * `autocomplete="one-time-code"` so iOS/Android propose the emailed/SMS code,
 * with large native-looking boxes drawn under it. Pasting a full code works;
 * tapping any box focuses the hidden input.
 */
const OtpInput: FC<OtpInputProps> = ({
  value,
  onChange,
  length = 6,
  autoFocus = false,
  autoComplete = "one-time-code",
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const digits = value.replace(/\D/g, "").slice(0, length);
  const boxes = Array.from({ length }, (_, i) => digits[i] ?? "");

  return (
    <div
      className="relative flex flex-wrap justify-center gap-2 sm:gap-3"
      onClick={() => inputRef.current?.focus()}
    >
      <input
        ref={inputRef}
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        autoComplete={autoComplete}
        maxLength={length}
        value={digits}
        autoFocus={autoFocus}
        onChange={(e) =>
          onChange(e.target.value.replace(/\D/g, "").slice(0, length))
        }
        className="absolute inset-0 h-full w-full cursor-text opacity-0 focus:outline-none"
        aria-label={`${length}-digit code`}
      />
      {boxes.map((digit, i) => {
        const isActive = i === digits.length;
        return (
          <div
            key={i}
            className={`flex h-14 w-11 items-center justify-center rounded-xl border-2 bg-white font-display text-2xl font-semibold transition dark:bg-slate-900 sm:w-12 ${
              digit
                ? "border-slate-300 text-ink dark:border-slate-600 dark:text-slate-100"
                : "border-slate-200 text-slate-300 dark:border-slate-700 dark:text-slate-600"
            } ${
              isActive
                ? "border-blue-600 shadow-[0_0_0_3px_rgba(59,130,246,0.15)]"
                : ""
            }`}
          >
            {digit || "•"}
          </div>
        );
      })}
    </div>
  );
};

export default OtpInput;