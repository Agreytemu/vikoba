# Phase 6 — Final Report (KYC + Member Identity + Verification Engine)

**Date:** 2026-09-23 · **Scope:** backend only · **Status:** COMPLETE (STEPs 1–15)

This report closes out Phase 6. KYC is a **separate trust layer** from authentication, group
membership and financial authorization: it produces trusted identity status that the withdrawal
and loan engines consume via configurable per-group policy levels. The design rationale and
line-level field inventory live in `Phase6-Audit-Report.md` (the STEP 1 deliverable); this
document records what was built, the audit findings, the integration points, and the resulting
state.

---

## 1. Existing identity / authentication / member architecture (STEPs 1–2)

Audit (three parallel explore passes + direct reads) of `users`, `members`, `groups`,
`accounts`, `governance`, `payments`, `loans`, `finance` and the SPA:

- **User vs Member are distinct.** `users.User` (auth + `role`) OneToOnes to
  `members.Member` (identity + `is_verified` + `registration_source`) which OneToOnes to
  `accounts.SavingsAccount` and memberships to `groups.VikobaGroup`.
- **Legacy "verified" is a plain boolean.** `Member.is_verified` was set optimistically at
  registration/payment and consumed by `governance/withdrawals.py` and `payments/views.py`
  (with `phone_verified`). There was no per-member identity state machine, no provider
  outcome record, no verification level, no expiry — and the `MeMemberSerializer` exposed
  only the raw flag.
- **Where the flag gate lived:** withdrawal submission, auto-withdrawal dispatch, loan
  eligibility, loan submit. So a stale `is_verified=True` was enough to pass every identity
  gate. That is the gap Phase 6 closes.
- **No third-party identity provider is configured** anywhere (`settings.py` had no
  KYC/NIDA block). No credentials exist — the provider layer must therefore be pluggable and
  fail closed by default.

## 2. KYC architecture (STEPs 3–8)

New `kyc` Django app. Three concerns, kept separate (retention-friendly):

- **`KYCProfile`** (one per member; `member` is the PK) — the member's *current* state:
  `status`, `verification_level`, `verification_method`, `provider` +
  `provider_reference`, `failure_code/reason`, `verified_at`, `expires_at`.
- **`KYCVerificationRequest`** — one idempotent verification flow; doubles as the stored
  structured *result* of that attempt (provider, reference, outcome, match flags, failure
  code, attempt accounting). DB constraint `kyc_request_single_active` enforces one in-flight
  request per member. Bounded retries (`KYC_MAX_ATTEMPTS`, default 3).
- **`KYCEvent`** — append-only audit/observability trail (request-initiated, provider
  response, retries, errors, manual review, expiry).
- **`kyc/statuses.py`** — `KYCStatus` (NOT_STARTED, PENDING, IN_REVIEW, VERIFIED,
  REQUIRES_UPDATE, REJECTED, EXPIRED, PROVIDER_ERROR), `KYCLevel`
  (LEVEL_0/1/2), `KYCVerificationMethod`, and an explicit `TRANSITIONS` table
  (including `NOT_STARTED → VERIFIED` for the legacy sync path and `NOT_STARTED →
  REJECTED/REQUIRES_UPDATE` for provider outcomes). The service layer is the only authority
  that may move a profile; a forged frontend `{"status": "VERIFIED"}` is impossible (the
  serializer is read-only).

**State machine summary**

```
NOT_STARTED ──submit──▶ PENDING ──provider──▶ VERIFIED
     │                      │                    │
     ├─▶ PROVIDER_ERROR ◀───┤ (retryable, bounded)
     ├─▶ REJECTED ──────────┤ (terminal until manual review reopens)
     ├─▶ REQUIRES_UPDATE ───┤
     └─▶ VERIFIED (legacy is_verified sync / manual approve)
VERIFIED ──expiry──▶ EXPIRED ──re-verify──▶ PENDING
```

**Provider layer (`kyc/providers/`)** — `ProviderAdapter` ABC with a `ProviderOutcome`
(success/rejected/pending/error scheme), `SimulatedKYCProvider`, and `get_provider()` that
**fails closed**: no provider, or any mode other than `simulated`, yields `PROVIDER_ERROR` —
never verification. A real NIDA adapter (see §18) slots in by implementing the ABC.

**API surface** (7 routes, `backend/urls.py` already includes `kyc.urls`):

- `GET  /api/v1/kyc/me/` — own profile + masked identity summary.
- `POST /api/v1/kyc/me/verify/` — submit idempotent verification (throttled `kyc-submit`).
- `GET  /api/v1/kyc/me/requests/` and `GET /api/v1/kyc/me/timeline/`.
- `GET  /api/v1/kyc/admin/` and `GET /api/v1/kyc/admin/<membership_number>/` — business-role
  staff only.
- `POST /api/v1/kyc/admin/<membership_number>/review/` — approve/reject/request_update with a
  mandatory reason, fully audited.

**Admin/ops**: read-mostly `kyc/admin.py` (`KYCEventAdmin` has no add/change/delete) and the
`backfill_kyc_profiles` management command (idempotent; see §15).

## 3. Verification levels and configurable gates

