import { ChangeEvent, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "react-toastify";

import Button from "@/components/Button";
import FormInput from "@/components/FormInput";
import Spinner from "@/components/Spinner";
import { SkeletonTable } from "@/components/Skeleton";
import LucideIcon from "@/components/LucideIcon";
import Modal from "@/components/ui/Modal";
import { Badge } from "@/components/ui/badge";
import VerificationGate from "@/components/VerificationGate";
import {
  useAddMyDocument,
  useAddMyGuarantor,
  useCreateMyLoan,
  useGetLoanTypes,
  useGetMyEligibility,
  useGetMyLoan,
  useGetMyLoanAccounts,
  useGetMyLoans,
  useRepayMyLoan,
  useSubmitMyLoan,
} from "@/hooks/api/memberLoans";
import { useGetMyMemberProfile } from "@/hooks/api/memberSelf";
import { useGetMyAccounts } from "@/hooks/api/myAccounts";
import { useUserProfileInfo } from "@/hooks/useUserProfile";
import { useCurrency } from "@/contexts/CurrencyContext";
import { MyLoanAccount, MyLoanListItem, MyLoanScheduleEntry } from "@/services/memberLoans";
import { getApiErrorMessage } from "@/lib/utils";
import { Link } from "react-router-dom";

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  under_review: "Under review",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
  disbursed: "Disbursed",
};

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200 border-transparent",
  submitted: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200 border-transparent",
  under_review: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200 border-transparent",
  approved: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200 border-transparent",
  rejected: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200 border-transparent",
  cancelled: "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 border-transparent",
  disbursed: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200 border-transparent",
};

const STATUS_COLORS: Record<string, `bg-${string}`> = {
  draft: "bg-slate-300",
  submitted: "bg-blue-500",
  under_review: "bg-amber-500",
  approved: "bg-green-500",
  rejected: "bg-red-500",
  cancelled: "bg-slate-400",
  disbursed: "bg-emerald-500",
};

const SECURITY_TYPES = [
  "collateral",
  "salary_guarantee",
  "guaranteed",
  "none",
].map((value) => ({ value, label: value.replace(/_/g, " ") }));

const DOCUMENT_TYPES = [
  "National ID",
  "Passport photo",
  "Signature",
  "Salary slip",
  "Bank statement",
  "Collateral title deed",
  "Loan application form",
  "Other",
];

