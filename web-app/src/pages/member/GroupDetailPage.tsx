
import { FC, ReactNode, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "react-toastify";

import Spinner from "@/components/Spinner";
import { SkeletonPage } from "@/components/Skeleton";
import LucideIcon from "@/components/LucideIcon";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  GroupActivity,
  GroupContribution,
  GroupLedgerEntry,
  GroupLoanProjection,
  GroupMembershipInfo,
  GroupRepaymentProjection,
  GroupWorkspaceOverview,
} from "@/services/groups";
import {
  useGetGroupActivity,
  useGetGroupLedger,
  useGetGroupLoans,
  useGetGroupMembers,
  useGetGroupOverview,
  useGetGroupRepayments,
  useGetContributions,
  useInviteToGroup,
} from "@/hooks/api/groups";
import {
  useInitiateContributionPayment,
  useMyPaymentStatus,
} from "@/hooks/api/memberPayments";
import { useCurrency } from "@/contexts/CurrencyContext";
import { getApiErrorMessage } from "@/lib/utils";

type TabKey =
  | "overview"
  | "members"
  | "contributions"
  | "loans"
  | "repayments"
  | "ledger"
  | "activity";

const tabs: { key: TabKey; label: string; icon: string }[] = [
  { key: "overview", label: "Overview", icon: "LayoutDashboard" },
  { key: "members", label: "Members", icon: "UsersRound" },
  { key: "contributions", label: "Contributions", icon: "ReceiptText" },
  { key: "loans", label: "Loans", icon: "HandCoins" },
  { key: "repayments", label: "Repayments", icon: "BadgeDollarSign" },
  { key: "ledger", label: "Ledger", icon: "BookOpenText" },
  { key: "activity", label: "Activity", icon: "History" },
];

const CURRENT_MONTH = new Date().toISOString().slice(0, 7);

const statusClass = (status?: string) => {
  const value = (status || "").toUpperCase();

  if (
    [
      "CONFIRMED",
      "SUCCESS",
      "POSTED",
      "PAID",
      "ACTIVE",
      "DISBURSED",
      "RECORDED",
    ].includes(value)
  ) {
    return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-transparent";
  }

  if (
    ["PENDING", "PROCESSING", "SUBMITTED", "UNDER_REVIEW", "DUE"].includes(
      value,
    )
  ) {
    return "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-transparent";
  }

  if (
    [
      "REJECTED",
      "FAILED",
      "VOIDED",
      "EXPIRED",
      "CANCELLED",
      "DEFAULTED",
    ].includes(value)
  ) {
    return "bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 border-transparent";
  }

  return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-transparent";
};

const memberName = (
  member?: {
    first_name?: string;
    last_name?: string;
    membership_number?: string;
  } | null,
) => {
  if (!member) return "Unknown member";

  const name = `${member.first_name || ""} ${member.last_name || ""}`.trim();

  return name || member.membership_number || "Unknown member";
};

const EmptyState = ({
  icon,
  title,
  body,
}: {
  icon: string;
  title: string;
  body: string;
}) => (
  <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-10 text-center dark:border-slate-700 dark:bg-slate-900">
    <LucideIcon
      name={icon}
      size={34}
      className="mx-auto text-slate-400"
    />
    <p className="mt-3 font-medium">{title}</p>
    <p className="mx-auto mt-1 max-w-md text-sm text-slate-500 dark:text-slate-400">
      {body}
    </p>
  </div>
);

const ErrorState = ({ message }: { message: string }) => (
  <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-5 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
    {message}
  </div>
);