- Levels `LEVEL_0` (none) → `LEVEL_1` (identity verified) → `LEVEL_2` (verified + review
  depth, reserved). `kyc_services.satisfies(member, level)` defaults to platform
  `KYC_REQUIRED_LEVEL` (`LEVEL_1`) when no group policy overrides it.
- **`GroupWithdrawalPolicy.kyc_level_required`** and **`GroupLoanPolicy.kyc_level_required`**
  are nullable; `effective_values` (governance/policy.py `_platform_kyc_level`,
  loans/policies.py `_default_kyc_level`) resolve `None` → platform default. So a group can
  demand LEVEL_2 while the platform floor stays LEVEL_1 — additive, non-breaking.
- KYC is **member-scoped, not group-scoped**: one user has one KYC profile; every group with a
  KYC gate consumes that same profile at the group's required level.

## 4. Provider + NIDA integration status

- **`SimulatedKYCProvider`** (only under `KYC_PROVIDER_MODE=simulated`, the test/dev mode):
  references are `SIM-KYC-…`; ID ending `666` → REJECTED IDENTITY_MISMATCH; all-zeros →
  ERROR PROVIDER_UNAVAILABLE; structurally invalid ID → REJECTED; anything well-formed →
  VERIFIED.
- **Default `KYC_PROVIDER_MODE=disabled` fails closed** — without a configured provider,
  `submit_verification` records PROVIDER_ERROR and never verifies. **No real NIDA adapter or
  credentials ship in this phase** (none are authorized); the ABC + simulated adapter + `.env`
  wiring are the integration seam. See §18.

## 5. DB and settings changes

- Migrations: `kyc/0001_initial` (profiles/requests/events + unique active-request
  constraint), `governance/0002_groupwithdrawalpolicy_kyc_level_required`,
  `loans/0008_grouploanpolicy_kyc_level_required`. `manage.py migrate` applied; `manage.py
  check` clean; no KYC-related `makemigrations --check` drift (only the pre-existing, ignored
  `users/0007`).
- Settings (`backend/settings.py`): `kyc.apps.KYCConfig` in `INSTALLED_APPS`, `KYC_PROVIDER`,
  `KYC_PROVIDER_MODE`, `KYC_REQUIRED_LEVEL`, `KYC_VERIFICATION_EXPIRY_DAYS`,
  `KYC_MAX_ATTEMPTS` (+ `ImproperlyConfigured` guard), throttle `kyc-submit: 10/min`.

## 6. Withdrawal integration

- `governance/policy.py` `evaluate_withdrawal` resolves `kyc_level_required` through
  `effective_values` and enforces it via the shared `_kyc_satisfied` helper; failure surfaces
  as `PolicyDecision(code=ApprovalError.KYC_REQUIRED)` with `required_level` metadata in the
  decision, enforcement metadata, the approval workflow metadata and the member notice.
- `governance/withdrawals.py` pre-raises with both checks kept: the legacy
  `member.is_verified` boolean AND `kyc_services.satisfies(member, policy_level)`.
- `accounts/views.py` withdrawal pre-check and `payments/views.py` AutoWithdrawalView add
  `kyc_services.satisfies(...)` after the existing checks; provider failure is never treated
  as approval (PROVIDER_ERROR status does not satisfy).

## 7. Loan integration

- `loans/eligibility.py` `check_eligibility` has a blocking KYC rule on the group loan
  policy's `kyc_level_required` (resolved via `loans/policies.py effective_values`
  `_default_kyc_level`).
- `loans/views.py` loan-submit gate adds `kyc_services.satisfies(member, level)`, and
  `governance/serializers.py` exposes the field + its effective value so the SPA can show the
  requirement.

## 8. Member, accounts, payments integration

- `Member.refresh_verification()` now sets `is_verified` AND calls
  `kyc_services.sync_from_member(self)` when the flag changed — the legacy pipeline keeps
  working while every verifed member gets a profile.
- `kyc/services.get_or_create_profile` lazily syncs a legacy `is_verified=True` member into a
  VERIFIED profile on first touch; `sync_from_member` uses `get_or_create` directly (no
  recursion into the same path).
- `MeMemberSerializer` exposes a read-only `kyc` summary (`current_status`) for the SPA.

## 9. Security (STEP 13)

- **Backend-only status control** — service-layer transitions only; test proves a client
  cannot change status by any payload/serializer path.
- **Member isolation / role gating** — a member can never read another member's KYC; admin
  endpoints require a business role.
- **Masking** — national IDs keep only the last 4 characters; provider references keep 6;
  serializers never return raw identity; raw provider payloads are never stored.
- **Throttling** — `POST /kyc/me/verify/` is `ScopedRateThrottle` `kyc-submit` (10/min);
  a dedicated rate-limit test asserts 429 on burst.
- **Fail-closed provider** — no provider / unsupported mode ⇒ PROVIDER_ERROR, never VERIFIED;
  provider failures are distinct from identity rejection (PROVIDER_ERROR ≠ REJECTED) and
  never grant withdrawal approval or loan eligibility (integration tests assert this).
- **Idempotency** — one active request per member (DB constraint) and keyed requests prevent
  duplicate provider submissions.

