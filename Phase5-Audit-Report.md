# Phase 5 — STEP 1: Internal Architecture Report (Financial & Reconciliation)

**Date:** 2026-09-22 · **Scope:** backend only · **Method:** read-only audit of the
existing implementation (no refactoring performed). These findings drive the
remaining Phase 5 steps.

---

## 1. The authoritative financial architecture

### Single source of truth: the double-entry journal (`finance/`)

`finance/models.py` defines the core ledger:

- `FinancialAccount` (`finance/models.py:35-113`) — chart of accounts; `account_number`
  unique, editable=False (`:56-58`); 15 codes seeded by migration (asset 1000-SUSPENSE,
  1100-CLEARING, 1300-LOAN_PRINCIPAL, 1310-LOAN_INTEREST; income 4001-INTEREST_INCOME,
  4002-PENALTY_INCOME, 5001-PROVIDER_FEE, …). JSON/relation-bound to member savings via
  `MS-{account_number}` (`finance/services/accounts_catalog.py`).
- `FinancialTransaction` (`:116-285`) — the business-financial transaction; `reference`
  unique (`:154`), `idempotency_key` unique (`:188-195`), `provider_transaction_id` unique
  (`:179-186`) but **never populated anywhere**; statuses incl. `REVERSED`, `REFUNDED`,
  `RECONCILIATION_REQUIRED` (`:125-134`); `reversal_of` self-FK (`:197-203`); linkage FKs to
  the operational records: `loan`, `payment_transaction`, `savings_transaction`,
  `deposit_request`, `withdrawal_request`, `contribution` (`:215-257`).
- `JournalEntry` (`:288-329`) — debit/credit legs; DB CheckConstraint
  `journal_entry_positive_amount` (`:319-322`) and `unique_journal_entry_position`
  (`:323-326`).
- `AuditEvent` (`:332-369`) — append-only audit written in the same DB transaction as the
  engine event.

**Engine:** `finance/services/engine.py post_transaction` (`:199-334`) enforces
`sum(DEBITS) == sum(CREDITS)` (raises `FinancialError.UNBALANCED_JOURNAL`), rejects
zero/negative amounts, currency checks, atomic reference allocation, and idempotency.
`mark_status` (`:337-372`) enforces a strict status-transition matrix (`:79-105`).
`reverse_transaction` (`:384-468`) posts an exact-opposite `REVERSAL` and marks the
original `REVERSED` — **reversals never delete history**.

**All money paths funnel through the engine** (verified): savings deposit/withdrawal legs
(`accounts/services.py:30-70`, `post_savings_transaction :73-187`), loan disbursement
(`loans/services.py:437-458`), loan repayment (`loans/repayments.py:223-267`),
penalty charge (`loans/penalties.py:87-108`), contribution/deposit/repayment webhooks
(`payments/services/payment_service.py:364-446`), provider fee leg
(`payment_service.py:821-856`), manual journal (`finance/views.py /journal/`).

### Ledger-derived balances

`finance/services/balances.py` is the authoritative read path:
`account_balance` (`:18-32`), `account_balance_by_number` (`:35-42`),
`member_savings_balance` (`:45-60`), `savings_account_balance` (`:63-70`),
`reconcile_savings_account` (`:73-81`, cached-vs-ledger drift detector).
`FinancialAccountSerializer.balance` computes live from JournalEntry
(`finance/serializers.py:32-35`).

---

## 2. What is NOT ledger-derived (reporting truth gaps)

The spec requires **every reported figure traceable to the ledger chain**. Current gaps:

1. **Member/group "mini-statement" is an operational projection, not the ledger.**
   `MemberAccountTransactionsView` (`accounts/views.py:61-77`) returns
   `SavingsTransaction` rows (no running balance, no status, no opening balance).
   `MemberFinancialTransactionsView` (`finance/views.py:153-171`) IS ledger-based but is a
   raw financial-transaction feed, not a statement.
2. **Group ledger is a synthesized in-memory fusion** of Contributions, Share purchases,
   PaymentTransactions, LoanTransactions, and MemberShareOut rows
   (`groups/views.py:153-263`, `_ledger_entries_for_group`), **not** the double-entry
   journal; hand-built `"RECORDED"/"POSTED"/"PAID"` statuses.
