# Phase 5 — Final Report (Financial Reporting & Reconciliation)

**Date:** 2026-09-22 · **Scope:** backend only · **Status:** COMPLETE (STEPs 1–15)

This report closes out Phase 5. Every figure exposed by the new reporting surface is derived
from the double-entry journal (`finance/`); the operational/cached projections are only ever
echoed as crossing references. Details and line references for the architecture live in
`Phase5-Audit-Report.md` (the STEP 1 deliverable); this document records what was built, what
the audit found, and the resulting state.

---

## 1. Scope and method

Read-only audit drive -> build. Work started with a STEP 1 internal architecture report of the
existing ledger, engines, posting paths, reconciliation service and test inventory. Each
following step added a ledger-derived reporting or reconciliation capability with its own tests;
steps never modified the books. Only the dev SQLite database was inspected (never mutated for
audit). Nothing was committed.

## 2. The authoritative financial architecture

- `finance.models`: `FinancialAccount` (chart of accounts, `account_number` unique and frozen),
  `FinancialTransaction` (`reference`/`idempotency_key`/`provider_transaction_id` unique; status
  machine incl. `RECONCILIATION_REQUIRED`, `REVERSED`, `REFUNDED`, `REVERSAL`; linkage FKs to
  loan/payment/savings/contribution records), `JournalEntry` (signed debit/credit legs with
  positive-amount and unique-position constraints), `AuditEvent` (append-only, same-transaction).
- `finance.services.engine.post_transaction`: one chokepoint enforcing balanced journals,
  positive amounts, currency checks, atomic reference allocation and idempotency. Reversals post
  an exact opposite journal and move the original to `REVERSED` — history is never deleted.
- _Every money path verified to funnel through the engine_ (savings deposit/withdrawal, loan
  disbursement/repayment/penalty, payment webhooks, provider fee leg, manual journal).

## 3. STEP 2 — Integrity monitor (findings)

`finance/services/integrity.py run_integrity_checks` + `financial_integrity` management command
(`--json`) + staff endpoint `GET /api/v1/finance/integrity/`. Checks: unbalanced journals,
transactions-without-entries, completed-payments-unposted, savings & loan cached/ledger drift,
duplicate provider references, unset `provider_transaction_id`. One run on the dev DB
immediately surfaced **3 settled payments with no posting** and **1 savings cached/ledger drift**
that no other surface had exposed. (10 tests.)

## 4. STEP 4 — Reconciliation (findings)

Extended `reconcile_payments` to produce the previously-silent issue types and closed the
`RECONCILIATION_REQUIRED → FAILED` escape: a failure report on a payment under review is recorded
as `PROVIDER_ERROR` and the payment stays under review; financial effects are never applied from
it. New dead-listing: `MISSING_INTERNAL_TRANSACTION`, `MISSING_WEBHOOK`,
`DUPLICATE_PROVIDER_TRANSACTION`, `ALREADY_PROCESSED_EVENT`. `ReconciliationRecord` registered in
admin. (8 tests.)

## 5. Member statements (STEP 5)

`finance/services/statements.py`: `run_member_statement(savings|financial)`.
- `savings` — per-account opening/closing and a per-row running balance; optional period bounds
  shift the opening balance; cutoff on `Coalesce(posted_at, created_at)`.
- `financial` — chronological leg-traceable itemisation of the member's transactions.
Endpoints: member `GET /api/v1/finance/me/statement/?kind=&account=&start=&end=` and staff
`GET /api/v1/finance/statements/<uuid:member_id>/`. (7 tests.)

## 6. Group statements (STEP 6)

`run_group_savings_statement` lists group-scoped transactions with per-row `delta` = sign-aware
net over member-savings legs (balanced journals net zero, so only member-liability legs move the
running figure), period-bound opening shift, and `flow_totals` that surface non-savings flows
(disbursements, repayments, penalties, fees). Endpoint `GET /api/v1/groups/<group_id>/statement`,
gated like the existing `/ledger`. (5 tests.)

## 7. Contribution reporting (STEP 7)

`run_group_contribution_report` ties scheduled `GroupContribution` records to CONTRIBUTION
journal legs — a confirmation only counts `collected` when its posting exists, otherwise it is
surfaced as `unrecorded_in_ledger`. Per-member rollup + month filter.
`GET /api/v1/groups/<group_id>/contributions/report`. (5 tests.)

## 8. Withdrawal reporting (STEP 8)

`run_withdrawal_report` ties `WithdrawalRequest` status to WITHDRAWAL journal postings; only a
ledger-posted request reports `paid_out`. Status/period/member filters + per-status rollup.
Staff `GET /api/v1/finance/reports/withdrawals/` (business-role staff only). (4 tests.)

