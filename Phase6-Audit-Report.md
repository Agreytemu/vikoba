# Phase 6 — STEP 1 & 2 Audit: Identity, Authentication, KYC, Member & Group Architecture

**Date:** 2026-09-22 · **Scope:** backend (read-only audit — no code changed) · **Method:** source
inspection of `users`, `members`, `groups`, `loans`, `accounts`, `governance`, `payments`,
`finance` apps + settings + frontend.

---

## 1. What identifies a user?

- **Login identity:** `users.User.email` — `USERNAME_FIELD = 'email'`, `unique=True`
  (`users/models.py:26,60`). PIN login identifies the account indirectly via
  `Member.phone_number` (trailing-digit lookup, `users/services.py:114-140`).
- **Auth gates:** JWT (SimpleJWT, access 60 min / refresh 1 day, no rotation/blacklist);
  `CustomTokenObtainPairSerializer.validate` refuses member tokens when `not email_verified`
  (`users/serializers.py:65-89`). PIN login additionally requires `role == MEMBER`, verified
  email and a set PIN.
- **Email** is unique and verified via 6-digit `EmailVerificationCode` (15 min TTL, max 5
  attempts, single-use; `users/models.py:87-125`). `email_verified` was back-filled true for all
  pre-existing users (`users/migrations/0004`).
- **Phone** is NOT on `User` and NOT unique at the DB level on `Member` (only a
  registration-time uniqueness/format check, `users/serializers.py:149-157`; format `^\+255[67]\d{8}$`).
- **No phone on User. No DOB / national ID / is_verified on User.** All identity-flavoured
  fields live on `Member`.

## 2. What identifies a member?

- `Member.membership_number` — public stable identifier, `unique=True`, generated `M{seq:06d}`
  server-side (`members/models.py:14-21,50-51`). **Public IDs are never DB PKs** (PK is a UUID).
- `Member.user` is `OneToOne(users.User)`, nullable (`members/models.py:54-60`) — staff/ADMIN
  members have no login. **One user ↔ at most one member; one member ↔ optionally one user.**
- `Member.national_id` — unique, nullable, max 20, free-text with **no format validation and no
  NIDA lookup** (`members/models.py:68`). `NextOfKin.national_id` also exists (`:201`).

## 3. Key audit answers

| Question | Answer |
|---|---|
| Can one user belong to multiple groups? | Yes — `GroupMembership` is many-to-many with `UniqueConstraint(group, member)` (`groups/models.py:49-87`). |
| Is member identity unique? | Yes — `membership_number` and `national_id` unique; `Member.user` OneToOne. |
| Is phone unique? | No DB constraint on `Member.phone_number`; only serializer-time check. |
| Is email unique? | Yes on `User.email`; `Member.email` is a plain, non-unique email for members without a user. |
| Is NIDA/national ID stored? | Yes, `Member.national_id` (unique, unverified free text). No link to any identity service. |
| Is KYC already partially implemented? | **Yes.** Phone OTP (`Member.phone_verified`), staff-verified `KYCDocument`s (NATIONAL_ID / PASSPORT_PHOTO / SIGNATURE), next-of-kin, `submit-for-review`, and a composite `Member.is_verified` computed by `refresh_verification()` (`members/models.py:134-176`). **It is a manual-review boolean pipeline, not a status machine; there is no provider, no levels, no results record, no KYC version/expiry.** |
| Which financial actions currently require verification? | Withdrawals: `governance/policy.py:151-157` (`ApprovalError.KYC_REQUIRED`), `accounts/views.py:138-145`, `payments/views.py:260`; Loans: submission only (`loans/views.py:403-410`) — **the approval eligibility engine (`loans/eligibility.py`) has NO KYC input**; Groups: creation limit 1 vs 3 (`groups/views.py`). |

## 4. Existing authentication architecture (what "verified" means today)

- **Auth layer (`User`):** `email_verified` gates JWT/PIN login for members. There is **no
  2FA/MFA/TOTP**, no auth audit trail (no login/failed-login/PIN-attempt/verification events are
  logged anywhere; `users/signals.py` is commented out), and no token-blacklist (logout is
  client-side).
- **Identity layer (`Member`):** `phone_verified` (via `PhoneOTP`, dev-mode code delivery only —
  no real SMS/WhatsApp channel wired; `whatsapp/service.py:140-155` `deliver_otp` is defined but
  never called), `verification_submitted`, `is_verified` (composite: ADMIN-source members are
  auto-verified; self-registered need submission + verified phone + next-of-kin + all KYC docs
  staff-verified). Phone change de-verifies (`MeMemberSerializer.update`,
  `members/serializers.py:117-133`).
