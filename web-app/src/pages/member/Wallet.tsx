import { FC, useState } from "react";
import { toast } from "react-toastify";

import Button from "@/components/Button";
import FormInput from "@/components/FormInput";
import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";
import Modal from "@/components/ui/Modal";
import { Badge } from "@/components/ui/badge";
import VerificationGate from "@/components/VerificationGate";
import { useGetMyAccounts } from "@/hooks/api/myAccounts";
import { useGetMyMemberProfile } from "@/hooks/api/memberSelf";
import {
  useCreateDeposit,
  useCreateWithdrawal,
  useGetMyDeposits,
  useGetMyStatement,
  useGetMyWithdrawals,
} from "@/hooks/api/memberWallet";
import { useUserProfileInfo } from "@/hooks/useUserProfile";
import { useCurrency } from "@/contexts/CurrencyContext";
import { getApiErrorMessage } from "@/lib/utils";

const REQUEST_STATUS_STYLES: Record<string, string> = {
  PENDING: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-transparent",
  APPROVED: "bg-green-100 text-green-800 dark:bg-green-950/60 dark:text-green-300 border-transparent",
  DECLINED: "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 border-transparent",
};

const Wallet: FC = () => {
  const { profile } = useUserProfileInfo();
  const { formatMoney } = useCurrency();
  const isMember = profile?.role === "ME";
  const { data: me } = useGetMyMemberProfile(isMember);
  const isVerified = isMember ? Boolean(me?.is_verified) : false;

  const { data: accounts } = useGetMyAccounts();
  const { data: deposits } = useGetMyDeposits(isMember);
  const { data: withdrawals } = useGetMyWithdrawals(isMember);
  const [selectedAccount, setSelectedAccount] = useState<string | null>(null);
  const { data: statement } = useGetMyStatement(selectedAccount ?? undefined);

  const [depositOpen, setDepositOpen] = useState(false);
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [withdrawGateOpen, setWithdrawGateOpen] = useState(false);

  if (!isMember) {
    return <p className="text-slate-500">This page is for members.</p>;
  }

  const showWithdraw = () => {
    if (!isVerified) {
      setWithdrawGateOpen(true);
      return;
    }
    setWithdrawOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold">My wallet</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Deposit money, view statements and request withdrawals.
          </p>
        </div>
        <div className="flex gap-2">
          <Button text="Deposit" onClick={() => setDepositOpen(true)} />
          <Button text="Withdraw" variant="secondary" onClick={showWithdraw} />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <p className="text-sm text-slate-500 dark:text-slate-400">Total deposits</p>
          <p className="mt-1 font-display text-xl font-semibold">{formatMoney(Number(accounts?.total_balance || 0))}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <p className="text-sm text-slate-500 dark:text-slate-400">Pending deposits</p>
          <p className="mt-1 font-display text-xl font-semibold">{(deposits ?? []).filter((d) => d.status === "PENDING").length}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <p className="text-sm text-slate-500 dark:text-slate-400">Pending withdrawals</p>
          <p className="mt-1 font-display text-xl font-semibold">{(withdrawals ?? []).filter((w) => w.status === "PENDING").length}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <p className="text-sm text-slate-500 dark:text-slate-400">Savings accounts</p>
          <p className="mt-1 font-display text-xl font-semibold">{accounts?.accounts.length ?? "—"}</p>
        </div>
      </div>

      {!isVerified && (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/30 dark:text-amber-200">
          <LucideIcon name="Info" size={18} className="mt-0.5 shrink-0" />
          <p>
            You can deposit and check your savings today. Withdrawals require a
            verified account — finish your verification and staff approval to unlock them.
          </p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <h2 className="mb-3 font-display text-lg font-semibold">Savings accounts</h2>
          {!accounts || accounts.accounts.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500 dark:text-slate-400">
              No savings account yet. Ask staff to open one for you.
            </p>
          ) : (
            <div className="space-y-2">
              {accounts.accounts.map((account) => (
                <button
                  key={account.id}
                  type="button"
                  onClick={() => setSelectedAccount(account.account_number)}
                  className={`flex w-full items-center justify-between gap-3 rounded-xl border px-4 py-3 text-left transition ${
                    selectedAccount === account.account_number
                      ? "border-blue-300 bg-blue-50 dark:border-blue-700 dark:bg-blue-950/40"
                      : "border-slate-200 hover:border-blue-200 dark:border-slate-800 dark:hover:border-blue-900"
                  }`}
                >
                  <div>
                    <p className="text-sm font-medium">{account.product_name}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{account.account_number}</p>
                  </div>
                  <p className="font-display font-semibold">{formatMoney(Number(account.balance || 0))}</p>
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <h2 className="mb-3 font-display text-lg font-semibold">Mini statement</h2>
          {!selectedAccount ? (
            <p className="py-6 text-center text-sm text-slate-500 dark:text-slate-400">
              Select an account to see its recent transactions.
            </p>
          ) : statement && statement.transactions.length > 0 ? (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {statement.transactions.slice(0, 10).map((txn) => (
                <li key={txn.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{txn.transaction_type.replace(/_/g, " ")}</p>
                    <p className="truncate text-xs text-slate-500 dark:text-slate-400">{txn.reference}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-medium text-emerald-700 dark:text-emerald-400">{formatMoney(Number(txn.credit ?? txn.amount))}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{new Date(txn.created_at).toLocaleDateString()}</p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-slate-500 dark:text-slate-400">
              {selectedAccount ? "No transactions yet on this account." : "Select an account to see its recent transactions."}
            </p>
          )}
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <h2 className="font-display text-lg font-semibold">Deposit requests</h2>
          <RequestList
            items={(deposits ?? []).map((d) => ({
              id: `d-${d.id}`,
              title: `${d.product_name} · ${d.channel || ""}`,
              meta: d.reference,
              amount: d.amount,
              status: d.status,
              status_display: d.status_display,
              created_at: d.requested_at,
            }))}
            formatMoney={formatMoney}
          />
        </div>
        <div className="space-y-3">
          <h2 className="font-display text-lg font-semibold">Withdrawal requests</h2>
          <RequestList
            items={(withdrawals ?? []).map((w) => ({
              id: `w-${w.id}`,
              title: w.product_name,
              meta: w.reference,
              amount: w.amount,
              status: w.status,
              status_display: w.status_display,
              created_at: w.requested_at,
            }))}
            formatMoney={formatMoney}
          />
        </div>
      </div>

      <DepositModal
        isOpen={depositOpen}
        onClose={() => setDepositOpen(false)}
        accounts={accounts?.accounts ?? []}
      />
      <WithdrawalModal
        isOpen={withdrawOpen}
        onClose={() => setWithdrawOpen(false)}
        accounts={accounts?.accounts ?? []}
      />
      <VerificationGate
        open={withdrawGateOpen}
        onClose={() => setWithdrawGateOpen(false)}
        message="Finish your verification before you can withdraw: confirm your phone, add a next of kin, upload your ID, passport photo and signature, then staff approve them."
      />
    </div>
  );
};

const RequestList = ({ items, formatMoney }: {
  items: { id: string; title: string; meta: string; amount: string; status: string; status_display: string; created_at: string }[];
  formatMoney: (value: number) => string;
}) => {
  if (items.length === 0) {
    return <p className="rounded-2xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500 dark:border-slate-700">Nothing here yet.</p>;
  }
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 dark:border-slate-800 dark:bg-slate-900">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{item.title}</p>
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">
              {item.meta} · {new Date(item.created_at).toLocaleDateString()}
            </p>
          </div>
          <div className="flex items-center gap-3 text-right">
            <p className="font-display font-semibold">{formatMoney(Number(item.amount))}</p>
            <Badge className={REQUEST_STATUS_STYLES[item.status] ?? ""}>{item.status_display}</Badge>
          </div>
        </li>
      ))}
    </ul>
  );
};

const DepositModal = ({ isOpen, onClose, accounts }: {
  isOpen: boolean;
  onClose: () => void;
  accounts: { account_number: string; product_name: string }[];
}) => {
  const createDeposit = useCreateDeposit();
  const [form, setForm] = useState({ account_number: "", amount: "", channel: "mpesa", transaction_code: "" });

  if (!isOpen) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.account_number) return toast.error("Choose the account to deposit into.");
    if (!form.amount || Number(form.amount) <= 0) return toast.error("Enter the amount to deposit.");
    try {
      await createDeposit.mutateAsync({
        account_number: form.account_number,
        amount: form.amount,
        channel: form.channel,
        transaction_code: form.transaction_code || undefined,
      });
      toast.success("Deposit request submitted. Staff will confirm and credit your account.", { autoClose: 4000 });
      setForm({ account_number: "", amount: "", channel: "mpesa", transaction_code: "" });
      onClose();
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Could not submit the deposit."));
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Deposit money">
      <form className="space-y-4" onSubmit={submit}>
        <div>
          <label className="mb-1 block text-sm font-medium">Account</label>
          <select
            value={form.account_number}
            onChange={(e) => setForm({ ...form, account_number: e.target.value })}
            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            required
          >
            <option value="">Select account…</option>
            {accounts.map((a) => (
              <option key={a.account_number} value={a.account_number}>{a.product_name} · {a.account_number}</option>
            ))}
          </select>
        </div>
        <FormInput type="number" label="Amount" name="amount" placeholder="e.g. 5,000" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
        <div>
          <label className="mb-1 block text-sm font-medium">Channel</label>
          <select
            value={form.channel}
            onChange={(e) => setForm({ ...form, channel: e.target.value })}
            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="mpesa">M-Pesa</option>
            <option value="cash">Cash</option>
            <option value="bank">Bank transfer</option>
          </select>
        </div>
        <FormInput type="text" label="Transaction code (optional)" name="txn_code" placeholder="e.g. SFXXXXXX" value={form.transaction_code} onChange={(e) => setForm({ ...form, transaction_code: e.target.value })} />
        <div className="flex justify-end gap-2 pt-1">
          <Button text="Cancel" onClick={onClose} />
          <Button text={createDeposit.isPending ? <Spinner /> : "Submit deposit"} type="submit" variant="primary" disabled={createDeposit.isPending} />
        </div>
      </form>
    </Modal>
  );
};

const WithdrawalModal = ({ isOpen, onClose, accounts }: {
  isOpen: boolean;
  onClose: () => void;
  accounts: { account_number: string; product_name: string }[];
}) => {
  const createWithdrawal = useCreateWithdrawal();
  const [form, setForm] = useState({ account_number: "", amount: "", narration: "" });

  if (!isOpen) return null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.account_number) return toast.error("Choose the account to withdraw from.");
    if (!form.amount || Number(form.amount) <= 0) return toast.error("Enter the amount to withdraw.");
    try {
      await createWithdrawal.mutateAsync({
        account_number: form.account_number,
        amount: form.amount,
        narration: form.narration || undefined,
      });
      toast.success("Withdrawal request submitted. Staff will review and process it.", { autoClose: 4000 });
      setForm({ account_number: "", amount: "", narration: "" });
      onClose();
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Could not submit the withdrawal."));
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Request a withdrawal">
      <form className="space-y-4" onSubmit={submit}>
        <div>
          <label className="mb-1 block text-sm font-medium">Account</label>
          <select
            value={form.account_number}
            onChange={(e) => setForm({ ...form, account_number: e.target.value })}
            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            required
          >
            <option value="">Select account…</option>
            {accounts.map((a) => (
              <option key={a.account_number} value={a.account_number}>{a.product_name} · {a.account_number}</option>
            ))}
          </select>
        </div>
        <FormInput type="number" label="Amount" name="amount" placeholder="e.g. 10,000" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
        <FormInput type="text" label="Note (optional)" name="narration" placeholder="Reason for withdrawal" value={form.narration} onChange={(e) => setForm({ ...form, narration: e.target.value })} />
        <div className="flex justify-end gap-2 pt-1">
          <Button text="Cancel" onClick={onClose} />
          <Button text={createWithdrawal.isPending ? <Spinner /> : "Submit request"} type="submit" variant="primary" disabled={createWithdrawal.isPending} />
        </div>
      </form>
    </Modal>
  );
};

export default Wallet;