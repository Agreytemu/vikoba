import { FC, useMemo } from "react";
import { Link } from "react-router-dom";

import { useUserProfileInfo } from "@/hooks/useUserProfile";
import { useGetMyMemberProfile } from "@/hooks/api/memberSelf";
import { SkeletonPage } from "@/components/Skeleton";
import LucideIcon from "@/components/LucideIcon";
import { useGetMyGroups, useGetMyGroupsSummary } from "@/hooks/api/groups";
import { useGetMyAccounts } from "@/hooks/api/myAccounts";
import { useGetMyLoans } from "@/hooks/api/memberLoans";
import { useGetMeetings } from "@/hooks/api/community";
import { useGetMyStatement } from "@/hooks/api/memberWallet";
import { useCurrency } from "@/contexts/CurrencyContext";

const greeting = () => {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
};

const countdownLabel = (startsAt: string) => {
  const start = new Date(startsAt).getTime();
  const diff = start - Date.now();
  if (Number.isNaN(start)) return "";
  if (diff < 0) return "Happening now";
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  if (days > 1) return `in ${days} days`;
  if (days === 1) return "Tomorrow";
  if (hours >= 1) return `in ${hours} hour${hours === 1 ? "" : "s"}`;
  return "Starting soon";
};

const MemberHome: FC = () => {
  useUserProfileInfo();
  const { formatMoney } = useCurrency();
  const { data: profile, isLoading: isProfileLoading } = useGetMyMemberProfile();

  const { data: myAccounts } = useGetMyAccounts();
  const { data: myGroups } = useGetMyGroups();
  const { data: mySummary } = useGetMyGroupsSummary();
  const { data: myLoans } = useGetMyLoans();
  const { data: meetings } = useGetMeetings();

  const firstAccountNumber = myAccounts?.accounts?.[0]?.account_number;
  const { data: statement } = useGetMyStatement(firstAccountNumber);

  const nextMeeting = useMemo(() => {
    const now = Date.now();
    return (meetings ?? [])
      .map((m) => ({ ...m, _t: new Date(m.starts_at).getTime() }))
      .filter((m) => !Number.isNaN(m._t) && m._t >= now - 3600000)
      .sort((a, b) => a._t - b._t)[0];
  }, [meetings]);

  const recentActivity = useMemo(
    () => [...(statement?.transactions ?? [])]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 5),
    [statement],
  );

  if (isProfileLoading) {
    return <SkeletonPage />;
  }

  if (!profile) {
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
        No member profile is linked to this account. Contact support.
      </div>
    );
  }

  const totalBalance = Number(myAccounts?.total_balance || 0);
  const accountCount = myAccounts?.accounts.length ?? 0;
  const groupCount = mySummary?.group_count ?? myGroups?.length ?? 0;
  const hisaCount = mySummary?.total_shares ?? 0;

  return (
    <div className="space-y-5">
      {/* HERO — green brand card with greeting + balance */}
      <div className="overflow-hidden rounded-2xl bg-gradient-to-br from-[#115036] to-[#0b3a26] p-5 text-white shadow-card sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[13px] text-white/70">
              {greeting()}, {profile.first_name || "member"}
            </p>
            <p className="mt-1 font-display text-[32px] font-bold leading-none tracking-tight">
              {formatMoney(totalBalance)}
            </p>
            <p className="mt-2 text-[12px] text-white/70">
              {accountCount} saving account{accountCount === 1 ? "" : "s"} · {groupCount} group{groupCount === 1 ? "" : "s"} · {hisaCount.toLocaleString()} hisa
            </p>
          </div>
          {profile.is_verified ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-[12px] font-medium text-white">
              <LucideIcon name="ShieldCheck" size={15} /> Verified
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-400/20 px-3 py-1 text-[12px] font-medium text-amber-200">
              <LucideIcon name="ShieldAlert" size={15} /> Pending verification
            </span>
          )}
        </div>
        <p className="mt-1 text-[11px] text-white/50">
          Member {profile.membership_number}
        </p>
      </div>

      {!profile.is_verified && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300">
              <LucideIcon name="ShieldAlert" size={18} />
            </span>
            <div>
              <p className="text-sm font-semibold text-amber-800 dark:text-amber-200">
                Finish your verification to unlock loans & withdrawals
              </p>
              <p className="text-xs text-amber-700/80 dark:text-amber-300/80">
                Verify phone, add next of kin and upload ID, passport & signature in your profile.
              </p>
            </div>
          </div>
          <Link
            to="/profile"
            className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-amber-700"
          >
            <LucideIcon name="ArrowRight" size={16} /> Finish verification
          </Link>
        </div>
      )}

      {/* QUICK ACTIONS — M-Pesa style icon tiles */}
      <div className="grid grid-cols-4 gap-3 sm:grid-cols-6">
        {[
          { to: "/deposit", icon: "ArrowDownToLine", label: "Deposit" },
          { to: "/withdraw", icon: "ArrowUpFromLine", label: "Withdraw" },
          { to: "/plan-checkout", icon: "Crown", label: "Plans" },
          { to: "/groups", icon: "Coins", label: "Buy hisa" },
          { to: "/loans-me?apply=1", icon: "HandCoins", label: "Loan" },
          { to: "/wallet", icon: "Wallet", label: "Wallet" },
        ].map((a) => (
          <Link
            key={a.label}
            to={a.to}
            className="group flex flex-col items-center gap-2 rounded-2xl border border-slate-200 bg-white p-3 text-center shadow-card transition hover:border-[#115036]/40 hover:shadow-md sm:p-4 dark:border-slate-800 dark:bg-slate-900"
          >
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#115036]/10 text-[#115036] transition group-hover:bg-[#115036] group-hover:text-white dark:bg-[#115036]/20 dark:text-emerald-300">
              <LucideIcon name={a.icon} size={22} />
            </span>
            <span className="text-[11px] font-medium text-slate-700 sm:text-xs dark:text-slate-200">{a.label}</span>
          </Link>
        ))}
      </div>

      {/* NEXT MEETING */}
      {nextMeeting ? (
        <Link
          to="/community"
          className="flex items-center gap-4 rounded-2xl border border-[#115036]/20 bg-[#EEF6F0] p-4 shadow-card transition hover:shadow-md dark:border-emerald-900 dark:bg-emerald-950/30"
        >
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[#115036] text-white">
            <LucideIcon name="CalendarDays" size={24} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#115036] dark:text-emerald-300">
              Next meeting · {countdownLabel(nextMeeting.starts_at)}
            </p>
            <p className="truncate text-[15px] font-semibold text-slate-900 dark:text-white">{nextMeeting.title}</p>
            <p className="truncate text-[12px] text-slate-500 dark:text-slate-400">
              {new Date(nextMeeting.starts_at).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
              {nextMeeting.location ? ` · ${nextMeeting.location}` : ""}
            </p>
          </div>
          <LucideIcon name="ChevronRight" size={20} className="shrink-0 text-[#115036] dark:text-emerald-300" />
        </Link>
      ) : (
        <Link
          to="/community"
          className="flex items-center gap-4 rounded-2xl border border-dashed border-slate-300 bg-white p-4 transition hover:border-[#115036]/40 dark:border-slate-700 dark:bg-slate-900"
        >
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300">
            <LucideIcon name="CalendarDays" size={24} />
          </span>
          <div className="flex-1">
            <p className="text-[14px] font-semibold text-slate-800 dark:text-slate-100">No upcoming meetings</p>
            <p className="text-[12px] text-slate-500 dark:text-slate-400">Check the community board for announcements →</p>
          </div>
        </Link>
      )}

      {/* MY GROUPS */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-[16px] font-semibold">My groups</h2>
          <Link to="/groups" className="text-[13px] font-medium text-[#115036] hover:underline dark:text-emerald-300">
            View all →
          </Link>
        </div>
        {(myGroups ?? []).length === 0 ? (
          <div className="rounded-xl bg-slate-50 px-4 py-6 text-center dark:bg-slate-800/60">
            <p className="text-[13px] text-slate-500 dark:text-slate-400">You have not joined a group yet.</p>
            <Link to="/groups" className="mt-2 inline-block text-[13px] font-medium text-[#115036] hover:underline dark:text-emerald-300">
              Find your group →
            </Link>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {(myGroups ?? []).slice(0, 4).map((g) => (
              <li key={g.id}>
                <Link to={`/groups/${g.id}`} className="group flex items-center gap-3 py-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#115036]/10 text-[15px] font-bold text-[#115036] dark:bg-[#115036]/20 dark:text-emerald-300">
                    {(g.name || "?").charAt(0).toUpperCase()}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[14px] font-semibold text-slate-900 group-hover:underline dark:text-white">
                      {g.name}
                    </span>
                    <span className="block truncate text-[12px] text-slate-500 dark:text-slate-400">
                      {g.my_shares.toLocaleString()} hisa · {g.member_count} members
                      {g.my_role ? ` · ${g.my_role}` : ""}
                    </span>
                  </span>
                  <LucideIcon name="ChevronRight" size={18} className="shrink-0 text-slate-300 group-hover:text-[#115036] dark:text-slate-600" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* COMPACT STATS */}
      <div className="grid grid-cols-3 gap-3">
        <Link
          to="/groups"
          className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card transition hover:border-[#115036]/40 dark:border-slate-800 dark:bg-slate-900"
        >
          <div className="flex items-center gap-1.5 text-[12px] text-slate-500 dark:text-slate-400">
            <LucideIcon name="Coins" size={15} /> Hisa
          </div>
          <p className="mt-1 font-display text-xl font-semibold">{mySummary ? mySummary.total_shares.toLocaleString() : "—"}</p>
        </Link>
        <Link
          to="/wallet"
          className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card transition hover:border-[#115036]/40 dark:border-slate-800 dark:bg-slate-900"
        >
          <div className="flex items-center gap-1.5 text-[12px] text-slate-500 dark:text-slate-400">
            <LucideIcon name="PiggyBank" size={15} /> Saved
          </div>
          <p className="mt-1 truncate font-display text-xl font-semibold">
            {mySummary ? formatMoney(Number(mySummary.contributed_total || 0)) : "—"}
          </p>
        </Link>
        <Link
          to="/loans-me"
          className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card transition hover:border-[#115036]/40 dark:border-slate-800 dark:bg-slate-900"
        >
          <div className="flex items-center gap-1.5 text-[12px] text-slate-500 dark:text-slate-400">
            <LucideIcon name="HandCoins" size={15} /> Loans
          </div>
          <p className="mt-1 font-display text-xl font-semibold">{myLoans?.length ?? "—"}</p>
        </Link>
      </div>

      {/* RECENT ACTIVITY */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-display text-[16px] font-semibold">Recent activity</h2>
          <Link to="/wallet" className="text-[13px] font-medium text-[#115036] hover:underline dark:text-emerald-300">
            Wallet →
          </Link>
        </div>
        {recentActivity.length === 0 ? (
          <p className="rounded-xl bg-slate-50 px-4 py-6 text-center text-[13px] text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
            No transactions yet. Your deposits and withdrawals will appear here.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {recentActivity.map((tx) => {
              const isOut =
                tx.transaction_type.toLowerCase() === "withdrawal" || Number(tx.debit || 0) > 0;
              return (
                <li key={tx.id} className="flex items-center gap-3 py-2.5">
                  <span
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
                      isOut
                        ? "bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-300"
                        : "bg-[#115036]/10 text-[#115036] dark:bg-[#115036]/20 dark:text-emerald-300"
                    }`}
                  >
                    <LucideIcon name={isOut ? "ArrowUpRight" : "ArrowDownLeft"} size={17} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-medium capitalize text-slate-800 dark:text-slate-100">
                      {tx.transaction_type} · {tx.reference || tx.transaction_number}
                    </span>
                    <span className="block text-[11px] text-slate-400">
                      {new Date(tx.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}
                    </span>
                  </span>
                  <span className={`text-[13px] font-semibold ${isOut ? "text-red-600 dark:text-red-300" : "text-[#115036] dark:text-emerald-300"}`}>
                    {isOut ? "−" : "+"}
                    {formatMoney(Number(tx.amount || 0))}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
};

export default MemberHome;
