import { FC } from "react";

import LucideIcon from "@/components/LucideIcon";
import { maskPhone } from "@/lib/payments";

interface WithdrawRecipientProps {
  phone: string;
  verified?: boolean;
}

/**
 * The payout destination. Showcased as the member's VERIFIED mobile money
 * number — fixed on the server, so this is display-only (no input).
 */
const WithdrawRecipient: FC<WithdrawRecipientProps> = ({ phone, verified = true }) => (
  <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">
      To your mobile money
    </p>
    <div className="mt-2 flex items-center gap-3">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#115036]/10 text-[#115036] dark:bg-emerald-950/50 dark:text-emerald-300">
        <LucideIcon name="ShieldCheck" size={19} />
      </span>
      <span className="min-w-0">
        <span className="block truncate font-display text-[16px] font-semibold text-slate-900 dark:text-white">
          {phone ? maskPhone(phone) : "—"}
        </span>
        <span className="block text-[12px] text-slate-500 dark:text-slate-400">
          {verified ? "Verified number on your profile" : "Phone number"}
        </span>
      </span>
      {verified && (
        <span className="ml-auto shrink-0 rounded-full bg-[#115036]/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-[#115036] dark:bg-emerald-950/50 dark:text-emerald-300">
          Verified
        </span>
      )}
    </div>
    <p className="mt-3 flex items-start gap-1.5 text-[11px] text-slate-400">
      <LucideIcon name="Lock" size={12} className="mt-0.5 shrink-0" />
      Withdrawals only ever go to this number — it can&apos;t be changed here.
    </p>
  </section>
);

export default WithdrawRecipient;