const MemberLoans = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { profile } = useUserProfileInfo();
  const isMember = profile?.role === "ME";
  const { data: me } = useGetMyMemberProfile(isMember);
  const isVerified = isMember ? Boolean(me?.is_verified) : false;

  const { data: loans, isLoading } = useGetMyLoans();
  const { data: loanTypes } = useGetLoanTypes();
  const { data: loanAccounts } = useGetMyLoanAccounts();
  const createLoan = useCreateMyLoan();
  const [isApplyOpen, setIsApplyOpen] = useState(searchParams.get("apply") === "1");
  const [gateOpen, setGateOpen] = useState(false);
  const [selectedNumber, setSelectedNumber] = useState<string | null>(null);
  const [selectedRepayNumber, setSelectedRepayNumber] = useState<string | null>(null);

  useEffect(() => {
    if (isApplyOpen && searchParams.get("apply") === "1") setSearchParams({}, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isApplyOpen]);

  useEffect(() => {
    if (me && !me.is_verified && isApplyOpen) {
      setIsApplyOpen(false);
      setGateOpen(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me?.is_verified, isApplyOpen]);

  const openApply = () => {
    if (!isVerified) {
      setGateOpen(true);
      return;
    }
    setIsApplyOpen(true);
  };

  const closeApply = () => setIsApplyOpen(false);

  const openDetail = (number: string) => setSelectedNumber(number);

  const openRepay = (loanNumber: string) => setSelectedRepayNumber(loanNumber);

  const repayAccount = loanAccounts?.find((a) => a.loan_number === selectedRepayNumber);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold">My loans</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Apply for a loan, pay installments and track its progress.
          </p>
        </div>
        <Button text="New application" onClick={openApply} />
      </div>

      {!isVerified && (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/30 dark:text-amber-200">
          <LucideIcon name="Info" size={18} className="mt-0.5 shrink-0" />
          <p>
            Applying for a loan needs a verified account. Verify your phone, add a
            next of kin and upload your ID, passport photo and signature — then staff
            approve you and you can apply.
          </p>
        </div>
      )}

      <EligibilityCard />

      {isLoading ? (
        <SkeletonTable rows={3} />
      ) : loans && loans.length > 0 ? (
        <div className="space-y-3">
          {loans.map((loan) => (
            <LoanCard key={loan.application_number} loan={loan} onOpen={() => openDetail(loan.application_number)} />
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center dark:border-slate-700 dark:bg-slate-900">
          <LucideIcon name="HandCoins" size={40} className="mx-auto text-slate-300 dark:text-slate-600" />
          <h2 className="mt-3 font-display text-lg font-semibold">No loan applications yet</h2>
          <p className="mx-auto mt-1 max-w-sm text-sm text-slate-500 dark:text-slate-400">
            When you apply for a loan it will appear here. Applications are reviewed by staff once submitted.
          </p>
          <Button className="mt-4" text="Apply for your first loan" onClick={openApply} />
        </div>
      )}

      {loanAccounts && loanAccounts.length > 0 && (
        <section>
          <h2 className="mb-3 font-display text-lg font-semibold">Active loans & repayment</h2>
          <div className="space-y-3">
            {loanAccounts.map((account) => (
              <RepayCard key={account.loan_number} account={account} onRepay={() => openRepay(account.loan_number)} />
            ))}
          </div>
        </section>
      )}

      <ApplyLoanModal isOpen={isApplyOpen} onClose={closeApply} loanTypes={loanTypes || []} isSubmitting={createLoan.isPending} onSubmit={async (values) => {
        try {
          const created = await createLoan.mutateAsync(values);
          toast.success("Draft saved. Add guarantors and documents, then submit.", { autoClose: 4000 });
          closeApply();
          setSelectedNumber(created.application_number);
        } catch (error) {
          toast.error(getApiErrorMessage(error, "Could not create the application."));
        }
      }} />

      {selectedNumber && (
        <LoanDetailModal applicationNumber={selectedNumber} onClose={() => setSelectedNumber(null)} />
      )}

      {selectedRepayNumber && repayAccount && (
        <RepayModal
          loanNumber={selectedRepayNumber}
          repaymentSchedule={repayAccount.schedule}
          onClose={() => setSelectedRepayNumber(null)}
        />
      )}

      <VerificationGate
        open={gateOpen}
        onClose={() => setGateOpen(false)}
        message="Applying for a loan needs a verified account. Finish your verification first — confirm your phone, add a next of kin and upload your ID, passport photo and signature."
      />
    </div>
  );
};

const LoanCard = ({ loan, onOpen }: { loan: MyLoanListItem; onOpen: () => void }) => {
  const { formatMoney } = useCurrency();
  const money = (value: string | number | null | undefined) =>
    formatMoney(Number(value || 0), { maxFractionDigits: 0 });
  return (
  <button
    type="button"
    onClick={onOpen}
    className="flex w-full flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5 text-left shadow-card transition hover:border-blue-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-blue-700"
  >
    <div className="flex items-center gap-4">
      <span className={`h-2.5 w-2.5 rounded-full ${STATUS_COLORS[loan.status] ?? "bg-slate-300"}`} />
      <div>
        <p className="font-medium">{loan.loan_type_name}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {loan.application_number} · {new Date(loan.created_at).toLocaleDateString()}
        </p>
      </div>
    </div>
    <div className="flex items-center gap-4">
      <div className="text-right">
        <p className="font-display font-semibold">{money(loan.requested_amount)}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">{loan.repayment_period_months} months</p>
      </div>
      <Badge className={STATUS_STYLES[loan.status] ?? ""}>{STATUS_LABELS[loan.status] ?? loan.status}</Badge>
    </div>
  </button>
  );
};

interface ApplyLoanValues {
  loan_type: number;
  requested_amount: string;
  repayment_period_months: number;
  purpose: string;
  security_type: string;
  employer: string;
  payroll_number: string;
  gross_salary: string;
  net_salary: string;
  collateral_description: string;
  remarks: string;
}

const ApplyLoanModal = ({ isOpen, onClose, loanTypes, isSubmitting, onSubmit }: {
  isOpen: boolean;
  onClose: () => void;
  loanTypes: { id: number; name: string; min_amount: string; max_amount: string; max_term_months: number; repayment_period_months: number }[];
  isSubmitting: boolean;
  onSubmit: (values: ApplyLoanValues) => void;
}) => {
  const { formatMoney, currency } = useCurrency();
  const money = (value: string | number | null | undefined) =>
    formatMoney(Number(value || 0), { maxFractionDigits: 0 });
  const [values, setValues] = useState<ApplyLoanValues>({
    loan_type: 0,
    requested_amount: "",
    repayment_period_months: 12,
    purpose: "",
    security_type: "salary_guarantee",
    employer: "",
    payroll_number: "",
    gross_salary: "",
    net_salary: "",
    collateral_description: "",
    remarks: "",
  });
  const selected = loanTypes.find((t) => t.id === values.loan_type);

  useEffect(() => {
    if (selected) {
      setValues((v) => ({
        ...v,
        repayment_period_months: selected.max_term_months || selected.repayment_period_months || 12,
      }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values.loan_type, loanTypes]);

  if (!isOpen) return null;

  const set = (field: keyof ApplyLoanValues) => (
    e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) => setValues((v) => ({ ...v, [field]: e.target.value }));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!values.loan_type) return toast.error("Choose a loan product.");
    if (!values.requested_amount || Number(values.requested_amount) <= 0)
      return toast.error("Enter the amount you want to borrow.");
    if (!values.purpose.trim()) return toast.error("Tell us what the loan is for.");
    onSubmit(values);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="New loan application">
      <form className="space-y-4" onSubmit={submit}>
        <div>
          <label className="mb-1 block text-sm font-medium">Loan product</label>
          <select
            value={values.loan_type}
            onChange={set("loan_type")}
            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            required
          >
            <option value={0}>Select a loan product…</option>
            {loanTypes.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
          {selected && (
            <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
              {money(selected.min_amount)} – {money(selected.max_amount)} · up to{" "}
              {selected.max_term_months || selected.repayment_period_months} months
            </p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="requested_amount" className="mb-1 block text-sm font-medium">Amount ({currency})</label>
            <input
              id="requested_amount"
              name="requested_amount"
              type="number"
              min="1"
              placeholder="100,000"
              value={values.requested_amount}
              onChange={set("requested_amount")}
              className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </div>
          <div>
            <label htmlFor="repayment_period_months" className="mb-1 block text-sm font-medium">Repayment (months)</label>
            <input
              id="repayment_period_months"
              name="repayment_period_months"
              type="number"
              min="1"
              max={selected?.max_term_months || undefined}
              value={values.repayment_period_months}
              onChange={set("repayment_period_months")}
              className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </div>
        </div>

        <FormInput type="text" label="Purpose of the loan" name="purpose" placeholder="e.g. School fees, farm inputs" value={values.purpose} onChange={set("purpose")} />

        <div>
          <label className="mb-1 block text-sm font-medium">Security type</label>
          <select
            value={values.security_type}
            onChange={set("security_type")}
            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            {SECURITY_TYPES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>

        {values.security_type === "collateral" && (
          <FormInput type="text" label="Collateral description" name="collateral_description" value={values.collateral_description} onChange={set("collateral_description")} placeholder="e.g. Title deed …" />
        )}

        <details className="rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/50">
          <summary className="cursor-pointer text-sm font-medium text-slate-600 dark:text-slate-300">
            Employment details (optional)
          </summary>
          <div className="mt-3 space-y-3">
            <FormInput type="text" label="Employer" name="employer" value={values.employer} onChange={set("employer")} />
            <div className="grid grid-cols-3 gap-3">
              <FormInput type="text" label="Payroll number" name="payroll_number" value={values.payroll_number} onChange={set("payroll_number")} />
              <FormInput type="number" label="Gross salary" name="gross_salary" value={values.gross_salary} onChange={set("gross_salary")} />
              <FormInput type="number" label="Net salary" name="net_salary" value={values.net_salary} onChange={set("net_salary")} />
            </div>
          </div>
        </details>

        <textarea
          className="min-h-20 w-full rounded-lg border border-slate-300 p-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          placeholder="Remarks (optional)"
          value={values.remarks}
          onChange={set("remarks")}
        />

        <div className="flex justify-end gap-2 pt-1">
          <Button text="Cancel" onClick={onClose} />
          <Button text={isSubmitting ? <Spinner /> : "Save draft"} type="submit" variant="primary" disabled={isSubmitting} />
        </div>
      </form>
    </Modal>
  );
};

const LoanDetailModal = ({ applicationNumber, onClose }: { applicationNumber: string; onClose: () => void }) => {
  const { data: loan, isLoading, error } = useGetMyLoan(applicationNumber);
  const submit = useSubmitMyLoan(applicationNumber);
  const addGuarantor = useAddMyGuarantor(applicationNumber);
  const addDocument = useAddMyDocument(applicationNumber);
  const [guarantorNumber, setGuarantorNumber] = useState("");
  const [guaranteedAmount, setGuaranteedAmount] = useState("");
  const [documentType, setDocumentType] = useState(DOCUMENT_TYPES[0]);
  const [file, setFile] = useState<File | null>(null);
  const { formatMoney } = useCurrency();
  const money = (value: string | number | null | undefined) =>
    formatMoney(Number(value || 0), { maxFractionDigits: 0 });

  if (!loan) {
    return (
      <Modal isOpen onClose={onClose} title="Loan application">
        {isLoading ? <SkeletonTable rows={3} /> : <p>{getApiErrorMessage(error, "Application not found.")}</p>}
      </Modal>
    );
  }

  const handleSubmit = async () => {
    try {
      await submit.mutateAsync();
      toast.success("Loan application submitted for review.", { autoClose: 4000 });
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e, "Could not submit the application."));
    }
  };

  const handleAddGuarantor = async () => {
    if (!guarantorNumber.trim() || !guaranteedAmount)
      return toast.error("Enter a membership number and guaranteed amount.");
    try {
      await addGuarantor.mutateAsync({ member: guarantorNumber.trim(), guaranteed_amount: guaranteedAmount });
      setGuarantorNumber(""); setGuaranteedAmount("");
      toast.success("Guarantor added.");
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e, "Unable to add the guarantor."));
    }
  };

  const handleUploadDocument = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) return toast.error("Choose a document to upload.");
    try {
      await addDocument.mutateAsync({ document_type: documentType, file });
      setFile(null);
      toast.success("Document uploaded.");
    } catch (e: unknown) {
      toast.error(getApiErrorMessage(e, "Unable to upload the document."));
    }
  };

  const isDraft = loan.status === "draft";

  return (
    <Modal isOpen onClose={onClose} title={loan.application_number}>
      <div className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="font-display text-lg font-semibold">{loan.loan_type_name}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {money(loan.requested_amount)} · {loan.repayment_period_months} months
            </p>
          </div>
          <Badge className={STATUS_STYLES[loan.status] ?? ""}>{STATUS_LABELS[loan.status] ?? loan.status}</Badge>
        </div>

        <dl className="grid grid-cols-2 gap-2 text-sm">
          <div><dt className="text-slate-500">Purpose</dt><dd>{loan.purpose}</dd></div>
          <div><dt className="text-slate-500">Security</dt><dd className="capitalize">{loan.security_type.replace(/_/g, " ")}</dd></div>
          {loan.collateral_description && <div className="col-span-2"><dt className="text-slate-500">Collateral</dt><dd>{loan.collateral_description}</dd></div>}
          <div><dt className="text-slate-500">Employer</dt><dd>{loan.employer || "—"}</dd></div>
          {loan.gross_salary != null && <div><dt className="text-slate-500">Gross salary</dt><dd>{money(loan.gross_salary)}</dd></div>}
          {loan.approved_amount != null && <div className="col-span-2"><dt className="text-slate-500">Approved amount</dt><dd className="font-medium">{money(loan.approved_amount)}</dd></div>}
        </dl>

        {loan.status === "cancelled" && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-300">
            This application was cancelled{loan.cancelled_at ? ` on ${new Date(loan.cancelled_at).toLocaleDateString()}` : ""}.
            {loan.rejection_reason ? ` Reason: ${loan.rejection_reason}` : ""}
          </div>
        )}

        {loan.eligibility_warnings.length > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            <strong>Eligibility notes</strong>
            <ul className="mt-1 list-disc pl-5">
              {loan.eligibility_warnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          </div>
        )}

        <section>
          <h3 className="mb-2 text-sm font-semibold">Guarantors</h3>
          <div className="space-y-1.5 text-sm">
            {loan.guarantors.length ? loan.guarantors.map((g) => (
              <div key={g.id} className="flex justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
                <span>{g.member_name}</span>
                <span className="font-medium">{money(g.guaranteed_amount)}</span>
              </div>
            )) : <p className="text-slate-500">No guarantors yet.</p>}
          </div>
          {isDraft && (
            <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
              <FormInput type="text" name="guarantor" placeholder="Membership number" value={guarantorNumber} onChange={(e) => setGuarantorNumber(e.target.value)} />
              <FormInput type="number" name="amount" placeholder="Amount" value={guaranteedAmount} onChange={(e) => setGuaranteedAmount(e.target.value)} />
              <button type="button" onClick={handleAddGuarantor} disabled={addGuarantor.isPending} className="col-span-2 rounded-lg bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-60 dark:bg-blue-950/50 dark:text-blue-300 dark:hover:bg-blue-950">
                {addGuarantor.isPending ? "Adding…" : "Add guarantor"}
              </button>
            </div>
          )}
        </section>

        <section>
          <h3 className="mb-2 text-sm font-semibold">Supporting documents</h3>
          <div className="space-y-1.5 text-sm">
            {loan.documents.length ? loan.documents.map((d) => (
              <div key={d.id} className="flex justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
                <a className="text-blue-700 underline dark:text-blue-300" href={d.file} target="_blank" rel="noreferrer">{d.document_type}</a>
              </div>
            )) : <p className="text-slate-500">No documents uploaded.</p>}
          </div>
          {isDraft && (
            <form className="mt-3 grid grid-cols-[1fr_auto] gap-2" onSubmit={handleUploadDocument}>
              <select value={documentType} onChange={(e) => setDocumentType(e.target.value)} className="h-10 rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100">
                {DOCUMENT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <input type="file" className="text-sm text-slate-500 dark:text-slate-400" onChange={(e) => { setFile(e.target.files?.[0] || null); e.currentTarget.value = ""; }} />
              <button type="submit" disabled={addDocument.isPending} className="col-span-2 rounded-lg bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-60 dark:bg-blue-950/50 dark:text-blue-300 dark:hover:bg-blue-950">
                {addDocument.isPending ? "Uploading…" : "Upload document"}
              </button>
            </form>
          )}
        </section>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 dark:border-slate-800">
          <div>
            <Link className="text-sm font-medium text-blue-700 underline dark:text-blue-300" to="/groups">← Back to dashboard</Link>
          </div>
          {isDraft && (
            <Button text={submit.isPending ? <Spinner /> : "Submit for review"} variant="primary" onClick={handleSubmit} disabled={submit.isPending} />
          )}
          {loan.status === "submitted" && (
            <p className="text-sm text-slate-500 dark:text-slate-400">Submitted — awaiting staff review.</p>
          )}
        </div>
      </div>
    </Modal>
  );
};

const EligibilityCard = () => {
  const { formatMoney } = useCurrency();
  const money = (value: string | number | null | undefined) =>
    formatMoney(Number(value || 0), { maxFractionDigits: 0 });
  const { data: eligibility, isLoading } = useGetMyEligibility();
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [amount, setAmount] = useState("");
  const [months, setMonths] = useState("");

  if (isLoading || !eligibility) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
        <h2 className="font-display text-lg font-semibold">Borrowing power</h2>
        {isLoading ? <SkeletonTable rows={2} /> : null}
      </div>
    );
  }

  const eligibleProduct = eligibility.products.find((p) => p.id === selectedProductId) || eligibility.products[0];
  const monthlyRate = Number(eligibleProduct?.interest_rate || 0) / 100 / 12;
  const term = Number(months) || Number(eligibleProduct?.max_term_months) || 12;
  const principal = Number(amount) || Number(eligibleProduct?.eligible_amount) || 0;
  const payment =
    monthlyRate > 0 && principal > 0
      ? (principal * monthlyRate * Math.pow(1 + monthlyRate, term)) / (Math.pow(1 + monthlyRate, term) - 1)
      : term > 0
        ? principal / term
        : 0;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
      <h2 className="flex items-center gap-2 font-display text-lg font-semibold">
        <LucideIcon name="Calculator" size={20} /> Borrowing power calculator
      </h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Based on your savings of {money(eligibility.current_deposits)} and a multiplier of {eligibility.loan_multiplier}×.
      </p>
      {eligibility.warnings.filter(Boolean).length > 0 && (
        <ul className="mt-3 space-y-1 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          {eligibility.warnings.filter(Boolean).map((warning) => (
            <li key={warning?.code}>{warning?.message}</li>
          ))}
        </ul>
      )}
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <div>
          <label className="mb-1 block text-sm font-medium">Loan product</label>
          <select
            value={eligibleProduct?.id ?? ""}
            onChange={(e) => setSelectedProductId(Number(e.target.value))}
            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            {eligibility.products.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">You could borrow</label>
          <input
            type="number"
            min="1"
            value={amount}
            placeholder={`${money(eligibleProduct?.eligible_amount ?? 0)}`}
            onChange={(e) => setAmount(e.target.value)}
            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Months</label>
          <input
            type="number"
            min="1"
            max={eligibleProduct?.max_term_months ?? undefined}
            value={months}
            placeholder={`${eligibleProduct?.max_term_months ?? 12}`}
            onChange={(e) => setMonths(e.target.value)}
            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </div>
      </div>
      {eligibleProduct && (
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
          Indicative maximum: <strong>{money(eligibleProduct.eligible_amount)}</strong> at {eligibleProduct.interest_rate}% {eligibleProduct.interest_type.toLowerCase()} interest.
        </p>
      )}
      {principal > 0 && (
        <p className="mt-2 font-medium text-blue-700 dark:text-blue-300">
          Estimated monthly repayment: {money(payment)} over {term} months
        </p>
      )}
    </div>
  );
};