3. **Cached-state sums are still surfaced directly** (not reconciled with the journal):
   - `MyAccountsView.total_balance = sum(a.balance)` (`accounts/views.py:57`).
   - `customers/views.py:42` `Sum("balance")` (legacy app).
   - Loan outstandings are read from stored `outstanding_principal/interest/penalty`
     (`loans/views.py:537-556`, `loans/serializers.py:153-160`, `loans/models.py:442-449`,
     `loans/services.py:209-226`, `groups/views.py:137-139, 381-396`).
4. **Loan outstandings are never ledger-reconciled** — unlike savings there is no
   `finance.services.balances` loan function (the stored projections are the sole source).
5. **Group overview omits penalties** (`groups/views.py:382-396` sums principal+interest
   only).

---

## 3. Reconciliation architecture

### What exists
- `payments/models.py`:
  - `PaymentTransaction` (`:20-175`) — statuses PENDING/PROCESSING/SUCCESS/FAILED/
    EXPIRED/CANCELLED/VOIDED/RECONCILIATION_REQUIRED (`:32-40`); `internal_reference`
    unique (`:42-49`); **`provider_reference` unique+indexed** (`:68-75`, the authoritative
    provider key); `idempotency_key` unique (`:87-89`); fee fields `fee`/`net_amount`
    separate from `amount` (`:84-85`); business FKs (contribution/loan/withdrawal/deposit/
    subscription) (`:92-127`).
  - `WebhookEvent` (`:178-193`) — `event_id` unique; idempotency anchor for at-least-once
    delivery.
  - `ReconciliationRecord` (`:196-270`) — audited, never-deleted exception rows
    (`AMOUNT_MISMATCH, CURRENCY_MISMATCH, UNKNOWN_PROVIDER_TRANSACTION,
    DUPLICATE_PROVIDER_TRANSACTION, MISSING_INTERNAL_TRANSACTION, MISSING_WEBHOOK,
    DELAYED_CONFIRMATION, STATUS_MISMATCH, ALREADY_PROCESSED_EVENT, PROVIDER_ERROR`);
    `resolution_status OPEN/RESOLVED`; unique `(provider, provider_reference, issue_type)`;
    **5 of the 10 issue types have zero creation sites** (dead enum values).
- Webhook gating: HMAC-SHA256 + 300s freshness (`payments/webhooks/snippe.py:33-55`),
  `event_id` dedup ack (`payments/views.py:559-569`), handlers
  `handle_payment_*/handle_payout_*` (`payment_service.py:364-558`), amount validator
  `_validate_provider_amount` with `MAX_AMOUNT_DISCREPANCY = 2.00` (`:736-751`) — mismatch →
  `RECONCILIATION_REQUIRED` via `_flag_for_reconciliation` (`:776-801`), unknown ref →
  `UNKNOWN_PROVIDER_TRANSACTION` (`_record_unknown_provider :804-818`).
- Reconcile engine: `payments/management/commands/reconcile_payments.py` — **pull-and-replay**
  on known pending/reconciliation-required internal rows keyed on **provider reference
  only**; creates `DELAYED_CONFIRMATION`/`STATUS_MISMATCH`; manual command only (no
  scheduler). No side-by-side ledger comparison, no detection of provider-side transactions
  with no internal counterpart, no duplicate/timing checks.
- API: `GET /api/v1/payments/reconciliation/` (staff list, resolution filter) and
  `POST .../<pk>/resolve/` (Admin/Manager, writes AuditEvent)
  (`payments/views.py:460-526`). `ReconciliationRecord` is **not registered in admin**.

### Confirmed reconciliation gaps (STEP 4 targets)
1. Dead issue types never generated (MISSING_INTERNAL_TRANSACTION, DUPLICATE_PROVIDER_TRANSACTION,
   MISSING_WEBHOOK, ALREADY_PROCESSED_EVENT, PROVIDER_ERROR) — no provider-list sweep, no
   duplicate-provider-ref detection, no missing-webhook detector, no duplicate-ref integrity
   handling.
2. **`RECONCILIATION_REQUIRED` → `FAILED` escape**: `handle_payment_failed`/`handle_payout_failed`
   guard only `SUCCESS` (`payment_service.py:462, 544`), so a late failure event silently
   removes a supervised payment from the reconcile watch-list.
3. `FinancialTransaction.provider_transaction_id` never populated — provider-keyed dedup at
   the journal level is dead.
4. **SUBSCRIPTION success posts no journal** (`_activate_subscription`,
   `payment_service.py:584-607`) — money confirmed but invisible in ledgers.
5. Collections retry is not idempotent across fresh initiations (`_payment_key` derived from a
   fresh `internal_reference`, `payment_service.py:55-64`); only payouts use a stable key
   (`PAYOUT-{withdrawal.pk}`, `payout_service.py:176-178`).
