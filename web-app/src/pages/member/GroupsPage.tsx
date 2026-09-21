import { FC, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";

import Spinner from "@/components/Spinner";
import { SkeletonGrid } from "@/components/Skeleton";
import LucideIcon from "@/components/LucideIcon";
import { Button } from "@/components/ui/button";
import VerifiedBadge from "@/components/VerifiedBadge";
import {
  useAcceptInvite,
  useGetMyGroups,
  useGetMyGroupsSummary,
  useGetPendingInvitations,
} from "@/hooks/api/groups";
import { useGetMyMemberProfile } from "@/hooks/api/memberSelf";
import { useUserProfileInfo } from "@/hooks/useUserProfile";
import { getApiErrorMessage } from "@/lib/utils";
import { formatPlace } from "@/lib/geo";

const GroupsPage: FC = () => {
  const navigate = useNavigate();
  const { profile } = useUserProfileInfo();
  const { data: me } = useGetMyMemberProfile(profile?.role === "ME");
  const isVerified = profile?.role === "ME" ? Boolean(me?.is_verified) : true;

  const { data: groups, isLoading } = useGetMyGroups();
  const { data: invitations, isLoading: isInvitesLoading } = useGetPendingInvitations(
    profile?.role === "ME",
  );
  const { data: mySummary } = useGetMyGroupsSummary(profile?.role === "ME");

  const acceptInvite = useAcceptInvite();

  const [accepting, setAccepting] = useState<string | null>(null);

  const groupLimit = isVerified ? 3 : 1;
  const createdCount = mySummary?.created_count ?? 0;
  const atGroupLimit = createdCount >= groupLimit;

  const openCreate = () => {
    if (atGroupLimit) {
      toast.error(
        `You can only create ${groupLimit} group${groupLimit === 1 ? "" : "s"}.`,
        { autoClose: 3500 },
      );
      return;
    }
    navigate("/create-group");
  };

  const handleAccept = (token: string) => {
    setAccepting(token);
    acceptInvite.mutate(token, {
      onSuccess: () => {
        toast.success("You joined the group.", { autoClose: 2500 });
        setAccepting(null);
      },
      onError: (error) => {
        toast.error(getApiErrorMessage(error, "Could not accept the invitation"), { autoClose: 3000 });
        setAccepting(null);
      },
    });
  };

  const loading = isLoading;

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 font-display text-2xl font-semibold">
            My Groups <VerifiedBadge size={20} />
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Create or join savings groups, buy hisa and make contributions.
          </p>
        </div>
        <Button type="button" onClick={openCreate} disabled={atGroupLimit}>
          <LucideIcon name="Plus" size={16} className="mr-1" />
          Create group
        </Button>
      </div>
      {atGroupLimit && (
        <p className="mb-3 -mt-2 text-right text-xs font-medium text-slate-500 dark:text-slate-400">
          Limit of {groupLimit} group{groupLimit === 1 ? "" : "s"} reached.
        </p>
      )}

      {!isVerified && (
        <div className="mb-6 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/30 dark:text-amber-200">
          <LucideIcon name="Info" size={18} className="mt-0.5 shrink-0" />
          <p>
            You're still unverified. You can create up to <strong>1 group</strong>,
            join others, buy hisa and contribute today — verification is only needed
            when you take a loan or withdraw. Get verified to create up to 3 groups.
          </p>
        </div>
      )}
      {isVerified && (
        <div className="mb-6 flex items-start gap-3 rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 dark:border-blue-700/50 dark:bg-blue-950/30 dark:text-blue-200">
          <LucideIcon name="BadgeCheck" size={18} className="mt-0.5 shrink-0" />
          <p>
            You can create up to <strong>3 groups</strong> as a verified member
            {createdCount > 0 ? ` (${createdCount} created so far)` : ""}.
          </p>
        </div>
      )}

      {isInvitesLoading || loading ? (
        <SkeletonGrid count={4} />
      ) : invitations && invitations.length > 0 ? (
        <div className="mb-6 rounded-2xl border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-blue-950/30">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-blue-900 dark:text-blue-100">
            <LucideIcon name="MailOpen" size={16} /> Pending invitations
          </h2>
          <ul className="space-y-2">
            {invitations.map((invite) => (
              <li
                key={invite.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white px-4 py-3 dark:bg-slate-900"
              >
                <div>
                  <p className="text-sm font-medium">{invite.group_name}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Invited by email — accept to join
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={accepting === invite.token}
                  onClick={() => handleAccept(invite.token)}
                >
                  {accepting === invite.token ? <Spinner /> : "Accept"}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {loading ? null : !groups || groups.length === 0 ? (
        <div className="flex flex-col items-center rounded-2xl border border-dashed border-slate-300 py-16 text-center dark:border-slate-700">
          <LucideIcon name="Boxes" size={40} className="text-slate-400" />
          <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
            You haven't joined any group yet.
          </p>
          <Button type="button" variant="outline" className="mt-4" onClick={openCreate}>
            Create your first group
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {groups.map((group) => (
            <Link
              key={group.id}
              to={`/groups/${group.id}`}
              className="group rounded-2xl border border-slate-200 bg-white p-5 transition hover:border-blue-300 hover:shadow-card dark:border-slate-800 dark:bg-slate-900 dark:hover:border-blue-800"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold">{group.name}</h3>
                <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                  {group.status === "ACTIVE" ? "Active" : "Closed"}
                </span>
              </div>
              {(group.area || group.region || group.country) && (
                <p className="mt-1 flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400">
                  <LucideIcon name="MapPin" size={12} />{" "}
                  {formatPlace({
                    area: group.area,
                    region: group.region,
                    country: group.country,
                  })}
                </p>
              )}
              <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
                <div className="rounded-xl bg-slate-50 px-3 py-2 dark:bg-slate-800">
                  <p className="text-xs text-slate-500 dark:text-slate-400">Members</p>
                  <p className="font-semibold">{group.member_count}</p>
                </div>
                <div className="rounded-xl bg-slate-50 px-3 py-2 dark:bg-slate-800">
                  <p className="text-xs text-slate-500 dark:text-slate-400">Your hisa</p>
                  <p className="font-semibold">{group.my_shares}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

export default GroupsPage;