- **Enforcement gaps:** `member.status` (ACTIVE/CLOSED/…) is never enforced;
  `governance/policy.py:158-164` even references a nonexistent `member.is_active`; current
  min-age 18 is enforced only in the onboarding view.

## 5. Existing member/group architecture

- `Member` identity fields: salutation, first/middle/last name, `national_id`, `phone_number`,
  `email`, `date_of_birth`, `kra_pin` (a Kenyan-anomaly field — legacy, in a Tanzania model),
  address block, `citizenship_type`, `gender`, occupation, plan, status, verification block.
- `GroupMembership` roles (incl. chairperson/secretary/treasurer), `is_active`, active filtering;
  group creation gated on `is_verified` (1 vs 3 groups).
- **One user can hold multiple active memberships in different groups**, and one member profile
  serves all groups — KYC must be **member-scoped, not group-scoped**.

## 6. Existing policy / eligibility engines (integration targets)

- **Withdrawal:** `governance/policy.py evaluate_withdrawal` (pure, deterministic decision) with
  hard-coded `member.is_verified → KYC_REQUIRED`; `GroupWithdrawalPolicy` (per-group,
  "`None` inherits platform default" merged by `effective_values`) is the correct configurable
  extension point. `governance/withdrawals.py submit_withdrawal` re-checks `is_verified` at the
  service entry and records everything through `ApprovalAction` audit.
- **Loan:** blocking gate is `loans/eligibility.py check_eligibility` at approval/disbursal;
  `GroupLoanPolicy` / `LoanProduct` provide the same `None`-inherits merge via
  `loans/policies.py effective_values`. **No `PolicyDecision` object exists for loans**; approval
  collects `(ok, errors)`.
- **Audit stores:** `finance.AuditEvent` (financial), `governance.ApprovalAction` (governance
  decisions incl. policy changes), `GroupActivity` (group workspace timeline). A KYC audit log
  should follow the `ApprovalAction` append-only pattern but as its own domain record.

## 7. Security, secrets, observability

- Secrets are env-only (`python-dotenv` + `os.getenv`); `backend/.env` is git-ignored;
  `web-app/.env*` are git-tracked (only API-base/VITE names — flagged for hygiene).
  `backend/.env.example` documents a previous real-credential leak that was scrubbed.
- No identity/KYC SDK in `requirements.txt` (22 packages: Django, DRF, simplejwt, cors,
  drf-writable-nested, pillow, requests, dotenv, gunicorn, psycopg2, whitenoise). No frontend
  identity packages.
- No generic key/value policy store; the two per-group policy models are the extension pattern.

## 8. Clinical conclusions driving Phase 6 design

1. **KYC is partially implemented as a manual boolean** (`Member.is_verified` +
   `KYCDocument.verified`) but is NOT a status machine, has no provider, no levels, no results
   record, no versioning, no audit events, and no expiry. This phase ADDS a dedicated KYC domain
   and converts the boolean gates to consume it — without destroying the existing manual pipeline
   (frontend `VerificationWorkflow` depends on it).
2. **Do not move identity fields around.** `Member` already holds the single identity record;
   `User` stays the auth record. The new KYC domain reads from `Member` and writes only KYC state.
3. **Financial integration is additive & configurable**: extend `GroupWithdrawalPolicy` and
   `GroupLoanPolicy` with a nullable `kyc_level_required` (None → platform default), resolved in
   `effective_values`, consumed by `evaluate_withdrawal` and `check_eligibility`.
4. **Provider isolation**: a `IdentityVerificationProvider` abstraction + fail-closed adapter
   factory. No authorized NIDA integration or credentials exist in this repo, so the real NIDA
   adapter is NOT implemented (spec §6/§38): the provider registry ships with a simulated adapter
   that only activates under an explicit `KYC_PROVIDER_MODE=simulated` flag; otherwise
   submissions fail-closed with PROVIDER_ERROR — never auto-verified without an authoritative
   response.
5. **Idempotency/retry/audit** follow the proven governance patterns: an idempotent request row
   (per-member active-request guard), bounded retries, append-only KYC audit events.
6. Backfill existing members into VERIFIED (manual-review method, LEVEL_1) so today's working
   behavior is preserved exactly while moving to explicit, auditable KYC state.

---

Next: STEP 3 design + STEP 4 state machine + STEP 5 provider abstraction (implementation order
from the Phase 6 spec).