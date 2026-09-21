# Phase 4 — Governance & Approval Engine (Technical Report)

## What was built

A reusable **governance & approval engine** for VICOBA financial actions, first
applied to withdrawals (auto-approval with manual-review exceptions) and wired
as a read-only observation layer for loans. Engine + withdrawal flow + loan
observations are all on the Django backend; the web frontend gained an officer
approvals workspace, an audit timeline, and a per-group withdrawal-policy editor.

It reuses the existing Phase 1 double-entry ledger and the Phase 2 Snippe payout
engine — **no second money engine** was introduced. Nothing from phases 1–3 was
rewritten; they were extended at integration points only.

## Backend

New app `backend/governance/`:

| File | Responsibility |
| --- | --- |
| `models.py` | `GroupWithdrawalPolicy`, `ApprovalRequest`, `ApprovalStep`, `ApprovalAction` (append-only audit), policy-change audit rows (`request` FK nullable) |
| `errors.py` | Stable machine-readable error codes |
| `policy.py` | Deterministic, explainable `evaluate_withdrawal()` → `AUTO_APPROVED` / `MANUAL_REVIEW` / `REJECTED` with `rules_passed` + first-failed-rule; platform defaults merge over group overrides |
| `workflow.py` | `create_request`, `approve`, `reject`, `cancel`, `expire`, `execute` + `can_review` (role/committee + no self-approval + SoD); expiry via `_expire_guard` outside the atomic block |
| `withdrawals.py` | `submit_withdrawal`, `request_for`, `sync_withdrawal_outcome` reservation-aware helpers |
| `loans.py` | `record_loan_decision` adapter |
| `serializers.py` | Inbox/detail/history/policy serializers incl. `can_act`, `can_cancel`, `is_requester` |
| `views.py`, `urls.py`, `admin.py` | REST endpoints + admin |
| `tests.py` | 27 tests |
| `migrations/0001_initial.py` | Initial schema |

### Endpoints (`/api/v1/governance/`)
- `GET approvals/` – officer/committee inbox (filters `type`, `status` comma-list, `group`)
- `GET approvals/<id>/` – detail incl. withdrawal context + decision flags
- `POST approvals/<id>/action/` – `{action: approve|reject|cancel, reason}`
- `GET approvals/<id>/history/` – append-only audit trail
- `GET|PUT groups/<id>/withdrawal-policy/` – committee/staff policy editor

### Withdrawal integration
- `Subjecture` → replaced: `MemberWithdrawalRequestView.create` and
  `AutoWithdrawalView` now both call `submit_withdrawal` from
  `governance.withdrawals`, returning `decision`, `decision_reason`,
  `review_required`, `approval_id` (201 when auto, 202 when manual review).
- Single-approval path: human officer approves → engine executes → payout
  dispatched → `SENT_TO_SNIPPE`; **no immediate debit** (the old dual-debit bug
  is gone — debit happens only after the webhook confirms payout).
- Payout webhooks (`payment_service`) sync the approval back: completed →
  withdrawal `SUCCESS` + ledger debit; failed → withdrawal `FAILED` + best-effort
  approval `FAILED`.

### Loan integration
- `loans/services.approve_application`, `loans/views` reject/cancel record a
  best-effort `LOAN` approval — transparent, never blocks the loan flow.

### Settings
`WITHDRAWAL_AUTO_LIMIT_TZS`, `WITHDRAWAL_MAX_LIMIT_TZS`,
`WITHDRAWAL_MIN_AMOUNT_TZS`, `WITHDRAWAL_MIN_RETAINED_RATIO`,
`WITHDRAWAL_POLICY_VERSION="platform-default-v1"`,
`GOVERNANCE_OFFICER_ROLES=("AD","MA","OP","FI","AC")`, `APPROVAL_EXPIRY_HOURS=72`.

### Validation
- `manage.py check` → **0 issues**
- `governance.tests` → **27/27 pass** (auto-approve above/below payout minimum,
  manual-review routing, insufficient balance + reservation/double-spend, reject
  and cancel releasing reservations, max-limit rejection, SoD, unauthorized
  member, duplicate two-level approval block, two-level step sequencing, expiry,
  frequency rules, platform defaults, inbox visibility, cross-group 404,
  action/unauthorized-action codes, append-only history, policy GET/PUT + audit +
  member 403, loan adapter)
- Full regression `accounts finance groups payments loans` → **141/141 pass**
- **Total: 168 tests green**

## Frontend (`web-app`)

- `src/services/governance.ts` + `src/hooks/api/governance.ts` – typed React Query
  layer (list/detail/action/history/policy GET+PUT).
- `src/pages/governance/Approvals.tsx` – officer workspace: **Inbox / History /
  Group policies** tabs, type + status filters, pending-count badges, decision
  buttons, error/empty/loading states.
- `src/components/governance/ApprovalDetailModal.tsx` – full drill-down: amount,
  requester, group, required role, policy version, deadline, withdrawal context
  (reference/member/account/network/balance), approval chain steps, checks
  passed, **append-only audit timeline**, and approve/reject/cancel with reason.
- `src/components/governance/GroupWithdrawalPolicies.tsx` – per-group policy
  editor (limits, weekly/monthly frequency, retained %, review levels +
  reviewer role, outstanding-loan/penalty triggers) with effective-default
  summary.
- `src/components/governance/ApprovalTimeline.tsx` – reusable timeline.
- Access: added `governance` to `AppModule`/`moduleAccess`
  (`AD/MA/OP/FI/AC`), new `Approvals` nav item, route
  `protectedModulePage("governance", ...)`, `nav.approvals` locale key.
- `Withdraw.tsx` handles `review_required: true` (202) → "Submitted for approval"
  state instead of crashing on a missing `payout.reference`; `review` stage added
  to `WithdrawStage`.

### Validation
- `npx tsc --noEmit` → clean
- `npm run lint` → clean (0 warnings)

## Notes / known gaps
- Committee members (role `ME` with a committee office) are authorized by the
  backend but the app nav only exposes Approvals to platform officers; they can
  still use the API/URLs. A future nav entry can extend this.
- Platform defaults are env-driven; per-group overrides live in
  `GroupWithdrawalPolicy` and inherit via `effective_values`.
- Nothing committed; work-in-progress on dev SQLite.