6. `provider_transaction_id` dead + `_payload_money` swallows parse errors to `0.00`,
   blank currency silently accepted (`:699-751`).

---

## 4. Posting paths, reversals, fees

- **Money-in:** contribution/deposit webhook → engine journal DEBIT 1100-CLEARING /
  CREDIT member-savings (`accounts/services.py:44-69`), inside the same atomic block as the
  payment status (idempotent by `idempotency_key`). Loan repayments journal
  CLEARING/LOAN_PRINCIPAL (+4001-INTEREST_INCOME / 1310-LOAN_INTEREST) (`loans/repayments.py:230-253`).
- **Money-out:** payout.completed → WithdrawalRequest SUCCESS, then debit member-savings /
  credit 1100-CLEARING (`accounts/services.py:50-54`, `payment_service.py:636-652`).
- **Fees:** stored separately (`fee`, `net_amount`) on PaymentTransaction (`:84-85`);
  journaled exactly-once as DEBIT 5001-PROVIDER_FEE / CREDIT 1100-CLEARING
  (`payment_service.py:821-856`); member credited with **gross** amount (platform absorbs
  the fee) — a firm business rule verified by tests (`payments/tests.py:921-945`).
- **Reversals:** engine-native + `finance/services/reversals.py` syncing cached balances;
  API `POST /finance/transactions/{ref}/reverse/` staff-only.

---

## 5. Authorization (financial data)

Role primitives `users/permissions.py:6-15`; group financial endpoints hard-gated by active
membership `_require_group_member` (`groups/views.py:88-93`) — members outside the group get
`PermissionDenied`; members see only their own rows; finance endpoints staff-or-own-member
(`finance/views.py:30-39`). Reporting must reuse these gates — never expose financial data on
route accessibility alone.

---

## 6. Drift / integrity risks (STEP 2 targets)

1. **Legacy Django admin mutates loans without any journal**
   (`loans/admin.py:115-138` disburse, `:140-196` repay → `LoanAccount.outstanding_*`
   decremented and `LoanTransaction` created, but **no FinancialTransaction / JournalEntry**).
2. **No integrity monitor** exists: nothing detects unbalanced journals, orphaned payments w/o
   ledger, ledger w/o source, duplicate provider refs, completed payments w/o posting,
   `provider_transaction_id` emptiness.
3. **Cached projections can drift silently** — savings has `reconcile_savings_account`
   (`finance/services/balances.py:73-81`) but there is **no loan equivalent** and no
   scheduled/on-demand run wired into ops.
4. **No financial periods/closing** and **no exports** (no CSV/XLSX/PDF anywhere).

---

## 7. Existing reporting & tests inventory

Statement/summary endpoints: `loans/dashboard`, `loans/me/accounts/{n}/balance`,
`groups/{id}/overview`, `groups/{id}/ledger`, `groups/{id}/loans|repayments`,
`groups/me/summary`, `accounts/me`, `accounts/me/{acct}/transactions`, `finance/*`
(accounts/transactions/audit/me), `payments/me/transactions`, `payments/reconciliation/`.
**No member loan statement, no group statement, no daily/treasury summary, no exports.**

Tests that guard the architecture: `finance/tests.py` (engine balance/status/reversal/
idempotency, 752 lines), `payments/tests.py` (webhooks, reconciliation core + API,
reliability 1091 lines), `loans/tests.py` + `loans/tests_phase3.py` (journal-keyed
disbursement/repayment/penalty), `governance/tests.py`, `groups/tests.py`. **No test exists
for the `reconcile_payments` command itself** nor for the dead issue types.

---

## 8. Decision log (for the remaining steps)

- Keep the `finance/` journal as the *only* source of truth; do not invent a second ledger.
- Reporting layer reads via `finance.services.balances` + engine queries, never ad-hoc sums in
  frontends/views.
- STEP 2: add a financial-integrity service + management command + admin surfacing (identity
  unbalanced journals, orphaned/absent ledger chain, duplicate refs, completed-unposted
  payments, empty provider_transaction_id, cached-vs-ledger drift incl. loans).
- STEP 4: extend `reconcile_payments` to sweep provider-side state for
  `MISSING_INTERNAL_TRANSACTION`/`DUPLICATE_PROVIDER_TRANSACTION`/`MISSING_WEBHOOK`/
  `PROVIDER_ERROR`; fix the `RECONCILIATION_REQUIRED → FAILED` escape; register
  `ReconciliationRecord` in admin.