## 9. Loan statements (STEP 9)

`run_loan_statement` reconstructs outstanding **purely from `1300-LOAN_PRINCIPAL` legs**
(disbursement DEBIT vs repayment CREDIT) and splits repayments into principal/interest/penalty
off their income-account legs; cached loan columns are echoed only as `recorded_*`. Member
`GET /api/v1/loans/me/accounts/<loan_number>/statement/` (borrower-scoped) and staff
`GET /api/v1/finance/loans/<loan_number>/statement/`. (5 tests.)

## 10. Dashboards (STEP 10)

`finance/services/dashboard.py`: `run_org_financial_dashboard` aggregates member savings,
clearing, loans outstanding and income from `JournalEntry` legs (never cached columns) with
30-day activity via `TruncDate`, embedding the integrity monitor's flags so drift surfaces
instead of hiding; `run_member_financial_dashboard` is member-scoped. Staff
`/api/v1/finance/dashboard/`, member `/api/v1/finance/me/dashboard/`. (3 tests.)

## 11. Integrity ops wiring (STEP 11)

`financial_integrity` now exits `SystemExit(1)` whenever the report's `ok` is False — in text and
`--json` modes — so CI/cron can alert on unean books without parsing. (4 tests.)

## 12. Exports (STEP 12)

`finance/services/exports.py`: UTF-8-BOM + CRLF CSV; `dict`/`list` cells JSON-dumped; per-account
member-statement rows flattened and stamped with `account_number`. `?export=csv` streams the same
journal-backed payload as a download on `me/statement/`, staff `statements/<uuid>/`, group
`statement`, and `reports/withdrawals/`. Read-only. (3 tests.)

## 13. Performance (STEP 13)

All FKs the reports filter/order by are already FK-indexed (`member`, `group`, `loan`,
`contribution`, `withdrawal_request`, `JournalEntry.account`/`transaction`).
`finance/tests_performance.py` guards member (3 accounts × 3 txns) and group (9 txns) statement
builds with `CaptureQueriesContext` + correctness assertions to catch any future N+1 regression.
`Coalesce(posted_at, created_at)` ordering is not covered by an index (expression) — acceptable
at current scale; flagged in §17.

## 14. Test results (STEP 14)

Full backend sweep: **269 tests**. Failures: 16, all in `users.tests` — the documented,
intentionally ignored stale password-policy + untracked `users/0007` migration drift. Finance
(82 tests), groups, loans, payments, accounts, members all green. `manage.py check` clean.

## 15. Consistency audit (STEP 15)

Re-ran `financial_integrity --json` on the dev DB: no new anomalies; the three known findings
persist (§17). Verified every report endpoint derives purely from journal legs; cached columns
only cross-reference. Command exit code was 1 (alerting path exercised).

## 16. Pre-existing deviations (intentionally ignored)

- `users/tests.py` stale password-policy + email-flow expectations and the untracked
  `users/0007_*` migration (makemigrations drift) fail by design.
- Not addressed this phase: financial-period locking / closing, exports beyond CSV (XLSX/PDF),
  and `provider_transaction_id` backfill — recommended next phase.

## 17. Live dev-DB state (known, real)

Findings the monitor keeps surfacing (pre-existing, not created by Phase 5):
- 3 settled payments with no posting (deposits/contribution/withdrawal replayed by the provider
  ingress, awaiting reconciliation posting).
- 1 savings cached/ledger drift on `SA00000001` (cached 100172.68 vs ledger 36672.68).
These are the exact signals Phase 5 was built to surface; reconciliation (`reconcile_payments`)
and integrity ops handle them operationally. No unbalanced journals, no orphaned ledger chains,
no duplicate provider references, no loan drift.

## 18. Recommendations

- Operationalize `financial_integrity` (cron + exit-code alerting) now that it alerts on the
  dev-DB findings.
- Post the 3 settled un-posted payments and reconcile `SA00000001` against the journal in dev.
- Next phase: period lock/close, XLSX/PDF exports, `provider_transaction_id` backfill,
  expression-index for statement ordering at scale.
- Keep reports journal-derived; never trust cached balance columns for reporting.

## 19. Sign-off

Phase 5 spec implemented in order (STEP 1 audit through STEP 15 consistency audit), every step
test-covered and regression-swept, the ledger remains the single source of truth, and the final
audit shows only the known, documented pre-existing dev-DB anomalies. Backend unchanged beyond
Phase 5's own diff; frontend untouched. Nothing committed.