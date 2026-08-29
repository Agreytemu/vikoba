import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  MapPin,
  PiggyBank,
  Users,
  WalletCards,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useGetAccounts } from "@/hooks/api/accounts";
import { useGetMembers } from "@/hooks/api/members";
import { useLoans } from "@/hooks/api/loans";
import { useGetTransactions } from "@/hooks/api/transactions";
import { useUserProfileInfo } from "@/hooks/useUserProfile";
import { hasModuleAccess } from "@/lib/access-control";

import { formatDate } from "@/lib/utils";
import { SYSTEM_NAME } from "@/lib/system";
import { useCurrency } from "@/contexts/CurrencyContext";
import { findCurrencyChoice } from "@/lib/currency";

const statusLabels: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  under_review: "Under review",
  approved: "Approved",
  rejected: "Rejected",
  disbursed: "Disbursed",
};

const statusColours: Record<string, string> = {
  draft: "#94a3b8",
  submitted: "#0d9488",
  under_review: "#f59e0b",
  approved: "#16a34a",
  rejected: "#ef4444",
  disbursed: "#115036",
};

const DashBoard = () => {
  const { t } = useTranslation();
  const { profile } = useUserProfileInfo();
  const {
    formatMoney,
    currency,
    countryName,
    promptState,
    requestDetection,
    dismissPrompt,
    openPicker,
  } = useCurrency();
  const money = formatMoney;
  const currencyLabel = findCurrencyChoice(currency)?.label || currency;
  const canViewMembers = hasModuleAccess(profile?.role, "members");
  const canViewAccounts = hasModuleAccess(profile?.role, "accounts");
  const canViewTransactions = hasModuleAccess(profile?.role, "transactions");
  const canViewLoans = hasModuleAccess(profile?.role, "loans");
  const { data: members = [], isLoading: membersLoading } = useGetMembers(canViewMembers);
  const { data: accounts = [], isLoading: accountsLoading } = useGetAccounts(canViewAccounts);
  const { data: transactions = [], isLoading: transactionsLoading } = useGetTransactions(canViewTransactions);
  const { data: loans = [], isLoading: loansLoading } = useLoans({}, canViewLoans);

  const dashboardLoading =
    (canViewMembers && membersLoading) ||
    (canViewAccounts && accountsLoading) ||
    (canViewTransactions && transactionsLoading) ||
    (canViewLoans && loansLoading);

  const activeMembers = members.filter((member) => member.status === "Active").length;
  const activeAccounts = accounts.filter((account) => account.is_active);
  const totalSavings = activeAccounts.reduce((total, account) => total + Number(account.balance || 0), 0);
  const pendingLoans = loans.filter((loan) => loan.status === "submitted" || loan.status === "under_review").length;

  const { cashFlow, thisMonthDeposits, thisMonthWithdrawals } = useMemo(() => {
    const months = Array.from({ length: 6 }, (_, index) => {
      const date = new Date();
      date.setDate(1);
      date.setMonth(date.getMonth() - (5 - index));
      return {
        key: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`,
        month: date.toLocaleDateString(undefined, { month: "short" }),
        deposits: 0,
        withdrawals: 0,
      };
    });
    const rows = new Map(months.map((item) => [item.key, item]));
    transactions.forEach((transaction) => {
      const date = new Date(transaction.created_at);
      if (Number.isNaN(date.getTime())) return;
      const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
      const row = rows.get(key);
      if (!row) return;
      if (transaction.transaction_type.toLowerCase() === "deposit") row.deposits += Number(transaction.amount || 0);
      if (transaction.transaction_type.toLowerCase() === "withdrawal") row.withdrawals += Number(transaction.amount || 0);
    });
    const current = months[months.length - 1];
    return { cashFlow: months, thisMonthDeposits: current.deposits, thisMonthWithdrawals: current.withdrawals };
  }, [transactions]);

  const loanStatusData = useMemo(() => Object.entries(statusLabels)
    .map(([status, name]) => ({ name, value: loans.filter((loan) => loan.status === status).length, fill: statusColours[status] }))
    .filter((item) => item.value > 0), [loans]);

  const productBalances = useMemo(() => Object.values(accounts.reduce<Record<string, { product: string; balance: number }>>((groups, account) => {
    const product = account.product || "Unspecified";
    groups[product] ||= { product, balance: 0 };
    groups[product].balance += Number(account.balance || 0);
    return groups;
  }, {})).sort((a, b) => b.balance - a.balance).slice(0, 6), [accounts]);

  const recentTransactions = useMemo(() => [...transactions]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 6), [transactions]);
  const recentLoans = useMemo(() => [...loans]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5), [loans]);

  if (dashboardLoading) return <div className="flex min-h-screen items-center justify-center"><Spinner /></div>;

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 py-2 md:gap-7">
      <div>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-blue-700 dark:text-blue-400">Operations overview</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">Good day, {profile?.username || "there"}</h1>
            <p className="mt-2 text-sm text-slate-500">A live view of {SYSTEM_NAME}'s member activity, savings, and loan pipeline.</p>
          </div>
          <button
            type="button"
            onClick={openPicker}
            className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-blue-300 hover:text-blue-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-blue-400"
          >
            <LucideIcon name="Banknote" size={16} />
            <span>{currency}</span>
            {countryName && <span className="text-xs text-slate-500">· {countryName}</span>}
            <span className="text-xs text-blue-600 underline">{t("currency.change")}</span>
          </button>
        </div>
      </div>

      {promptState === "ask" && (
        <Card className="border-blue-200 bg-gradient-to-br from-blue-50/80 to-white dark:border-blue-900 dark:from-blue-950/30 dark:to-slate-950">
          <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <span className="rounded-full bg-blue-100 p-2 text-blue-700 dark:bg-blue-900/50 dark:text-blue-200">
                <MapPin className="h-5 w-5" />
              </span>
              <div>
                <p className="font-medium">{t("currency.promptTitle")}</p>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{t("currency.promptBody")}</p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Button onClick={requestDetection}>{t("currency.allow")}</Button>
              <Button type="button" variant="ghost" onClick={dismissPrompt}>
                {t("currency.later")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {promptState === "detecting" && (
        <Card className="border-blue-200 dark:border-blue-900">
          <CardContent className="flex items-center gap-3 p-4 text-sm text-slate-600 dark:text-slate-300">
            <Spinner /> {t("currency.detecting")}
          </CardContent>
        </Card>
      )}

      {promptState === "note" && (
        <p className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <MapPin className="h-3.5 w-3.5" />
          {countryName
            ? t("currency.detected", { currency: currencyLabel, country: countryName })
            : t("currency.detectedNoCountry", { currency: currencyLabel })}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="overflow-hidden border-blue-100 bg-gradient-to-br from-blue-50 to-white dark:border-blue-950 dark:from-blue-950/40 dark:to-slate-950"><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle className="text-sm font-medium">Active members</CardTitle><Users className="h-4 w-4 text-blue-700" /></CardHeader><CardContent><p className="text-2xl font-semibold">{canViewMembers ? activeMembers.toLocaleString() : "—"}</p><p className="mt-1 text-xs text-slate-500">{canViewMembers ? `${members.length.toLocaleString()} total registered` : "Members access unavailable"}</p></CardContent></Card>
        <Card className="overflow-hidden border-emerald-100 bg-gradient-to-br from-emerald-50 to-white dark:border-emerald-950 dark:from-emerald-950/40 dark:to-slate-950"><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle className="text-sm font-medium">Savings held</CardTitle><PiggyBank className="h-4 w-4 text-emerald-700" /></CardHeader><CardContent><p className="text-2xl font-semibold">{canViewAccounts ? money(totalSavings) : "—"}</p><p className="mt-1 text-xs text-slate-500">{canViewAccounts ? `${activeAccounts.length} active accounts` : "Accounts access unavailable"}</p></CardContent></Card>
        <Card className="overflow-hidden border-violet-100 bg-gradient-to-br from-violet-50 to-white dark:border-violet-950 dark:from-violet-950/40 dark:to-slate-950"><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle className="text-sm font-medium">Net flow this month</CardTitle><WalletCards className="h-4 w-4 text-violet-700" /></CardHeader><CardContent><p className="text-2xl font-semibold">{canViewTransactions ? money(thisMonthDeposits - thisMonthWithdrawals) : "—"}</p><p className="mt-1 text-xs text-slate-500">{canViewTransactions ? `${money(thisMonthDeposits)} in · ${money(thisMonthWithdrawals)} out` : "Transactions access unavailable"}</p></CardContent></Card>
        <Card className="overflow-hidden border-amber-100 bg-gradient-to-br from-amber-50 to-white dark:border-amber-950 dark:from-amber-950/40 dark:to-slate-950"><CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle className="text-sm font-medium">Loans awaiting review</CardTitle><Activity className="h-4 w-4 text-amber-700" /></CardHeader><CardContent><p className="text-2xl font-semibold">{canViewLoans ? pendingLoans.toLocaleString() : "—"}</p><p className="mt-1 text-xs text-slate-500">{canViewLoans ? `${loans.length} applications in total` : "Loans access unavailable"}</p></CardContent></Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,1fr)]">
        <Card><CardHeader><CardTitle>Cash flow trend</CardTitle><CardDescription>Monthly deposits and withdrawals for the last six months.</CardDescription></CardHeader><CardContent className="h-72">{canViewTransactions && transactions.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={cashFlow}><CartesianGrid vertical={false} strokeDasharray="3 3" /><XAxis dataKey="month" tickLine={false} axisLine={false} /><YAxis tickFormatter={(value) => `${Number(value) / 1000}k`} tickLine={false} axisLine={false} width={45} /><Tooltip formatter={(value) => money(Number(value))} /><Legend /><Bar dataKey="deposits" name="Deposits" fill="#1f9a66" radius={[5, 5, 0, 0]} /><Bar dataKey="withdrawals" name="Withdrawals" fill="#f97316" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer> : <div className="flex h-full items-center justify-center text-sm text-slate-500">No transaction data available yet.</div>}</CardContent></Card>
        <Card><CardHeader className="flex flex-row items-start justify-between"><div><CardTitle>Loan pipeline</CardTitle><CardDescription>Applications by current status.</CardDescription></div>{canViewLoans && <Button asChild size="sm" variant="ghost"><Link to="/loans">View loans <ArrowUpRight className="ml-1 h-3.5 w-3.5" /></Link></Button>}</CardHeader><CardContent className="h-72">{canViewLoans && loanStatusData.length ? <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={loanStatusData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={83} paddingAngle={3}>{loanStatusData.map((item) => <Cell key={item.name} fill={item.fill} />)}</Pie><Tooltip /><Legend /></PieChart></ResponsiveContainer> : <div className="flex h-full items-center justify-center text-sm text-slate-500">No loan application data available yet.</div>}</CardContent></Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
        <Card><CardHeader className="flex flex-row items-start justify-between"><div><CardTitle>Recent transactions</CardTitle><CardDescription>Latest activity across all accounts.</CardDescription></div>{canViewTransactions && <Button asChild size="sm" variant="ghost"><Link to="/transactions">View all <ArrowUpRight className="ml-1 h-3.5 w-3.5" /></Link></Button>}</CardHeader><CardContent>{canViewTransactions && recentTransactions.length ? <Table><TableHeader><TableRow><TableHead>Reference</TableHead><TableHead>Account</TableHead><TableHead>Type</TableHead><TableHead>Amount</TableHead><TableHead>Date</TableHead></TableRow></TableHeader><TableBody>{recentTransactions.map((transaction) => <TableRow key={transaction.id}><TableCell className="font-medium">{transaction.reference}</TableCell><TableCell>{transaction.account_number}</TableCell><TableCell><Badge variant={transaction.transaction_type === "withdrawal" ? "destructive" : "secondary"}>{transaction.transaction_type}</Badge></TableCell><TableCell className={transaction.transaction_type === "withdrawal" ? "text-red-600" : "text-emerald-700"}>{transaction.transaction_type === "withdrawal" ? <ArrowDownRight className="mr-1 inline h-3.5 w-3.5" /> : <ArrowUpRight className="mr-1 inline h-3.5 w-3.5" />}{money(transaction.amount)}</TableCell><TableCell className="whitespace-nowrap text-slate-500">{formatDate(transaction.created_at)}</TableCell></TableRow>)}</TableBody></Table> : <p className="py-10 text-center text-sm text-slate-500">No transactions available yet.</p>}</CardContent></Card>
        <Card><CardHeader><CardTitle>Savings by product</CardTitle><CardDescription>Current balances in the most-used products.</CardDescription></CardHeader><CardContent className="h-72">{canViewAccounts && productBalances.length ? <ResponsiveContainer width="100%" height="100%"><LineChart data={productBalances} layout="vertical" margin={{ left: 10 }}><CartesianGrid horizontal={false} strokeDasharray="3 3" /><XAxis type="number" tickFormatter={(value) => `${Number(value) / 1000}k`} tickLine={false} axisLine={false} /><YAxis type="category" dataKey="product" width={90} tickLine={false} axisLine={false} /><Tooltip formatter={(value) => money(Number(value))} /><Line type="monotone" dataKey="balance" name="Balance" stroke="#059669" strokeWidth={3} dot={{ r: 4 }} /></LineChart></ResponsiveContainer> : <div className="flex h-full items-center justify-center text-sm text-slate-500">No account balance data available yet.</div>}</CardContent></Card>
      </div>

      <Card><CardHeader className="flex flex-row items-start justify-between"><div><CardTitle>Recent loan applications</CardTitle><CardDescription>Newest loan requests submitted into the workflow.</CardDescription></div>{canViewLoans && <Button asChild size="sm" variant="outline"><Link to="/loans">Open applications</Link></Button>}</CardHeader><CardContent>{canViewLoans && recentLoans.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">{recentLoans.map((loan) => <Link key={loan.application_number} to={loan.status === "draft" ? `/loans/edit/${loan.application_number}` : `/loans/view/${loan.application_number}`} className="rounded-lg border p-3 transition hover:border-blue-300 hover:bg-blue-50/50 dark:hover:bg-blue-950/20"><div className="flex items-start justify-between gap-2"><p className="font-medium text-blue-700">{loan.application_number}</p><Badge variant={loan.status === "rejected" ? "destructive" : "secondary"}>{statusLabels[loan.status]}</Badge></div><p className="mt-3 text-sm">{loan.member_name}</p><p className="mt-1 text-xs text-slate-500">{loan.loan_type_name}</p><p className="mt-3 font-medium">{money(loan.requested_amount)}</p></Link>)}</div> : <p className="py-6 text-center text-sm text-slate-500">No loan applications available yet.</p>}</CardContent></Card>
    </div>
  );
};

export default DashBoard;
