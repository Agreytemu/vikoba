import { FC } from "react";

import LucideIcon from "@/components/LucideIcon";

/**
 * Black animated verification icon shown once a payout/deposit is done.
 *
 * The user wants the "verification" badge in pure black: the outer line first
 * traces a full circle (0.9s), then the tick is drawn (0.45s), then a soft
 * black glow settles behind the new badge. This is purely presentational — it
 * appears only after the confirmed webhook lands, never before.
 */
const SuccessCheckmark: FC = () => (
  <div className="flex flex-col items-center">
    <svg
      viewBox="0 0 72 72"
      width="76"
      height="76"
      fill="none"
      aria-hidden="true"
      className="verification-svg text-ink dark:text-white"
    >
      <circle
        className="verification-circle"
        cx="36"
        cy="36"
        r="33"
        stroke="currentColor"
      />
      <path
        className="verification-tick"
        d="M25 37 L34 46 L50 28"
        stroke="currentColor"
      />
      <circle className="verification-glow" cx="36" cy="36" r="33" fill="currentColor" />
    </svg>
    <p className="mt-3 flex items-center gap-1.5 text-sm font-medium text-ink dark:text-white">
      <LucideIcon name="Sparkles" size={14} />
      Successfully
    </p>
  </div>
);

export default SuccessCheckmark;