const RepayCard = ({ account, onRepay }: {
  account: {
    loan_number: string;
    product: string;
    status_display: string;
    outstanding_balance: string;
    outstanding_penalty?: string;
    next_installment?: MyLoanAccount["next_installment"];
    schedule: MyLoanScheduleEntry[];
  };
  onRepay: () => void;
}) => {
  const { formatMoney } = useCurrency();
  const money = (value: string | number | null | undefined) =>
    formatMoney(Number(value || 0), { maxFractionDigits: 0 });
  const nextUnpaid = account.schedule.find((s) => !s.is_paid);
  const next = account.next_installment;
  const hasPenalty = Number(account.outstanding_penalty || 0) > 0;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
      <div>
        <p className="font-medium">{account.product}</p>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {account.loan_number} · {account.status_display}
        </p>
        {hasPenalty && (
          <p className="mt-1 text-xs font-medium text-red-600 dark:text-red-400">
            Includes overdue penalty of {money(account.outstanding_penalty)}
          </p>
        )}
      </div>
      <div className="flex items-center gap-4">
        <div className="text-right">
          <p className="font-display font-semibold">{money(account.outstanding_balance)}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {next
              ? `Next: ${money(next.amount_due)} due ${new Date(next.due_date).toLocaleDateString()}`
              : nextUnpaid
                ? `Next: ${money(nextUnpaid.outstanding_due)} due ${new Date(nextUnpaid.due_date).toLocaleDateString()}`
                : "Fully paid"}
          </p>
        </div>
        {nextUnpaid && (
          <Button text="Repay installment" variant="secondary" onClick={onRepay} />
        )}
      </div>
    </div>
  );
};

