import { FC, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";

import Spinner from "@/components/Spinner";
import { SkeletonPage } from "@/components/Skeleton";
import LucideIcon from "@/components/LucideIcon";
import { Button } from "@/components/ui/button";
import FormInput from "@/components/FormInput";
import {
  useAddContribution,
  useBuyShares,
  useCloseCommittee,
  useDeclareCandidacy,
  useGetCommittee,
  useGetContributions,
  useGetGroup,
  useInviteToGroup,
  useVoteCommittee,
} from "@/hooks/api/groups";
import { useGetMyMemberProfile } from "@/hooks/api/memberSelf";
import { useCurrency } from "@/contexts/CurrencyContext";
import { getApiErrorMessage } from "@/lib/utils";
import { formatPlace } from "@/lib/geo";
import WhatsAppConnectModal from "@/components/whatsapp/WhatsAppConnectModal";
import { useGetWhatsAppSessions } from "@/hooks/api/whatsapp";

const CURRENT_MONTH = new Date().toISOString().slice(0, 7);

const STATUS_STYLES: Record<string, string> = {
  PENDING: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
  CONFIRMED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300",
  REJECTED: "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300",
};

const GroupDetailPage: FC = () => {
  const { groupId } = useParams();
  const navigate = useNavigate();
  const { formatMoney } = useCurrency();

  const { data: group, isLoading, isError } = useGetGroup(groupId);
  const { data: contributions } = useGetContributions(groupId);
  const { data: committee } = useGetCommittee(groupId);
  const { data: myMember } = useGetMyMemberProfile();
  const isVerified = Boolean(myMember?.is_verified);

  const buyShares = useBuyShares(groupId);
  const invite = useInviteToGroup();
  const addContribution = useAddContribution(groupId);
  const declare = useDeclareCandidacy(groupId);
  const vote = useVoteCommittee(groupId);
  const closeVoting = useCloseCommittee(groupId);

  const [sharesForm, setSharesForm] = useState({ quantity: "1", amount: "" });
  const [contributionForm, setContributionForm] = useState({
    amount: "",
    month: CURRENT_MONTH,
    reference: "",
  });
  const [inviteEmail, setInviteEmail] = useState("");
  const [whatsappOpen, setWhatsappOpen] = useState(false);
  const { data: waSessions } = useGetWhatsAppSessions(Boolean(groupId));
  const groupDevice = waSessions?.find((s) => s.group === Number(groupId));

  const handleBuyShares = (e: React.FormEvent) => {
    e.preventDefault();
    const quantity = Number(sharesForm.quantity);
    if (!Number.isInteger(quantity) || quantity < 1) {
      toast.error("Enter how many hisa you want to buy.", { autoClose: 2500 });
      return;
    }
    buyShares.mutate(
      { quantity, amount_paid: sharesForm.amount || "0" },
      {
        onSuccess: () => {
          toast.success(`Bought ${quantity} hisa.`, { autoClose: 2500 });
          setSharesForm({ quantity: "1", amount: "" });
        },
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Could not buy hisa"), { autoClose: 3000 }),
      },
    );
  };

  const handleInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    invite.mutate(
      { groupId: groupId!, email: inviteEmail.trim() },
      {
        onSuccess: () => {
          toast.success("Invitation sent by email.", { autoClose: 2500 });
          setInviteEmail("");
        },
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Could not send the invitation"), {
            autoClose: 3000,
          }),
      },
    );
  };

  const handleContribute = (e: React.FormEvent) => {
    e.preventDefault();
    if (!contributionForm.amount || Number(contributionForm.amount) <= 0) {
      toast.error("Enter the contribution amount.", { autoClose: 2500 });
      return;
    }
    addContribution.mutate(
      {
        amount: contributionForm.amount,
        month: contributionForm.month,
        reference: contributionForm.reference.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast.success("Contribution recorded. It will show as pending until staff confirm it.", {
            autoClose: 3500,
          });
          setContributionForm({ amount: "", month: CURRENT_MONTH, reference: "" });
        },
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Could not record the contribution"), {
            autoClose: 3000,
          }),
      },
    );
  };

  const handleDeclare = (role: string) => {
    declare.mutate(role, {
      onSuccess: () => toast.success("You're now a candidate for this role.", { autoClose: 2500 }),
      onError: (error) =>
        toast.error(getApiErrorMessage(error, "Could not declare interest"), { autoClose: 3000 }),
    });
  };

  const handleVote = (role: string, candidate_id: string, candidateName: string) => {
    vote.mutate(
      { role, candidate_id },
      {
        onSuccess: () =>
          toast.success(`Your vote for ${candidateName} is recorded.`, { autoClose: 2500 }),
        onError: (error) =>
          toast.error(getApiErrorMessage(error, "Could not record your vote"), { autoClose: 3000 }),
      },
    );
  };

  const handleClose = (role: string) => {
    closeVoting.mutate(role, {
      onSuccess: (result) =>
        toast.success(
          `Voting closed. ${result.member?.first_name ?? "The winner"} is now ${result.role === "TREASURER" ? "treasurer" : "secretary"}.`,
          { autoClose: 3500 },
        ),
      onError: (error) =>
        toast.error(getApiErrorMessage(error, "Could not close voting"), { autoClose: 3000 }),
    });
  };

  if (isLoading) {
    return <SkeletonPage />;
  }

  if (isError || !group) {
    return (
      <div className="mx-auto w-full max-w-2xl px-4 py-16 text-center">
        <LucideIcon name="CircleAlert" size={36} className="mx-auto text-slate-400" />
        <h1 className="mt-3 font-display text-xl font-semibold">Group unavailable</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          You may not be a member of this group, or it doesn't exist.
        </p>
        <Button type="button" variant="outline" className="mt-5" onClick={() => navigate("/groups")}>
          Back to groups
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6">
      <Link
        to="/groups"
        className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
      >
        <LucideIcon name="ArrowLeft" size={16} /> My Groups
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 font-display text-2xl font-semibold">
            {group.name}
          </h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            {(group.area || group.region || group.country) && (
              <span className="inline-flex items-center gap-1">
                <LucideIcon name="MapPin" size={14} />{" "}
                {formatPlace({
                  area: group.area,
                  region: group.region,
                  country: group.country,
                })}
              </span>
            )}
            <span>{group.member_count} members</span>
            <span>Total hisa: {group.total_shares}</span>
          </p>
          {group.description && (
            <p className="mt-2 max-w-xl text-sm text-slate-600 dark:text-slate-300">
              {group.description}
            </p>
          )}
        </div>
        <div className="text-right">
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
            Your hisa: {group.my_shares}
          </span>
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        {/* Members */}
        <section className="rounded-2xl border border-slate-200 bg-white p-5 lg:col-span-2 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold">
            <LucideIcon name="Users" size={16} /> Members
          </h2>
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {group.members.map((membership) => {
              const initials = `${membership.member.first_name?.[0] ?? ""}${membership.member.last_name?.[0] ?? ""}`;
              return (
                <li key={membership.id} className="flex items-center gap-3 py-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-800 dark:bg-blue-950/50 dark:text-blue-200">
                    {initials || "•"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {membership.member.first_name} {membership.member.last_name}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {membership.member.membership_number}
                    </p>
                  </div>
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    hisa: {membership.shares_count}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>

        {/* Actions */}
        <section className="space-y-4">
          {/* Invite */}
          <form onSubmit={handleInvite} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <LucideIcon name="UserPlus" size={16} /> Invite by email
            </h2>
            <FormInput
              type="email"
              name="invite-email"
              value={inviteEmail}
              placeholder="friend@example.com"
              onChange={(e) => setInviteEmail(e.target.value)}
            />
            <Button
              type="submit"
              size="sm"
              className="mt-3 w-full"
            >
              <LucideIcon name="Send" size={14} className="mr-1" />
              Send invitation
            </Button>
          </form>

          {/* Buy hisa */}
          <form onSubmit={handleBuyShares} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <LucideIcon name="Coins" size={16} /> Buy hisa
            </h2>
            <div className="grid grid-cols-2 gap-3">
              <FormInput
                type="number"
                name="shares-quantity"
                value={sharesForm.quantity}
                label="Quantity"
                onChange={(e) => setSharesForm({ ...sharesForm, quantity: e.target.value })}
              />
              <FormInput
                type="number"
                name="shares-amount"
                value={sharesForm.amount}
                placeholder="Amount paid"
                label="Amount paid"
                onChange={(e) => setSharesForm({ ...sharesForm, amount: e.target.value })}
              />
            </div>
            <Button
              type="submit"
              size="sm"
              className="mt-3 w-full"
              disabled={buyShares.isPending}
            >
              {buyShares.isPending ? (
                <Spinner />
              ) : (
                <>
                  <LucideIcon name="ShoppingCart" size={14} className="mr-1" />
                  Buy hisa
                </>
              )}
            </Button>
          </form>

          {/* Contribute */}
          <form onSubmit={handleContribute} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <LucideIcon name="Wallet" size={16} /> Contribute
            </h2>
            <div className="grid grid-cols-2 gap-3">
              <FormInput
                type="number"
                name="contrib-amount"
                value={contributionForm.amount}
                placeholder="Amount"
                label="Amount"
                onChange={(e) => setContributionForm({ ...contributionForm, amount: e.target.value })}
              />
              <FormInput
                type="month"
                name="contrib-month"
                value={contributionForm.month}
                label="Month"
                onChange={(e) => setContributionForm({ ...contributionForm, month: e.target.value })}
              />
            </div>
            <FormInput
              type="text"
              name="contrib-reference"
              value={contributionForm.reference}
              placeholder="Reference (optional)"
              className="mt-3"
              onChange={(e) => setContributionForm({ ...contributionForm, reference: e.target.value })}
            />
            <Button
              type="submit"
              size="sm"
              variant="secondary"
              className="mt-3 w-full"
              disabled={addContribution.isPending}
            >
              {addContribution.isPending ? <Spinner /> : "Record contribution"}
            </Button>
          </form>
        </section>
      </div>

      {/* Committee */}
      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold">
          <LucideIcon name="Crown" size={16} /> Committee
        </h2>

        <div className="mb-5 grid gap-3 sm:grid-cols-3">
          {(
            [
              ["Chairperson", "Crown", committee?.chairperson],
              ["Treasurer", "PiggyBank", committee?.treasurer],
              ["Secretary", "ClipboardList", committee?.secretary],
            ] as const
          ).map(([label, icon, person]) => (
            <div
              key={label}
              className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5 dark:border-slate-800 dark:bg-slate-800/40"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
                <LucideIcon name={icon} size={16} />
              </span>
              <div className="min-w-0">
                <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
                <p className="truncate text-sm font-medium">
                  {person
                    ? `${person.first_name} ${person.last_name}`
                    : label === "Chairperson"
                      ? group.created_by?.first_name && group.created_by?.last_name
                        ? `${group.created_by.first_name} ${group.created_by.last_name}`
                        : "—"
                      : "Not elected yet"}
                </p>
              </div>
            </div>
          ))}
        </div>

        {committee && committee.is_chairperson && (
          <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50/60 p-4 dark:border-emerald-950 dark:bg-emerald-950/20">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <h3 className="text-sm font-semibold">WhatsApp receipts</h3>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                  {groupDevice?.status === "connected"
                    ? `Receipts go out from +${groupDevice.phone} · confirmed contributions notify members automatically.`
                    : "Connect the chairperson's WhatsApp so contribution receipts are sent automatically."}
                </p>
              </div>
              <Button type="button" size="sm" variant={groupDevice ? "outline" : "secondary"} onClick={() => setWhatsappOpen(true)}>
                {groupDevice
                  ? groupDevice.status === "connected"
                    ? "Manage device"
                    : `Connect device (${groupDevice.status.replace("_", " ")})`
                  : "Connect WhatsApp"}
              </Button>
            </div>
          </div>
        )}

        {committee &&
          (["TREASURER", "SECRETARY"] as const).map((role) => {
            const state = committee.roles[role];
            const roleName = role === "TREASURER" ? "Treasurer" : "Secretary";
            return (
              <div
                key={role}
                className="mt-4 rounded-xl border border-slate-100 p-4 dark:border-slate-800"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold">{roleName}</h3>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      state.open
                        ? "bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300"
                        : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                    }`}
                  >
                    {state.open ? "Voting open" : "Elected"}
                  </span>
                </div>

                {state.open ? (
                  <>
                    {state.candidates.length === 0 && (
                      <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
                        No candidates yet. Verified members can declare interest.
                      </p>
                    )}

                    {state.candidates.length > 0 && (
                      <ul className="mt-3 space-y-2">
                        {state.candidates.map((candidate) => (
                          <li
                            key={candidate.member_id}
                            className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/40"
                          >
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium">
                                {candidate.member.first_name} {candidate.member.last_name}
                                <span className="ml-2 text-xs font-normal text-slate-500">
                                  {candidate.votes} vote{candidate.votes === 1 ? "" : "s"}
                                </span>
                              </p>
                              <p className="text-xs text-slate-500 dark:text-slate-400">
                                {candidate.member.membership_number}
                              </p>
                            </div>
                            {state.my_vote === candidate.member_id ? (
                              <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                                Your vote
                              </span>
                            ) : (
                              !committee.is_chairperson && (
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() =>
                                    handleVote(
                                      role,
                                      candidate.member_id,
                                      `${candidate.member.first_name} ${candidate.member.last_name}`,
                                    )
                                  }
                                  disabled={vote.isPending}
                                >
                                  Vote
                                </Button>
                              )
                            )}
                          </li>
                        ))}
                      </ul>
                    )}

                    <div className="mt-3 flex flex-wrap gap-2">
                      {!state.my_candidacy && isVerified && !committee.is_chairperson && (
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={declare.isPending}
                            onClick={() => handleDeclare(role)}
                          >
                            {declare.isPending ? <Spinner /> : "Declare interest"}
                          </Button>
                        )}
                      {state.my_candidacy && (
                        <span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-800 dark:bg-blue-950/60 dark:text-blue-300">
                          You declared interest
                        </span>
                      )}
                      {committee.is_chairperson && (
                        <Button
                          type="button"
                          size="sm"
                          variant="destructive"
                          disabled={closeVoting.isPending}
                          onClick={() =>
                            window.confirm(
                              `Close voting for ${roleName}? The candidate with the most votes wins.`,
                            ) && handleClose(role)
                          }
                        >
                          {closeVoting.isPending ? <Spinner /> : "Close voting"}
                        </Button>
                      )}
                    </div>
                  </>
                ) : (
                  <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                    {committee.roles[role].candidates[0]
                      ? `${roleName} elected with ${committee.roles[role].candidates[0].votes} vote${committee.roles[role].candidates[0].votes === 1 ? "" : "s"}.`
                      : `${roleName} elected.`}
                  </p>
                )}
              </div>
            );
          })}
      </section>

      {/* Contributions */}
      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold">
          <LucideIcon name="ReceiptText" size={16} /> My contributions
        </h2>
        {!contributions || contributions.length === 0 ? (
          <p className="py-4 text-center text-sm text-slate-500 dark:text-slate-400">
            No contributions yet.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {contributions.map((contribution) => (
              <li key={contribution.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div>
                  <p className="text-sm font-medium">
                    {formatMoney(Number(contribution.amount))}
                    <span className="ml-2 text-xs font-normal text-slate-500">{contribution.month}</span>
                  </p>
                  {contribution.reference && (
                    <p className="text-xs text-slate-500 dark:text-slate-400">{contribution.reference}</p>
                  )}
                </div>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    STATUS_STYLES[contribution.status] ?? ""
                  }`}
                >
                  {contribution.status_display}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <WhatsAppConnectModal
        isOpen={whatsappOpen}
        onClose={() => setWhatsappOpen(false)}
        groupId={groupId ? Number(groupId) : undefined}
        defaultDisplayName="Chairperson device"
        onConnected={(phone) => toast.success(`Device connected (+${phone}).`, { autoClose: 3000 })}
      />
    </div>
  );
};

export default GroupDetailPage;