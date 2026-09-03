import { FC, useEffect, useState } from "react";
import { toast } from "react-toastify";

import { useUserProfileInfo } from "@/hooks/useUserProfile";
import {
  useGetMyMemberProfile,
  useUpdateMyProfile,
} from "@/hooks/api/memberSelf";
import Button from "@/components/Button";
import FormInput from "@/components/FormInput";
import Spinner from "@/components/Spinner";
import { SkeletonCard, SkeletonPage } from "@/components/Skeleton";
import LucideIcon from "@/components/LucideIcon";
import { getApiErrorMessage } from "@/lib/utils";
import { useGetMyGroups, useGetMyGroupsSummary } from "@/hooks/api/groups";
import { useGetMyAccounts } from "@/hooks/api/myAccounts";
import { useGetMyLoans } from "@/hooks/api/memberLoans";
import { Link } from "react-router-dom";
import { useCurrency } from "@/contexts/CurrencyContext";

const MemberHome: FC = () => {
  useUserProfileInfo();
  const { formatMoney } = useCurrency();
  const { data: profile, isLoading: isProfileLoading } = useGetMyMemberProfile();
  const updateProfile = useUpdateMyProfile();

  const { data: myAccounts } = useGetMyAccounts();
  const { data: myGroups } = useGetMyGroups();
  const { data: mySummary } = useGetMyGroupsSummary();
  const { data: myLoans } = useGetMyLoans();

  const [editable, setEditable] = useState({
    first_name: "",
    last_name: "",
    country: "",
    county: "",
    city: "",
    date_of_birth: "",
  });

  const isLoading = isProfileLoading;

  const syncEditable = () => {
    if (!profile) return;
    setEditable({
      first_name: profile.first_name,
      last_name: profile.last_name,
      country: profile.country || "",
      county: profile.county || "",
      city: profile.city || "",
      date_of_birth: profile.date_of_birth || "",
    });
  };

  useEffect(() => {
    syncEditable();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile]);

  const handleSaveProfile = () => {
    updateProfile.mutate(
      {
        first_name: editable.first_name || undefined,
        last_name: editable.last_name || undefined,
        country: editable.country || undefined,
        county: editable.county || undefined,
        city: editable.city || undefined,
        date_of_birth: editable.date_of_birth || undefined,
      },
      {
        onSuccess: () => toast.success("Profile updated.", { autoClose: 2000 }),
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Could not update profile"), {
            autoClose: 3000,
          }),
      },
    );
  };

  if (isLoading) {
    return <SkeletonPage />;
  }

  if (!profile) {
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
        No member profile is linked to this account. Contact support.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold">
            {profile.first_name} {profile.last_name}
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Member {profile.membership_number} · {profile.email}
          </p>
        </div>
        {profile.is_verified ? (
          <span className="inline-flex items-center gap-2 rounded-full border border-green-200 bg-green-50 px-4 py-1.5 text-sm font-medium text-green-700 dark:border-green-900 dark:bg-green-950/40 dark:text-green-300">
            <LucideIcon name="ShieldCheck" size={18} /> Verified member
          </span>
        ) : (
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-4 py-1.5 text-sm font-medium text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
            <LucideIcon name="ShieldAlert" size={18} /> Pending verification
          </span>
        )}
      </div>

      {!profile.is_verified && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30 flex flex-wrap items-center justify-between gap-3">
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
            className="inline-flex items-center gap-2 rounded-xl bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 transition"
          >
            <LucideIcon name="ArrowRight" size={16} /> Finish verification
          </Link>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <LucideIcon name="Wallet" size={18} /> Totals balance
          </div>
          <p className="mt-2 font-display text-2xl font-semibold">
            {formatMoney(Number(myAccounts?.total_balance || 0))}
          </p>
          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
            {myAccounts?.accounts.length
              ? `${myAccounts.accounts.length} saving account${myAccounts.accounts.length === 1 ? "" : "s"}`
              : "No savings account yet"}
          </p>
        </div>
        <Link
          to="/groups"
          className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-card transition hover:border-blue-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-blue-700"
        >
          <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <LucideIcon name="Boxes" size={18} /> My groups
          </div>
          <p className="mt-2 font-display text-2xl font-semibold">{myGroups?.length ?? "—"}</p>
          <p className="mt-1 text-xs font-medium text-blue-600 group-hover:underline dark:text-blue-400">
            Open groups →
          </p>
        </Link>
        <Link
          to="/loans-me"
          className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-card transition hover:border-blue-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-blue-700"
        >
          <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <LucideIcon name="HandCoins" size={18} /> Loan applications
          </div>
          <p className="mt-2 font-display text-2xl font-semibold">{myLoans?.length ?? "—"}</p>
          <p className="mt-1 text-xs font-medium text-blue-600 group-hover:underline dark:text-blue-400">
            Open my loans →
          </p>
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Link
          to="/groups"
          className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-card transition hover:border-blue-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-blue-700"
        >
          <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <LucideIcon name="Coins" size={18} /> Hisa bought (all groups)
          </div>
          <p className="mt-2 font-display text-2xl font-semibold">
            {mySummary ? mySummary.total_shares.toLocaleString() : "—"}
          </p>
          <p className="mt-1 text-xs font-medium text-blue-600 group-hover:underline dark:text-blue-400">
            {mySummary?.group_count ?? 0} group{mySummary?.group_count === 1 ? "" : "s"} →
          </p>
        </Link>
        <Link
          to="/groups"
          className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-card transition hover:border-blue-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-blue-700"
        >
          <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <LucideIcon name="Wallet" size={18} /> Money contributed
          </div>
          <p className="mt-2 font-display text-2xl font-semibold">
            {mySummary ? (
              <>
                {formatMoney(Number(mySummary.contributed_total || 0))}
                {mySummary.contributed_pending > 0 && (
                  <span className="ml-2 text-xs font-normal text-slate-400">
                    +{formatMoney(Number(mySummary.contributed_pending))} pending
                  </span>
                )}
              </>
            ) : (
              "—"
            )}
          </p>
          <p className="mt-1 text-xs font-medium text-blue-600 group-hover:underline dark:text-blue-400">
            Confirmed contributions →
          </p>
        </Link>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <LucideIcon name="BadgePercent" size={18} /> Value of one hisa
          </div>
          <p className="mt-2 font-display text-2xl font-semibold">
            {mySummary ? formatMoney(Number(mySummary.hisa_value || 0)) : "—"}
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Average paid per hisa you own.
          </p>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
        <h2 className="mb-3 font-display text-lg font-semibold">Quick actions</h2>
        <div className="flex flex-wrap gap-3">
          <Link
            to="/wallet"
            className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700"
          >
            <LucideIcon name="PiggyBank" size={18} /> Deposit money
          </Link>
          <Link
            to="/loans-me?apply=1"
            className="inline-flex items-center gap-2 rounded-xl border border-blue-600 px-4 py-2.5 text-sm font-medium text-blue-700 transition hover:bg-blue-50 dark:text-blue-300 dark:hover:bg-blue-950/40"
          >
            <LucideIcon name="HandCoins" size={18} /> Apply for a loan
          </Link>
          <Link
            to="/groups"
            className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <LucideIcon name="Coins" size={18} /> Buy hisa
          </Link>
          {!profile.is_verified && (
            <Link
              to="/profile"
              className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700"
            >
              <LucideIcon name="ShieldCheck" size={18} /> Finish verification
            </Link>
          )}
          <Link
            to="/profile"
            className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <LucideIcon name="UserCog" size={18} /> Manage profile
          </Link>
        </div>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
        <h2 className="mb-4 flex items-center gap-2 font-display text-lg font-semibold">
          <LucideIcon name="PencilLine" /> My details
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormInput
            type="text"
            name="editFirstName"
            value={editable.first_name}
            label="First name"
            placeholder=""
            onChange={(e) => setEditable({ ...editable, first_name: e.target.value })}
          />
          <FormInput
            type="text"
            name="editLastName"
            value={editable.last_name}
            label="Last name"
            placeholder=""
            onChange={(e) => setEditable({ ...editable, last_name: e.target.value })}
          />
          <FormInput
            type="date"
            name="editDob"
            value={editable.date_of_birth}
            label="Date of birth"
            placeholder=""
            onChange={(e) => setEditable({ ...editable, date_of_birth: e.target.value })}
          />
          <FormInput
            type="text"
            name="editCountry"
            value={editable.country}
            label="Country"
            placeholder=""
            onChange={(e) => setEditable({ ...editable, country: e.target.value })}
          />
          <FormInput
            type="text"
            name="editCounty"
            value={editable.county}
            label="County"
            placeholder=""
            onChange={(e) => setEditable({ ...editable, county: e.target.value })}
          />
          <FormInput
            type="text"
            name="editCity"
            value={editable.city}
            label="City"
            placeholder=""
            onChange={(e) => setEditable({ ...editable, city: e.target.value })}
          />
        </div>
        <Button
          text={updateProfile.isPending ? <Spinner /> : "Save details"}
          type="button"
          variant="secondary"
          onClick={handleSaveProfile}
          className="mt-4 w-full sm:w-auto"
        />
      </section>
    </div>
  );
};

export default MemberHome;