const RepayModal = ({ loanNumber, repaymentSchedule, onClose }: {
  loanNumber: string;
  repaymentSchedule: MyLoanScheduleEntry[];
  onClose: () => void;
}) => {
  const { formatMoney } = useCurrency();
  const money = (value: string | number | null | undefined) =>
    formatMoney(Number(value || 0), { maxFractionDigits: 0 });
  const repay = useRepayMyLoan(loanNumber);
  const payoutAccounts = useGetMyAccounts();
  const [installmentNumber, setInstallmentNumber] = useState<number | null>(null);
  const [accountNumber, setAccountNumber] = useState("");

  const repayable = payoutAccounts.data?.accounts ?? [];
  const account = repayable.find((a) => a.account_number === accountNumber);
  const unpaid = repaymentSchedule.filter((s) => !s.is_paid);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!installmentNumber) return toast.error("Choose the installment to repay.");
    if (!accountNumber) return toast.error("Choose the savings account to pay from.");
    try {
      const installment = repaymentSchedule.find((s) => s.installment_number === installmentNumber);
      await repay.mutateAsync({
        account_number: accountNumber,
        installment_number: installmentNumber,
        amount: installment ? installment.outstanding_due : undefined,
      });
      toast.success(`Installment ${installmentNumber} paid from ${account?.product_name ?? accountNumber}.`, { autoClose: 4000 });
      onClose();
    } catch (error) {
      toast.error(getApiErrorMessage(error, "Repayment failed."));
    }
  };

  return (
    <Modal isOpen onClose={onClose} title={`Repay ${loanNumber}`}>
      <form className="space-y-4" onSubmit={submit}>
        <div>
          <label className="mb-1 block text-sm font-medium">Installment to pay</label>
          <select
            value={installmentNumber ?? ""}
            onChange={(e) => setInstallmentNumber(Number(e.target.value))}
            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">Select installment…</option>
            {unpaid.map((s) => (
              <option key={s.id} value={s.installment_number}>
                Installment {s.installment_number} · {money(s.outstanding_due)}
                {Number(s.partially_paid_amount) > 0 ? ` of ${money(s.total_due)}` : ""} · {s.status.replace(/_/g, " ").toLowerCase()}
              </option>
            ))}
          </select>
          {installmentNumber && (
            <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
              The full amount due (including anything left after a partial payment) will be deducted from your savings.
            </p>
          )}
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">Pay from savings account</label>
          <select
            value={accountNumber}
            onChange={(e) => setAccountNumber(e.target.value)}
            className="h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-ink dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="">Select account…</option>
            {repayable.map((a) => (
              <option key={a.account_number} value={a.account_number}>
                {a.product_name} · {a.account_number} · {money(a.balance)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button text="Cancel" onClick={onClose} />
          <Button text={repay.isPending ? <Spinner /> : "Pay installment"} type="submit" variant="primary" disabled={repay.isPending} />
        </div>
      </form>
    </Modal>
  );
};

export default MemberLoans;