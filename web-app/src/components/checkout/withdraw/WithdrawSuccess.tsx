import { FC } from "react";

import Button from "@/components/Button";
import SuccessCheckmark from "@/components/checkout/SuccessCheckmark";
import { maskPhone } from "@/lib/payments";
import { formatDepositMoney } from "../deposit/depositFlow";

interface WithdrawSuccessProps {
  amount: string;
  phone: string;
  reference: string;
  onViewWallet: () => void;
  onDone: () => void;
}

/** Shown only after the verified payout webhook confirms the money was sent. */
const WithdrawSuccess: FC<WithdrawSuccessProps> = ({
  amount,
  phone,
  reference,
  onViewWallet,
  onDone,
}) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-card dark:border-slate-800 dark:bg-slate-900">
    <SuccessCheckmark />

    <h1 className="mt-3 font-display text-2xl font-semibold">Withdrawal sent</h1>
    <p className="mx-auto mt-2 max-w-sm text-sm text-slate-500 dark:text-slate-400">
      {formatDepositMoney(amount)} was sent to your verified mobile money number{" "}
      <strong className="text-slate-900 dark:text-white">{maskPhone(phone)}</strong>.
    </p>

    {reference ? (
      <p className="mt-4 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
        Transaction ID · {reference}
      </p>
    ) : null}

    <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
      <Button text="View wallet" onClick={onViewWallet} variant="secondary" />
      <Button text="Done" onClick={onDone} variant="primary" />
    </div>
  </div>
);

export default WithdrawSuccess;