const SearchInput = ({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) => (
  <div className="relative min-w-0 flex-1">
    <LucideIcon
      name="Search"
      size={16}
      className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
    />
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className="h-10 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-sm outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-700/10 dark:border-slate-800 dark:bg-slate-950"
    />
  </div>
);

const Metric = ({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) => (
  <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/70">
    <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
      {label}
    </p>
    <p className="mt-1 truncate font-display text-lg font-semibold">
      {value}
    </p>
  </div>
);

const Panel = ({
  title,
  icon,
  children,
}: {
  title: string;
  icon: string;
  children: ReactNode;
}) => (
  <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
    <h2 className="mb-4 flex items-center gap-2 font-display text-lg font-semibold">
      <LucideIcon name={icon} size={18} />
      {title}
    </h2>
    {children}
  </section>
);

const GroupDetailPage: FC = () => {
  const { groupId } = useParams();
  const { formatMoney } = useCurrency();

  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [memberSearch, setMemberSearch] = useState("");
  const [memberRole, setMemberRole] = useState("");
  const [contributionSearch, setContributionSearch] = useState("");
  const [contributionStatus, setContributionStatus] = useState("");
  const [loanSearch, setLoanSearch] = useState("");
  const [loanStatus, setLoanStatus] = useState("");
  const [ledgerSearch, setLedgerSearch] = useState("");
  const [ledgerStatus, setLedgerStatus] = useState("");
  const [selectedLedger, setSelectedLedger] =
    useState<GroupLedgerEntry | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [paymentForm, setPaymentForm] = useState({
    amount: "",
    month: CURRENT_MONTH,
    phone: "",
  });

  const overview = useGetGroupOverview(groupId);

  const members = useGetGroupMembers(groupId, {
    search: memberSearch,
    role: memberRole,
    page_size: 30,
  });

  const contributions = useGetContributions(groupId, {
    search: contributionSearch,
    status: contributionStatus,
    page_size: 30,
  });

  const loans = useGetGroupLoans(groupId, {
    search: loanSearch,
    status: loanStatus,
    page_size: 30,
  });

  const repayments = useGetGroupRepayments(groupId, {
    page_size: 30,
  });

  const ledger = useGetGroupLedger(groupId, {
    search: ledgerSearch,
    status: ledgerStatus,
    page_size: 30,
  });

  const activity = useGetGroupActivity(groupId, {
    page_size: 30,
  });

  const invite = useInviteToGroup();

  const contributionPayment = useInitiateContributionPayment();

  const paymentStatus = useMyPaymentStatus(
    paymentReference,
    Boolean(paymentReference),
  );

  const group = overview.data?.group;
  const permissions = overview.data?.permissions;

  const headerPlace = useMemo(
    () =>
      [group?.area, group?.region, group?.country]
        .filter(Boolean)
        .join(", "),
    [group],
  );

  const submitContributionPayment = () => {
    if (!groupId || !paymentForm.amount || Number(paymentForm.amount) <= 0) {
      toast.error("Enter a valid contribution amount.");
      return;
    }

    contributionPayment.mutate(
      {
        group_id: Number(groupId),
        amount: paymentForm.amount,
        month: paymentForm.month,
        phone: paymentForm.phone || undefined,
      },
      {
        onSuccess: (tx) => {
          setPaymentReference(tx.reference);

          toast.success(
            "Payment request initiated. It will stay pending until confirmed by the provider.",
          );

          setPaymentForm({
            amount: "",
            month: CURRENT_MONTH,
            phone: "",
          });
        },

        onError: (error) =>
          toast.error(
            getApiErrorMessage(
              error,
              "Could not initiate contribution payment.",
            ),
          ),
      },
    );
  };

  const submitInvite = () => {
    if (!groupId || !inviteEmail.trim()) return;

    invite.mutate(
      {
        groupId,
        email: inviteEmail.trim(),
      },
      {
        onSuccess: () => {
          toast.success("Invitation sent.");
          setInviteEmail("");
          overview.refetch();
          activity.refetch();
        },

        onError: (error) =>
          toast.error(
            getApiErrorMessage(error, "Could not send invitation."),
          ),
      },
    );
  };

  if (overview.isLoading) {
    return <SkeletonPage />;
  }

  if (overview.isError || !overview.data || !group) {
    return (
      <div className="mx-auto max-w-4xl">
        <ErrorState message="Unable to load this group. You may not have access or the group no longer exists." />

        <Link
          className="mt-4 inline-flex text-sm font-medium text-blue-700 hover:underline dark:text-blue-300"
          to="/groups"
        >
          Back to groups
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <Link
              className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:underline dark:text-blue-300"
              to="/groups"
            >
              <LucideIcon name="ChevronLeft" size={16} />
              Groups
            </Link>

            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-display text-2xl font-semibold sm:text-3xl">
                {group.name}
              </h1>

              <Badge className={statusClass(group.status)}>
                {group.status}
              </Badge>
            </div>

            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {group.code}
              {headerPlace ? ` · ${headerPlace}` : ""}
            </p>

            {group.description ? (
              <p className="mt-3 max-w-3xl text-sm text-slate-600 dark:text-slate-300">
                {group.description}
              </p>
            ) : null}
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[520px]">
            <Metric label="Members" value={group.member_count} />
            <Metric label="Your role" value={group.my_role} />
            <Metric label="Total hisa" value={group.total_shares} />
            <Metric
              label="Pending"
              value={overview.data.pending_items.pending_contributions}
            />
          </div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white p-2 shadow-card dark:border-slate-800 dark:bg-slate-900">
        <div className="flex min-w-max gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`inline-flex h-10 items-center gap-2 rounded-xl px-3 text-sm font-medium transition ${
                activeTab === tab.key
                  ? "bg-blue-700 text-white"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              }`}
            >
              <LucideIcon name={tab.icon} size={16} />
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {activeTab === "overview" && (
        <OverviewTab
          overview={overview.data}
          formatMoney={formatMoney}
          onOpenLedger={(entry) => {
            setSelectedLedger(entry);
            setActiveTab("ledger");
          }}
        />
      )}

      {activeTab === "members" && (
        <MembersTab
          members={members.data?.results ?? []}
          isLoading={members.isLoading}
          isError={members.isError}
          search={memberSearch}
          setSearch={setMemberSearch}
          role={memberRole}
          setRole={setMemberRole}
          inviteEmail={inviteEmail}
          setInviteEmail={setInviteEmail}
          submitInvite={submitInvite}
          canInvite={Boolean(permissions?.can_invite)}
        />
      )}

      {activeTab === "contributions" && (
        <ContributionsTab
          rows={contributions.data?.results ?? []}
          isLoading={contributions.isLoading}
          isError={contributions.isError}
          search={contributionSearch}
          setSearch={setContributionSearch}
          statusFilter={contributionStatus}
          setStatusFilter={setContributionStatus}
          paymentForm={paymentForm}
          setPaymentForm={setPaymentForm}
          submitPayment={submitContributionPayment}
          isSubmitting={contributionPayment.isPending}
          paymentStatus={paymentStatus.data?.status}
          formatMoney={formatMoney}
        />
      )}

      {activeTab === "loans" && (
        <LoansTab
          rows={loans.data?.results ?? []}
          isLoading={loans.isLoading}
          isError={loans.isError}
          search={loanSearch}
          setSearch={setLoanSearch}
          statusFilter={loanStatus}
          setStatusFilter={setLoanStatus}
          formatMoney={formatMoney}
        />
      )}

      {activeTab === "repayments" && (
        <RepaymentsTab
          rows={repayments.data?.results ?? []}
          isLoading={repayments.isLoading}
          isError={repayments.isError}
          formatMoney={formatMoney}
        />
      )}

      {activeTab === "ledger" && (
        <LedgerTab
          rows={ledger.data?.results ?? []}
          isLoading={ledger.isLoading}
          isError={ledger.isError}
          search={ledgerSearch}
          setSearch={setLedgerSearch}
          statusFilter={ledgerStatus}
          setStatusFilter={setLedgerStatus}
          selected={selectedLedger}
          setSelected={setSelectedLedger}
          formatMoney={formatMoney}
        />
      )}

      {activeTab === "activity" && (
        <ActivityTab
          rows={activity.data?.results ?? []}
          isLoading={activity.isLoading}
          isError={activity.isError}
        />
      )}
    </div>
  );
};

const OverviewTab = ({
  overview,
  formatMoney,
  onOpenLedger,
}: {
  overview: GroupWorkspaceOverview;
  formatMoney: (amount: number) => string;
  onOpenLedger: (entry: GroupLedgerEntry) => void;
}) => (
  <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(360px,0.7fr)]">
    <section className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="Confirmed contributions"
          value={formatMoney(
            Number(overview.contribution_summary.confirmed_amount || 0),
          )}
        />

        <Metric
          label="Pending contributions"
          value={formatMoney(
            Number(overview.contribution_summary.pending_amount || 0),
          )}
        />

        <Metric
          label="Active loans"
          value={overview.loan_summary.active_count}
        />

        <Metric
          label="Outstanding loans"
          value={formatMoney(
            Number(overview.loan_summary.outstanding_total || 0),
          )}
        />
      </div>

      <Panel title="Recent transactions" icon="BookOpenText">
        {overview.recent_ledger.length === 0 ? (
          <EmptyState
            icon="BookOpenText"
            title="No ledger entries yet"
            body="Contributions, shares, loans and share-outs will appear here as records are created."
          />
        ) : (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {overview.recent_ledger.map((entry) => (
              <button
                key={entry.id}
                type="button"
                onClick={() => onOpenLedger(entry)}
                className="flex w-full items-center justify-between gap-3 py-3 text-left"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    {entry.transaction_type}
                  </p>

                  <p className="truncate text-xs text-slate-500">
                    {memberName(entry.member)} ·{" "}
                    {entry.reference || "No reference"}
                  </p>
                </div>

                <div className="text-right">
                  <p className="font-display font-semibold">
                    {formatMoney(Number(entry.amount || 0))}
                  </p>

                  <Badge className={statusClass(entry.status)}>
                    {entry.status}
                  </Badge>
                </div>
              </button>
            ))}
          </div>
        )}
      </Panel>
    </section>

    <section className="space-y-5">
      <Panel title="Pending items" icon="CircleAlert">
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
          <Metric
            label="Pending contributions"
            value={overview.pending_items.pending_contributions}
          />

          <Metric
            label="Pending invitations"
            value={overview.pending_items.pending_invitations}
          />
        </div>
      </Panel>

      <Panel title="Recent activity" icon="History">
        <ActivityList rows={overview.recent_activity} />
      </Panel>
    </section>
  </div>
);

const MembersTab = ({
  members,
  isLoading,
  isError,
  search,
  setSearch,
  role,
  setRole,
  inviteEmail,
  setInviteEmail,
  submitInvite,
  canInvite,
}: {
  members: GroupMembershipInfo[];
  isLoading: boolean;
  isError: boolean;
  search: string;
  setSearch: (value: string) => void;
  role: string;
  setRole: (value: string) => void;
  inviteEmail: string;
  setInviteEmail: (value: string) => void;
  submitInvite: () => void;
  canInvite: boolean;
}) => (
  <Panel title="Members" icon="UsersRound">
    <div className="mb-4 flex flex-col gap-2 lg:flex-row">
      <SearchInput
        value={search}
        onChange={setSearch}
        placeholder="Search by name or member ID"
      />

      <select
        value={role}
        onChange={(event) => setRole(event.target.value)}
        className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950"
      >
        <option value="">All roles</option>
        <option value="CHAIRPERSON">Chairperson</option>
        <option value="TREASURER">Treasurer</option>
        <option value="SECRETARY">Secretary</option>
        <option value="MEMBER">Member</option>
      </select>
    </div>

    {canInvite && (
      <div className="mb-5 flex flex-col gap-2 rounded-2xl bg-slate-50 p-3 dark:bg-slate-950 sm:flex-row">
        <input
          value={inviteEmail}
          onChange={(event) => setInviteEmail(event.target.value)}
          placeholder="Invite by email"
          className="h-10 min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-900"
        />

        <Button type="button" onClick={submitInvite}>
          <LucideIcon name="MailPlus" size={16} className="mr-1" />
          Invite
        </Button>
      </div>
    )}

    {isLoading ? (
      <Spinner />
    ) : isError ? (
      <ErrorState message="Unable to load group members." />
    ) : members.length === 0 ? (
      <EmptyState
        icon="UsersRound"
        title="No members found"
        body="Try adjusting your search or filters."
      />
    ) : (
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {members.map((item) => (
          <div
            key={item.id}
            className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800"
          >
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-blue-100 font-semibold text-blue-800 dark:bg-blue-950 dark:text-blue-200">
                {memberName(item.member).slice(0, 2).toUpperCase()}
              </div>

              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">
                  {memberName(item.member)}
                </p>

                <p className="text-xs text-slate-500">
                  {item.member.membership_number}
                </p>
              </div>

              <Badge className={statusClass(item.role)}>
                {item.role}
              </Badge>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
              <Metric label="Hisa" value={item.shares_count} />

              <Metric
                label="Status"
                value={item.is_active ? "Active" : "Inactive"}
              />
            </div>

            <div className="mt-3 flex flex-wrap gap-2">
              <Badge
                className={statusClass(
                  item.is_verified ? "CONFIRMED" : "PENDING",
                )}
              >
                {item.is_verified ? "Verified" : "Unverified"}
              </Badge>

              {item.member_status ? (
                <Badge variant="outline">{item.member_status}</Badge>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    )}
  </Panel>
);

const ContributionsTab = ({
  rows,
  isLoading,
  isError,
  search,
  setSearch,
  statusFilter,
  setStatusFilter,
  paymentForm,
  setPaymentForm,
  submitPayment,
  isSubmitting,
  paymentStatus,
  formatMoney,
}: {
  rows: GroupContribution[];
  isLoading: boolean;
  isError: boolean;
  search: string;
  setSearch: (value: string) => void;
  statusFilter: string;
  setStatusFilter: (value: string) => void;
  paymentForm: {
    amount: string;
    month: string;
    phone: string;
  };
  setPaymentForm: (value: {
    amount: string;
    month: string;
    phone: string;
  }) => void;
  submitPayment: () => void;
  isSubmitting: boolean;
  paymentStatus?: string;
  formatMoney: (amount: number) => string;
}) => (
  <div className="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
    <Panel title="Pay contribution" icon="Smartphone">
      <div className="space-y-3">
        <input
          value={paymentForm.amount}
          onChange={(event) =>
            setPaymentForm({
              ...paymentForm,
              amount: event.target.value,
            })
          }
          inputMode="decimal"
          placeholder="Amount"
          className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950"
        />

        <input
          value={paymentForm.month}
          onChange={(event) =>
            setPaymentForm({
              ...paymentForm,
              month: event.target.value,
            })
          }
          type="month"
          className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950"
        />

        <input
          value={paymentForm.phone}
          onChange={(event) =>
            setPaymentForm({
              ...paymentForm,
              phone: event.target.value,
            })
          }
          placeholder="Phone (optional)"
          className="h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950"
        />

        <Button
          type="button"
          className="w-full"
          onClick={submitPayment}
          disabled={isSubmitting}
        >
          {isSubmitting ? <Spinner /> : "Initiate payment"}
        </Button>

        <p className="text-xs text-slate-500">
          Payments use the existing payment service and stay pending until
          provider confirmation.
        </p>

        {paymentStatus ? (
          <Badge className={statusClass(paymentStatus)}>
            Latest payment: {paymentStatus}
          </Badge>
        ) : null}
      </div>
    </Panel>

    <Panel title="Contribution history" icon="ReceiptText">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search reference, member or ID"
        />

        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950"
        >
          <option value="">All statuses</option>
          <option value="PENDING">Pending</option>
          <option value="CONFIRMED">Completed</option>
          <option value="REJECTED">Failed</option>
        </select>
      </div>

      {isLoading ? (
        <Spinner />
      ) : isError ? (
        <ErrorState message="Unable to load contributions." />
      ) : rows.length === 0 ? (
        <EmptyState
          icon="ReceiptText"
          title="No contributions found"
          body="Contribution records will appear here after members pay or authorized manual records are created."
        />
      ) : (
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row) => (
            <div
              key={row.id}
              className="flex flex-wrap items-center justify-between gap-3 py-3"
            >
              <div>
                <p className="font-medium">
                  {memberName(row.member)}
                </p>

                <p className="text-xs text-slate-500">
                  {row.month} · {row.reference || "No reference"} ·{" "}
                  {new Date(row.created_at).toLocaleDateString()}
                </p>
              </div>

              <div className="text-right">
                <p className="font-display font-semibold">
                  {formatMoney(Number(row.amount || 0))}
                </p>

                <Badge className={statusClass(row.status)}>
                  {row.status === "CONFIRMED"
                    ? "Completed"
                    : row.status === "REJECTED"
                      ? "Failed"
                      : "Pending"}
                </Badge>
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  </div>
);

const LoansTab = ({
  rows,
  isLoading,
  isError,
  search,
  setSearch,
  statusFilter,
  setStatusFilter,
  formatMoney,
}: {
  rows: GroupLoanProjection[];
  isLoading: boolean;
  isError: boolean;
  search: string;
  setSearch: (value: string) => void;
  statusFilter: string;
  setStatusFilter: (value: string) => void;
  formatMoney: (amount: number) => string;
}) => (
  <Panel title="Group member loans" icon="HandCoins">
    <div className="mb-4 flex flex-col gap-2 sm:flex-row">
      <SearchInput
        value={search}
        onChange={setSearch}
        placeholder="Search borrower, member ID or loan number"
      />

      <select
        value={statusFilter}
        onChange={(event) => setStatusFilter(event.target.value)}
        className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950"
      >
        <option value="">All statuses</option>
        <option value="disbursed">Disbursed</option>
        <option value="closed">Closed</option>
        <option value="defaulted">Defaulted</option>
        <option value="approved">Approved</option>
      </select>
    </div>

    {isLoading ? (
      <Spinner />
    ) : isError ? (
      <ErrorState message="Unable to load group loans." />
    ) : rows.length === 0 ? (
      <EmptyState
        icon="HandCoins"
        title="No loans found"
        body="Loans belonging to group members will appear here. Ownership remains in the existing loan module."
      />
    ) : (
      <div className="grid gap-3 lg:grid-cols-2">
        {rows.map((loan) => (
          <div
            key={loan.loan_number}
            className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium">
                  {memberName(loan.borrower)}
                </p>

                <p className="text-xs text-slate-500">
                  {loan.loan_number} · {loan.product}
                </p>
              </div>

              <Badge className={statusClass(loan.status)}>
                {loan.status}
              </Badge>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2">
              <Metric
                label="Principal"
                value={formatMoney(
                  Number(loan.principal_amount || 0),
                )}
              />

              <Metric
                label="Outstanding"
                value={formatMoney(
                  Number(loan.outstanding_amount || 0),
                )}
              />
            </div>

            <p className="mt-3 text-sm text-slate-500">
              Next due:{" "}
              {loan.next_due_date
                ? `${formatMoney(
                    Number(loan.next_repayment_amount || 0),
                  )} on ${new Date(
                    loan.next_due_date,
                  ).toLocaleDateString()}`
                : "No unpaid schedule"}
            </p>
          </div>
        ))}
      </div>
    )}
  </Panel>
);

const RepaymentsTab = ({
  rows,
  isLoading,
  isError,
  formatMoney,
}: {
  rows: GroupRepaymentProjection[];
  isLoading: boolean;
  isError: boolean;
  formatMoney: (amount: number) => string;
}) => (
  <Panel title="Repayments" icon="BadgeDollarSign">
    {isLoading ? (
      <Spinner />
    ) : isError ? (
      <ErrorState message="Unable to load repayments." />
    ) : rows.length === 0 ? (
      <EmptyState
        icon="BadgeDollarSign"
        title="No repayments found"
        body="Loan repayments for group members will appear here from the existing loan/payment architecture."
      />
    ) : (
      <div className="divide-y divide-slate-100 dark:divide-slate-800">
        {rows.map((row) => (
          <div
            key={row.id}
            className="flex flex-wrap items-center justify-between gap-3 py-3"
          >
            <div>
              <p className="font-medium">
                {memberName(row.borrower)}
              </p>

              <p className="text-xs text-slate-500">
                {row.loan_reference} · {row.transaction_reference} ·{" "}
                {new Date(row.date).toLocaleDateString()}
              </p>
            </div>

            <div className="text-right">
              <p className="font-display font-semibold">
                {formatMoney(Number(row.amount || 0))}
              </p>

              <Badge className={statusClass(row.status)}>
                {row.status}
              </Badge>
            </div>
          </div>
        ))}
      </div>
    )}
  </Panel>
);

const LedgerTab = ({
  rows,
  isLoading,
  isError,
  search,
  setSearch,
  statusFilter,
  setStatusFilter,
  selected,
  setSelected,
  formatMoney,
}: {
  rows: GroupLedgerEntry[];
  isLoading: boolean;
  isError: boolean;
  search: string;
  setSearch: (value: string) => void;
  statusFilter: string;
  setStatusFilter: (value: string) => void;
  selected: GroupLedgerEntry | null;
  setSelected: (entry: GroupLedgerEntry | null) => void;
  formatMoney: (amount: number) => string;
}) => (
  <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
    <Panel title="Group ledger" icon="BookOpenText">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search reference, member or description"
        />

        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950"
        >
          <option value="">All statuses</option>
          <option value="SUCCESS">Success</option>
          <option value="CONFIRMED">Confirmed</option>
          <option value="PENDING">Pending</option>
          <option value="POSTED">Posted</option>
          <option value="FAILED">Failed</option>
        </select>
      </div>

      {isLoading ? (
        <Spinner />
      ) : isError ? (
        <ErrorState message="Unable to load ledger entries." />
      ) : rows.length === 0 ? (
        <EmptyState
          icon="BookOpenText"
          title="No ledger entries found"
          body="This read-only projection will show existing group financial records when available."
        />
      ) : (
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((entry) => (
            <button
              key={entry.id}
              type="button"
              onClick={() => setSelected(entry)}
              className="flex w-full flex-wrap items-center justify-between gap-3 py-3 text-left"
            >
              <div>
                <p className="font-medium">
                  {entry.transaction_type}
                </p>

                <p className="text-xs text-slate-500">
                  {memberName(entry.member)} ·{" "}
                  {entry.reference || "No reference"} ·{" "}
                  {new Date(entry.date).toLocaleDateString()}
                </p>
              </div>

              <div className="text-right">
                <p className="font-display font-semibold">
                  {formatMoney(Number(entry.amount || 0))}
                </p>

                <Badge className={statusClass(entry.status)}>
                  {entry.status}
                </Badge>
              </div>
            </button>
          ))}
        </div>
      )}
    </Panel>

    <Panel title="Transaction details" icon="FileText">
      {!selected ? (
        <p className="text-sm text-slate-500">
          Select a ledger row to inspect the transaction details.
        </p>
      ) : (
        <dl className="space-y-3 text-sm">
          <Detail label="Transaction ID" value={String(selected.id)} />

          <Detail
            label="Member"
            value={memberName(selected.member)}
          />

          <Detail
            label="Type"
            value={selected.transaction_type}
          />

          <Detail
            label="Amount"
            value={formatMoney(Number(selected.amount || 0))}
          />

          <Detail label="Status" value={selected.status} />

          <Detail
            label="Date/time"
            value={new Date(selected.date).toLocaleString()}
          />

          <Detail
            label="Internal reference"
            value={selected.internal_reference || "—"}
          />

          <Detail
            label="Provider reference"
            value={selected.provider_reference || "—"}
          />

          <Detail
            label="Related contribution"
            value={
              selected.related_contribution
                ? String(selected.related_contribution)
                : "—"
            }
          />

          <Detail
            label="Related loan"
            value={selected.related_loan || "—"}
          />

          <Detail
            label="Description"
            value={selected.description || "—"}
          />

          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => setSelected(null)}
          >
            Clear selection
          </Button>
        </dl>
      )}
    </Panel>
  </div>
);

const Detail = ({
  label,
  value,
}: {
  label: string;
  value: string;
}) => (
  <div>
    <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
      {label}
    </dt>

    <dd className="mt-1 break-words font-medium">
      {value}
    </dd>
  </div>
);

const ActivityTab = ({
  rows,
  isLoading,
  isError,
}: {
  rows: GroupActivity[];
  isLoading: boolean;
  isError: boolean;
}) => (
  <Panel title="Activity" icon="History">
    {isLoading ? (
      <Spinner />
    ) : isError ? (
      <ErrorState message="Unable to load activity." />
    ) : (
      <ActivityList rows={rows} />
    )}
  </Panel>
);

const ActivityList = ({ rows }: { rows: GroupActivity[] }) => {
  if (rows.length === 0) {
    return (
      <EmptyState
        icon="History"
        title="No activity yet"
        body="Group activity will appear here as members join, contributions are recorded, or roles change."
      />
    );
  }

  return (
    <ol className="space-y-3">
      {rows.map((item) => (
        <li
          key={item.id}
          className="flex gap-3 rounded-2xl border border-slate-200 p-3 dark:border-slate-800"
        >
          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200">
            <LucideIcon name="History" size={17} />
          </span>

          <div className="min-w-0">
            <p className="font-medium">{item.title}</p>

            <p className="text-sm text-slate-500">
              {item.description || item.event_type_display}
            </p>

            <p className="mt-1 text-xs text-slate-400">
              {new Date(item.created_at).toLocaleString()} ·{" "}
              {memberName(item.actor)}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
};

export default GroupDetailPage;
