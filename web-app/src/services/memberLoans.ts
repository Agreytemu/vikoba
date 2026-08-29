import api from "../lib/api";

export type LoanApplicationStatus =
  | "draft"
  | "submitted"
  | "under_review"
  | "approved"
  | "rejected"
  | "disbursed";

export interface LoanTypeOption {
  id: number;
  name: string;
  interest_rate: string;
  repayment_period_months: number;
  multiplier: string;
  interest_type: string;
  min_amount: string;
  max_amount: string;
  max_term_months: number;
  requires_guarantors: boolean;
  is_active: boolean;
}

export interface MyLoanListItem {
  application_number: string;
  loan_type: number;
  loan_type_name: string;
  requested_amount: string;
  purpose: string;
  repayment_period_months: number;
  status: LoanApplicationStatus;
  status_display: string;
  created_at: string;
  submitted_at?: string | null;
}

export interface MyLoanDetail extends MyLoanListItem {
  member: string;
  member_name: string;
  member_summary: unknown;
  employer?: string;
  payroll_number?: string;
  gross_salary?: string | null;
  net_salary?: string | null;
  security_type: string;
  collateral_description?: string;
  remarks?: string;
  submitted_by?: number | null;
  reviewed_by?: number | null;
  approved_by?: number | null;
  rejected_by?: number | null;
  disbursed_by?: number | null;
  reviewed_at?: string | null;
  approved_at?: string | null;
  rejected_at?: string | null;
  disbursed_at?: string | null;
  approval_notes?: string;
  rejection_reason?: string;
  disbursement_notes?: string;
  eligibility_warnings: string[];
  eligibility_summary: Record<string, unknown>;
  guarantors: MyLoanGuarantor[];
  documents: MyLoanDocument[];
}

export interface MyLoanGuarantor {
  id: number;
  member: string;
  member_name: string;
  guaranteed_amount: string;
  created_at: string;
}

export interface MyLoanDocument {
  id: number;
  document_type: string;
  file: string;
  uploaded_by: number;
  uploaded_by_username: string;
  uploaded_at: string;
}

export interface CreateLoanPayload {
  loan_type: number;
  requested_amount: string;
  purpose: string;
  repayment_period_months: number;
  employer?: string;
  payroll_number?: string;
  gross_salary?: string;
  net_salary?: string;
  security_type?: string;
  collateral_description?: string;
  remarks?: string;
}

export interface AddGuarantorPayload {
  member: string;
  guaranteed_amount: string;
}

export interface AddDocumentPayload {
  document_type: string;
  file: File;
}

export interface MyLoanScheduleEntry {
  id: number;
  installment_number: number;
  due_date: string;
  principal_due: string;
  interest_due: string;
  total_due: string;
  is_paid: boolean;
  paid_at?: string | null;
}

export interface MyLoanAccount {
  loan_number: string;
  product: string;
  interest_rate: string;
  term_months: number;
  approved_at?: string | null;
  disbursed_at?: string | null;
  status: string;
  status_display: string;
  outstanding_principal: string;
  outstanding_interest: string;
  outstanding_balance: string;
  total_repayable: string;
  interest_type: string;
  schedule: MyLoanScheduleEntry[];
  created_at: string;
}

export interface RepayLoanPayload {
  account_number: string;
  installment_number: number;
}

export interface EligibilityProduct {
  id: number;
  name: string;
  interest_rate: string;
  interest_type: string;
  multiplier: string;
  min_amount: string;
  max_amount: string;
  max_term_months: number;
  requires_guarantors: boolean;
  eligible_amount: string;
}

export interface EligibilityWarning {
  code: string;
  message: string;
}

export interface EligibilitySummary {
  membership_date: string;
  membership_months: number;
  current_deposits: string;
  monthly_contribution: string;
  loan_multiplier: string;
  active_loans: number;
  outstanding_balance: string;
  products: EligibilityProduct[];
  warnings: (EligibilityWarning | null)[];
}

export const memberLoansService = {
  listMyLoans: () => api.get("/loans/me/") as Promise<MyLoanListItem[]>,

  getMyLoan: (applicationNumber: string) =>
    api.get(`/loans/me/${applicationNumber}/`) as Promise<MyLoanDetail>,

  createMyLoan: (data: CreateLoanPayload) =>
    api.post("/loans/me/", data) as Promise<MyLoanDetail>,

  submitMyLoan: (applicationNumber: string) =>
    api.post(`/loans/me/${applicationNumber}/submit/`) as Promise<MyLoanDetail>,

  listMyGuarantors: (applicationNumber: string) =>
    api.get(`/loans/me/${applicationNumber}/guarantors/`) as Promise<MyLoanGuarantor[]>,

  addMyGuarantor: (applicationNumber: string, data: AddGuarantorPayload) =>
    api.post(`/loans/me/${applicationNumber}/guarantors/`, data) as Promise<MyLoanGuarantor>,

  removeMyGuarantor: (applicationNumber: string, guarantorId: number) =>
    api.delete(`/loans/me/${applicationNumber}/guarantors/${guarantorId}/`),

  listMyDocuments: (applicationNumber: string) =>
    api.get(`/loans/me/${applicationNumber}/documents/`) as Promise<MyLoanDocument[]>,

  addMyDocument: (applicationNumber: string, data: AddDocumentPayload) => {
    const body = new FormData();
    body.append("document_type", data.document_type);
    body.append("file", data.file);
    return api.post(`/loans/me/${applicationNumber}/documents/`, body) as Promise<MyLoanDocument>;
  },

  removeMyDocument: (applicationNumber: string, documentId: number) =>
    api.delete(`/loans/me/${applicationNumber}/documents/${documentId}/`),

  listLoanTypes: () =>
    api.get("/loan-types/", { params: { is_active: "1" } }) as Promise<LoanTypeOption[]>,

  listMyLoanAccounts: () => api.get("/loans/me/accounts/") as Promise<MyLoanAccount[]>,

  getMyLoanAccount: (loanNumber: string) =>
    api.get(`/loans/me/accounts/${loanNumber}/`) as Promise<MyLoanAccount>,

  repayLoan: (loanNumber: string, data: RepayLoanPayload) =>
    api.post(`/loans/me/accounts/${loanNumber}/repay/`, data) as Promise<MyLoanAccount>,

  getMyEligibility: () =>
    api.get("/loans/me/eligibility/") as Promise<EligibilitySummary>,
};