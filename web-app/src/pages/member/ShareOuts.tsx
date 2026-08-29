import { FC } from "react";

import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";
import { Badge } from "@/components/ui/badge";
import { useGetMyShareOuts } from "@/hooks/api/shareOuts";

const money = (value: string | number | null | undefined) =>
  new Intl.NumberFormat("en-KE", { style: "currency", currency: "KES", maximumFractionDigits: 0 }).format(Number(value || 0));

const ShareOuts: FC = () => {
  const { data: records, isLoading } = useGetMyShareOuts();

  const totals = (records ?? []).reduce((acc, r) => {
    const base = Number(r.amount) || 0;
    if (!r.is_paid) acc.pending += base;
    return acc;
  }, { pending: 0 });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold">Share-outs</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Your entitlements when a group's cycle ends and profits are shared out.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <p className="text-sm text-slate-500 dark:text-slate-400">Pending share-out</p>
          <p className="mt-1 font-display text-2xl font-semibold">{money(totals.pending)}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <p className="text-sm text-slate-500 dark:text-slate-400">Share-out records</p>
          <p className="mt-1 font-display text-2xl font-semibold">{records?.length ?? "—"}</p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16"><Spinner /></div>
      ) : !records || records.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900">
          <LucideIcon name="Coins" size={40} className="mx-auto text-slate-300 dark:text-slate-600" />
          <h2 className="mt-3 font-display text-lg font-semibold">No share-outs yet</h2>
          <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">
            When a group's cycle ends, staff declare a share-out and your entitlement will appear here.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {records.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-card dark:border-slate-800 dark:bg-slate-900">
              <div>
                <p className="font-medium">
                  {r.group_name}
                  <span className="ml-2 text-xs font-normal text-slate-500">{r.cycle_label}</span>
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Declared {new Date(r.declared_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <p className="font-display font-semibold">{money(r.amount)}</p>
                <Badge className={r.is_paid ? "bg-green-100 text-green-800 dark:bg-green-950/60 dark:text-green-300" : "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"}>
                  {r.is_paid ? "Paid" : "Pending"}
                </Badge>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default ShareOuts;