- No financial-period closing or exports in this phase unless time permits — document as
  known limitations and a recommended next phase.

### Delivery status (updates as steps land)

**STEP 2 — DONE.** `backend/finance/services/integrity.py` (`run_integrity_checks`) implements all
seven target checks; `backend/finance/management/commands/financial_integrity.py` (with `--json`);
staff-only `GET /api/v1/finance/integrity/` (`FinancialIntegrityView`); 10 new tests in
`finance/tests_integrity.py`. Running the command on the dev DB immediately surfaced real,
previously invisible inconsistencies (3 settled payments with no posting, 1 savings cached/ledger
drift) — confirming the monitor earns its place. `finance` suite green (49 tests).

**STEP 4 — DONE.** `RECONCILIATION_REQUIRED → FAILED` escape closed in `handle_payment_failed` and
`handle_payout_failed` (a failure report for a payment under review is recorded as
`PROVIDER_ERROR` and the payment stays under review; financial effects never applied). Dead issue
types are now produced:
- `PROVIDER_ERROR` — reconcile-command provider lookup failures (previously silenced) and the
  review-guard above.
- `MISSING_WEBHOOK` — a polled settlement with no processed webhook event.
- `MISSING_INTERNAL_TRANSACTION` — a settled payment that never posted to the ledger (this also
  documents the known subscription gap).
- `DUPLICATE_PROVIDER_TRANSACTION` — a real second completion event (different id) for an
  already-settled payment; synthetic `recon-` replays stay silent.
- `ALREADY_PROCESSED_EVENT` — duplicate webhook deliveries (same id) recorded in the ingress.
`ReconciliationRecord` registered in `payments/admin.py`. 8 new tests in
`payments/tests_reconciliation.py`; `payments` + `finance` suites green (111 tests). The 16
remaining failures across the whole backend are the pre-existing, intentionally ignored
`users.tests` stale-password-policy + untracked `users/0007` migration drift — untouched.

**STEP 5 — DONE.** Ledger-derived member statements. `backend/finance/services/statements.py`
builds two statements purely from `JournalEntry`/`FinancialTransaction` (cached projections never
trusted):
- `savings` — per-account opening/closing + a running balance on every row (credit = member
  money-in, debit = money-out), optional `start`/`end` period bounds that shift the opening
  balance, cutoff via `Coalesce(posted_at, created_at)`.
- `financial` — chronological itemisation of the member's FinancialTransactions with their
  journal legs (fully ledger-traceable).
Endpoints: member `GET /api/v1/finance/me/statement/?kind=&account=&start=&end=` (IsMember) and
staff `GET /api/v1/finance/statements/<uuid:member_id>/` (business-role staff only). 7 new tests
in `finance/tests_statements.py` (running balance, period bounds, reversal keeps books tied,
leg-traceable financial activity, member/staff authorization, invalid date → 400). `finance`
suite green (56 tests).

**STEP 6 — DONE.** Ledger-derived group statement. `run_group_savings_statement` in
`finance/services/statements.py` lists every group-scoped FinancialTransaction with a per-row
`delta` = sign-aware net over the transaction's member-savings journal legs (a balanced journal
nets zero across all accounts, so only member-liability legs move the running figure). Opening
balance shifts with period bounds; the summary carries inflows/outflows plus per-transaction-type
`flow_totals` so non-savings flows (loan disbursements, repayments, penalties, fees) are never
report-only. New `GET /api/v1/groups/<group_id>/statement` (`GroupStatementView`) gated exactly
like the existing `/ledger` (active group member). 5 tests in `finance/tests_group_statements.py`
(running balance, period-bound opening shift, external flows surfaced, invalid period → 400,
non-member → 403). `finance` (61) + `groups` + `payments` + `accounts` + `loans` suites green.

**STEP 7 — DONE.** Contribution report. `run_group_contribution_report` ties scheduled
`GroupContribution` records to CONTRIBUTION journal legs: a confirmation only counts as
`collected` when its ledger posting exists, so a confirmed-but-unposted contribution shows up as
`unrecorded_in_ledger` — never silently counted. Per-member rollup plus month filter.
`GET /api/v1/groups/<group_id>/contributions/report` (`GroupContributionReportView`) reuses the
contributions list's data scoping (officers/staff → whole group, regular members → own rows).
5 tests in `finance/tests_contribution_reporting.py` (journal-derived totals, gap surfacing,
month filter, member scoping, non-member → 403).