## 10. Observability and audit (KYCEvent)

Every transition from the provider path and every manual review writes an append-only
`KYCEvent` (actor for reviews, system for the engine), same-transaction. `KYCEventAdmin` is
read-only; the member timeline endpoint exposes the trail to the owner.

## 11. Frontend changes

- **None in this phase.** The SPA remains untouched (consistent with prior phases; Phase 6 was
  scoped backend-only). The read-only `kyc` field on `MeMemberSerializer` and the 7 endpoints
  are the integration surface for a later frontend step.

## 12. Test results (STEP 14)

- `kyc/tests.py` — **36 tests, all passing** (identity/sync/satisfies; provider
  success/reject/error/idempotency/active-request constraint/bounded retry/expiry; disabled
  fail-closed; manual review incl. reject-then-approve and request-update; API security —
  isolation, role gating, forged-status impossibility, masking, rate limiting; financial
  integration — withdrawal gate, verified auto-approve, loan eligibility block/pass, LEVEL_2
  policy overrides, provider failure never grants approval).
- Full Phase 6 regression sweep (kyc + governance + loans + accounts + payments + members +
  finance + groups): **269 tests green**. The only failing line in the sweep was the
  deliberate pre-existing, ignored `users.tests` drift (documented in §15). `manage.py check`
  clean.
- Legacy Phase 3 loan/approval tests were updated to fixture KYC-verified members
  (`loans/tests.py`, `loans/tests_phase3.py`) since the new hard gate legitimately requires
  KYC before approval.

## 13. Consistency audit (STEP 15)

- Re-audited every identity and financial-access path: withdrawal submission, auto-withdrawal,
  loan eligibility, loan submit, member serializer. All now route through
  `kyc_services.satisfies` in addition to the legacy boolean.
- `manage.py check` — clean; `makemigrations --check` — no KYC-related drift (only the known,
  ignored `users/0007`).
- Backfill + sanity check on dev DB: idempotent, `0 member(s) synced; 3 already VERIFIED or
  remain NOT_STARTED`; all three dev members are honestly `NOT_STARTED` (no legacy-verified
  members to migrate). KYC never touches the ledger (verified by design: no KYC code imports
  finance/payments).

## 14. Pre-existing deviations (intentionally ignored)

- `users/tests.py` stale password-policy + email-flow expectations and the untracked
  `users/0007_*` migration (makemigrations drift) fail by design — untouched.
- Not addressed this phase: a real NIDA adapter, KYC document upload/storage, LEVEL_2 materials
  flow, and frontend KYC screens — recommended next phase (§17).

## 15. Live dev-DB state (known, real)

- Migrations applied to dev SQLite (`kyc/0001`, `governance/0002`, `loans/0008`).
- `backfill_kyc_profiles` ran idempotently: no legacy members needed syncing; all 3 profiles
  are `NOT_STARTED`/`LEVEL_0` (correct — nothing verified yet).
- The pre-existing Phase 5 dev-DB findings (3 settled un-posted payments, 1 savings drift)
  remain and are operational reconciliation work, not Phase 6 deliverables.

## 16. Security verification matrix (STEP 13 recap)

| Claim | Test |
|---|---|
| Forged `{"status":"VERIFIED"}` payload does nothing | `test_forged_status_is_impossible` |
| Member cannot read another member's KYC | `test_member_cannot_read_another_member_kyc` |
| Admin endpoints need business role | `test_admin_requires_business_role` |
| Provider failure never grants approval/loan | `test_*` in KYCFinancialIntegrationTests |
| National ID / provider ref masked | serializer masking assertions |
| Verify endpoint rate-limited | `test_verify_endpoint_is_rate_limited` (429) |

## 17. Recommendations

- Wire a real NIDA adapter behind `kyc/providers/` (ABC + `get_provider`) once credentials are
  authorized; keep the fail-closed default for production until then.
- Add LEVEL_2 materials (document upload, expiry-driven re-verification sweeps) and the member
  KYC screens in the SPA, consuming the read-only `kyc` field and `/kyc/me/`.
- Operationalize expiry: schedule `KYC_VERIFICATION_EXPIRY_DAYS` sweeps so EXPIRED states
  actually block downstream gates.
- Keep KYC as the single trust layer; retire the legacy `is_verified` boolean checks gradually
  (KYC already doubles them).

## 18. Known limitations

- Simulated provider only; production is fail-closed until a real adapter ships.
- No document upload storage this phase; LEVEL_2 is defined but has no materials flow.
- KYC is member-global — a member is verified everywhere at one level; finer per-product or
  per-account levels are out of scope.
- Frontend untouched (backlog).

## 19. Sign-off

Phase 6 spec implemented in order (STEP 1 audit through STEP 15 consistency audit), every step
test-covered and regression-swept, all 36 KYC tests and the 269-test Phase 6 regression suite
green, `manage.py check` clean, migrations applied, backfill idempotent on the dev DB. The KYC
engine is backend-authoritative, provider-fail-closed, member-scoped and consumed by the
withdrawal and loan engines through configurable per-group policy levels. Frontend untouched;
nothing committed.