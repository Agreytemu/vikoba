import { FC, useEffect } from "react";
import { Link } from "react-router-dom";

import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";
import { Badge } from "@/components/ui/badge";
import {
  useGetMyNotifications,
  useMarkNotificationsRead,
} from "@/hooks/api/notifications";

const KIND_ICONS: Record<string, string> = {
  deposit: "PiggyBank",
  withdrawal: "Wallet",
  loan: "HandCoins",
  group: "Boxes",
  share_out: "Coins",
  meeting: "Calendar",
  announcement: "Megaphone",
  info: "Info",
};

const Notifications: FC = () => {
  const { data: notifications, isLoading } = useGetMyNotifications();
  const markRead = useMarkNotificationsRead();

  useEffect(() => {
    if (notifications && notifications.some((n) => !n.read)) {
      markRead.mutate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notifications?.some((n) => !n.read)]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold">Notifications</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Important updates about your savings, loans, groups and the cooperative.
        </p>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16"><Spinner /></div>
      ) : !notifications || notifications.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900">
          <LucideIcon name="BellOff" size={40} className="mx-auto text-slate-300 dark:text-slate-600" />
          <h2 className="mt-3 font-display text-lg font-semibold">No notifications yet</h2>
          <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">
            You'll be notified when staff process your deposits, withdrawals and loans, or when new share-outs and meetings are announced.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {notifications.map((n) => (
            <li key={n.id}>
              <Link
                to={n.link || "#"}
                onClick={(e) => { if (!n.link) e.preventDefault(); }}
                className={`flex items-start gap-3 rounded-2xl border px-4 py-3 shadow-card transition ${
                  n.read
                    ? "border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900"
                    : "border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950/40"
                }`}
              >
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  <LucideIcon name={KIND_ICONS[n.kind] ?? "Bell"} size={18} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold">{n.title}</p>
                    <Badge className={n.read ? "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400" : "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300"}>
                      {n.read ? "Read" : "New"}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">{n.body}</p>
                  <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                    {new Date(n.created_at).toLocaleString()}
                  </p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default Notifications;