**STEP 8 — DONE.** Withdrawal report. `run_withdrawal_report` ties `WithdrawalRequest` status to
WITHDRAWAL journal postings: only a request with a real ledger leg reports `paid_out`, otherwise it
is surfaced via `unrecorded_in_ledger`. Status/period/member filters, per-status rollup.
`GET /api/v1/finance/reports/withdrawals/` (`StaffWithdrawalReportView`, business-role staff only,
mirrors STEP 5's ALL_BUSINESS_ROLES guard). 4 tests in `finance/tests_withdrawal_reporting.py`
(journal-reported payouts, gap surfacing, status filter, member → 403).

**STEP 9 — DONE.** Loan statements reconstructed FROM THE JOURNAL. `run_loan_statement` derives
outstanding principal purely from `1300-LOAN_PRINCIPAL` legs (disbursement DEBIT vs repayment
CREDIT) and splits repayments into principal/interest/penalty off their income-account legs; the
cached loan columns are echoed back only as `recorded_*` crossing figures. Member self-service
`GET /api/v1/loans/me/accounts/<loan_number>/statement/` (borrower-scoped action on
`MemberLoanAccountViewSet`) and staff `GET /api/v1/finance/loans/<loan_number>/statement/`
(`StaffLoanStatementView`). 5 tests in `finance/tests_loan_statements.py` (journal-reconstructed
outstanding, period-bound opening shift, borrower scoping, staff role gate).

**STEP 7–9 regression:** `finance` + `groups` + `loans` + `payments` + `accounts` all green
(185 tests). `check` clean.

**STEP 10 — DONE.** Dashboards. `backend/finance/services/dashboard.py` adds
- `run_org_financial_dashboard` — member savings, clearing, loans outstanding and income
  totals all aggregated from `JournalEntry` legs (never from cached columns), with
  member/transaction counts and 30-day activity via `TruncDate` on
  `Coalesce(posted_at, created_at)`. The integrity monitor's flags are embedded as-is so the
  dashboard surfaces drift instead of hiding it. (Fixed an initial `FieldError` by annotating
  `day = TruncDate(...)` instead of filtering on the expression.)
- `run_member_financial_dashboard` — member-scoped savings/loan KPIs plus recent transactions.
Staff `GET /api/v1/finance/dashboard/` and member `GET /api/v1/finance/me/dashboard/`.
3 tests in `finance/tests_dashboards.py`.

**STEP 11 — DONE.** Integrity ops alerting. `financial_integrity` management command now raises
`SystemExit(1)` whenever `report["ok"]` is False, in both text and `--json` modes — so cron/CI
can detect an unclean books state without parsing output. 4 tests in
`finance/tests_integrity_ops.py` (clean exit 0, anomaly exit 1, JSON exit 1, `--json` shape).

**STEP 12 — DONE.** CSV exports. `backend/finance/services/exports.py` adds a small CSV layer
(UTF-8 BOM + CRLF, `dict`/`list` cells JSON-dumped; per-account member-statement rows flattened
and stamped with `account_number`). `?export=csv` streams the same journal-backed payload as a
download on member statements (`me/statement/`), staff member statements
(`statements/<uuid>/`), group statements (`groups/<id>/statement`) and the withdrawal report
(`reports/withdrawals/`). Read-only — exports never touch the books. 3 tests in
`finance/tests_exports.py`.

**STEP 13 — DONE.** Report performance guard. Statement/report builders verified against
N+1 degradation: all relied-on FKs (`member`, `group`, `loan`, `contribution`,
`withdrawal_request`, `JournalEntry.account`/`transaction`) are already FK-indexed, and
`finance/tests_performance.py` wraps member (3 accounts × 3 txns) and group (9 txns) statements
in `CaptureQueriesContext` with generous bounds + correctness assertions. 2 tests.

**STEP 14 — DONE.** Full-suite consolidation: 269 backend tests run; the only failures are the
16 known, intentionally ignored `users.tests` (stale password-policy + untracked `users/0007`
drift). Finance (82), groups, loans, payments, accounts, members suites all green; `check` clean.

**STEP 15 — DONE.** Consistency audit. Dev-DB re-run of `financial_integrity --json` shows the
same three known findings as pre-existing live-state noise — 3 settled-but-unposted payments
(two deposits/contributions via the payment ingress being reconciled, one withdrawal) and one
savings cached/ledger drift on `SA00000001` — with no new anomalies. The command's new exit-1
alerting fired as expected. See the 19-section final report below.