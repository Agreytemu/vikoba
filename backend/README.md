# Vikoba Kidigitali — Backend Documentation

> A plain‑English guide to the API server. You do **not** need to be a programmer
> to understand this. Read the "Big Picture" section first.

---

## 1. What is this backend, in plain words?

The backend is the **brain and memory** of the Vikoba Kidigitali system.

- The **frontend** (the React website you already built) is what people click.
- The **backend** (this folder) is a web server that:
  - stores all the data (members, savings, loans, staff) in a database,
  - checks who is allowed to do what (login, roles),
  - and answers questions from the frontend like *"show me all members"* or
    *"post this deposit"* over the internet using a REST API.

Think of it as a restaurant kitchen: the frontend is the waiter taking orders,
the backend is the kitchen cooking and the fridge (database) storing ingredients.

**Tech stack (what it is built with):**
- **Django 4.2** — a popular Python web framework (the skeleton).
- **Django REST Framework (DRF)** — turns Django into a REST API (the part that
  speaks "JSON" with the frontend).
- **PostgreSQL** — the production database (on Render). Locally it can use a
  simple file database (SQLite).
- **SimpleJWT** — handles login tokens (JSON Web Tokens).
- **Gunicorn + WhiteNoise** — serves the app and its static files in production.

---

## 2. Big picture: how the pieces talk

```
 Browser / React app (Vercel)
        │  HTTPS + JSON  (Authorization: Bearer <token>)
        ▼
 Django API  (this backend, on Render)   ← you are here
        │
        ▼
 PostgreSQL database  (on Render)
```

1. A user opens the app and logs in with **email + password**.
2. The backend checks the password and returns two **tokens** (a short‑lived
   *access* token and a longer *refresh* token).
3. The frontend stores those tokens and sends the access token with every
   later request in the `Authorization` header.
4. The backend reads the token, figures out who the user is and what role they
   have, does the work (read/write the database), and returns JSON.

---

## 3. Project layout (every folder)

```
render.yaml                 # (repo root) Render blueprint; rootDir = backend
backend/
├── manage.py                # Django command-line entry point
├── requirements.txt         # List of Python libraries needed
├── runtime.txt              # Tells Render which Python version to use
├── Dockerfile               # Builds a local Docker image (optional)
├── start-server.sh          # Starts the server (migrate + gunicorn)
├── .env.example             # Template of the settings (copy to .env)
├── backend/                 # Project settings package
│   ├── settings.py          # ALL configuration (database, auth, CORS...)
│   ├── urls.py              # Master list of URL routes (/api/v1/...)
│   ├── wsgi.py              # How Gunicorn runs the app
│   └── asgi.py              # Async entry point (not used in prod)
├── users/                   # Staff accounts, login, registration
├── members/                 # SACCO members + KYC documents
├── accounts/                # Savings products, accounts, transactions
├── loans/                   # Loan products, applications, repayments
├── customers/               # OLD/legacy data models (mostly unused)
├── media/                   # Uploaded files (KYC, avatars) — NOT committed
└── templates/               # Email/HTML templates
```

Each Django **app** (`users`, `members`, `accounts`, `loans`, `customers`)
follows the same internal structure:

```
<app>/
├── models.py        # The data tables (what is stored)
├── serializers.py   # Converts data <-> JSON
├── views.py         # The logic that runs for each endpoint
├── urls.py          # The URLs belonging to this app
├── permissions.py   # Who is allowed (roles)
├── admin.py         # Django admin panel display
├── apps.py          # App metadata
├── services.py      # Reusable business logic (money math)
├── forms.py         # Admin-only forms
├── signals.py       # (users) hooks on user creation
├── tests.py         # Automated tests
└── migrations/      # Database change history (do not edit by hand)
```

---

## 4. The apps, explained simply

### `users/` — staff & login
This is **not** the SACCO members. It is the **employees/staff** who run the
system (admins, managers, loan officers, accountants).

- **Models:** `User` (custom login account with an `email`, a `role`, and an
  optional profile picture). Roles: `AD` Admin, `MA` Manager, `OP` Operations,
  `FI` Finance, `LO` Loan Officer, `AC` Accountant.
- **What it does:** registration, **JWT login**, token refresh, logout,
  password reset, change password, and "current user" profile.
- **Key files:** `views.py` (the auth endpoints), `serializers.py` (data
  shapes), `permissions.py` (role checks), `managers.py` (how users are
  created), `signals.py` (currently disabled), `management/commands/seed_demo_data.py`
  (creates the demo admin account).

### `members/` — the SACCO members (the real people)
This is the heart of the system. A **Member** is a person in the savings group.

- **Models:**
  - `Member` — name, national ID, phone, email, address, membership number
    (`M000001`…), and a `status` (Active / Pending / Suspended / Dormant / Closed).
  - `NextOfKin` — a member's relative/contact.
  - `EmploymentDetail` — job / business info.
  - `KYCDocument` — identity documents uploaded for verification (national ID,
    photo, signature) with a `verified` flag.
- **What it does:** create/list/update members, and upload KYC files.

### `accounts/` — savings
Manages **savings products** (e.g. "Standard Savings") and **savings accounts**
per member, plus the **transactions** (deposits/withdrawals) on those accounts.

- **Models:** `SavingsProduct`, `SavingsAccount` (balance), `SavingsTransaction`.
- **Important logic (`services.py`):** `post_savings_transaction()` is the only
  safe way to move money. It locks the account row, checks the product allows
  withdrawals and that the balance is enough, then updates the balance. All
  deposits/withdrawals go through here.
- **What it does:** create products, open accounts, post deposits/withdrawals,
  list transactions.

### `loans/` — credit
The full loan lifecycle: apply → review → approve/reject → disburse → repay.

- **Models:** `LoanProduct` (the loan type/terms), `LoanApplication` (status:
  draft → submitted → under_review → approved/rejected → disbursed),
  `LoanApplicationGuarantor`, `LoanApplicationDocument`, `LoanAccount`,
  `LoanSchedule` (monthly installments), `LoanTransaction`.
- **Important logic (`services.py`):**
  - `create_repayment_schedule()` — builds the monthly payment plan.
  - `disburse_application()` — creates the loan account, puts the money into the
    member's savings, and generates the schedule.
  - `post_installment_repayment()` — takes a repayment from savings and marks
    the installment paid.
  - `build_eligibility_summary()` — checks things like "has the member been
    around long enough?" and shows **warnings** (advisory only, never blocks).
- **What it does:** manage loan products, apply for loans, and the
  submit/review/approve/reject/disburse/repay actions.

### `customers/` — legacy (old) models
An **older, separate** set of models (Customer, Account, Transaction, Loan) that
existed before the `members`/`accounts`/`loans` apps were added. It still works
for `/api/v1/customers/`, but its `/accounts/`, `/transactions/`, `/loans/`
routes are **overridden** by the newer apps, so they are effectively retired.
You can ignore this app for normal use.

---

## 5. How data connects (relationships)

```
User (staff)  ── verifies/performs ──▶  KYC docs, transactions, loans
                                              │
Member  ──1───────*──▶  NextOfKin, EmploymentDetail, KYCDocument
   │
   ├──*──▶ SavingsAccount ──*──▶ SavingsTransaction
   │
   └──*──▶ LoanApplication ──1──▶ LoanAccount ──*──▶ LoanSchedule (installments)
                    │                     │
                    └── Guarantors ──────┘
```

- **Members** are the central people.
- A member can have savings accounts and loan applications.
- Staff (Users) are recorded as "who did this action" on transactions/loans.

---

## 6. Authentication & roles (who can do what)

- **Login uses the email address** (not username) + password.
- After login you get an **access token** (valid 60 minutes) and a **refresh
  token** (valid 1 day). Send the access token on every request:
  `Authorization: Bearer <access_token>`.
- **Roles** decide permissions. Example rules:
  - Only **Admin / Manager** can register new staff or manage products.
  - **Loan officers / managers** can review and approve loans.
  - Any authenticated staff can view members/accounts (read).
- The demo login is **`admin@example.com` / `admin12345`** (a superuser, so it
  can do everything). It is created by `seed_demo_data`.

> Note: logout does **not** invalidate the JWT (tokens are not "blacklisted").
> That is fine for this app, but worth knowing.

---

## 7. What the backend needs to run (configuration)

These are **environment variables** (settings). On your machine they go in a
`.env` file (copy `.env.example`). On Render they are set in the dashboard /
`render.yaml`.

| Variable | Needed? | What it does |
|---|---|---|
| `DJANGO_SECRET_KEY` | **Yes (prod)** | A secret used to sign tokens/sessions. Refuses to boot in production without it. |
| `JWT_SIGNING_KEY` | No | Optional: sign JWTs with a key separate from the Django secret. |
| `DEBUG` | No (default off) | `True` only for local development. Must be `False` in production. |
| `DJANGO_ALLOWED_HOSTS` | No | Comma‑separated list of allowed domains. `localhost` and `*.onrender.com` are always allowed. |
| `DATABASE_MODE` | No (default `sqlite`) | `sqlite` for local, `postgres` for Render. |
| `DATABASE_URL` | **Yes on Render** | Full database connection string (Render provides it automatically). |
| `DATABASE_NAME/USER/PASSWORD/HOST/PORT` | Only if `DATABASE_MODE=postgres` | Discrete DB connection (used by Docker). |
| `SQLITE_DATABASE_NAME` | No | SQLite filename for local dev. |
| `FRONTEND_URL` | No (default `http://localhost:3000`) | Frontend origin used to build the password‑reset email link. |
| `CORS_ALLOWED_ORIGINS` | No | Extra frontend domains allowed to call the API. |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | Optional | Gmail account used to send password‑reset emails. |
| `LOAN_MINIMUM_MEMBERSHIP_MONTHS` | No (default 3) | Used only for loan eligibility *warnings*. |
| `LOAN_MINIMUM_MONTHLY_CONTRIBUTION` | No (default 0.00) | Used only for loan eligibility *warnings*. |

**Dependencies** (from `requirements.txt`) include: Django, DRF, SimpleJWT,
django-cors-headers, dj-database-url, whitenoise, gunicorn, psycopg2-binary
(Postgres driver), Pillow (images), drf-writable-nested, python-dotenv.

---

## 8. File‑by‑file reference

### Root files
- `manage.py` — Django CLI (run migrations, start server, seed data).
- `requirements.txt` — Python packages to install.
- `runtime.txt` — Python version for Render (`python-3.12`).
- `Dockerfile` — Builds a Docker image (local/container use).
- `start-server.sh` — Runs `migrate` then starts Gunicorn (the production server).
- `render.yaml` — Render "blueprint": defines the web service + free Postgres
  database and all environment variables. It lives at the **repository root**
  (Render only auto-detects it there); `rootDir: backend` points it at this
  folder.
- `.env.example` — Template of all settings; copy to `.env` for local work.

### `backend/` (project config)
- `settings.py` — **The central configuration.** Database, installed apps,
  middleware, auth (JWT), CORS, static/media, email, loan rules.
- `urls.py` — Registers all URL prefixes (`/admin/`, `/api/v1/auth/`,
  `/api/v1/members/`, `/api/v1/accounts/`, `/api/v1/loans/`, `/api/v1/customers/`).
- `wsgi.py` — Entry point used by Gunicorn in production.
- `asgi.py` — Async entry point (not used by the current start command).

### `users/`
- `models.py` — `User` model + role choices.
- `managers.py` — `create_user` / `create_superuser` logic.
- `serializers.py` — Shapes for user, register, password reset/change.
- `views.py` — Login, register, refresh, logout, password reset, me, users list.
- `urls.py` — Auth endpoints (see API list below).
- `permissions.py` — Role‑based permission classes.
- `admin.py` — How users appear in Django admin.
- `signals.py` — Hooks on user creation (currently commented out).
- `management/commands/seed_demo_data.py` — Creates the demo admin + sample data.
- `apps.py`, `tests.py`, `migrations/` — App config, tests, DB history.

### `members/`
- `models.py` — `Member`, `NextOfKin`, `EmploymentDetail`, `KYCDocument`.
- `serializers.py` — Nested member serializer (includes kin/employment/KYC).
- `views.py` — `MemberViewSet` + KYC upload action.
- `urls.py` — Member endpoints.
- `permissions.py` → actually `admin.py`, `apps.py`, `tests.py`, `migrations/`.

### `accounts/`
- `models.py` — `SavingsProduct`, `SavingsAccount`, `SavingsTransaction`.
- `serializers.py` — Product / account / transaction serializers.
- `views.py` — Products, accounts, transactions viewsets + custom actions.
- `services.py` — **`post_savings_transaction`** (safe money movement).
- `urls.py` — Account/product/transaction endpoints.
- `forms.py` — Admin-only transaction form.
- `admin.py`, `apps.py`, `tests.py`, `migrations/`.

### `loans/`
- `models.py` — `LoanProduct`, `LoanApplication`, `LoanApplicationGuarantor`,
  `LoanApplicationDocument`, `LoanAccount`, `LoanSchedule`, `LoanTransaction`.
- `serializers.py` — Application/list/detail serializers + submit/approve/reject/
  disburse/repay serializers.
- `views.py` — Loan types + applications with submit/review/approve/reject/
  disburse/repay/guarantors/documents actions.
- `services.py` — Schedule creation, disbursement, repayment, eligibility summary.
- `urls.py` — Loan endpoints.
- `forms.py` — Admin repayment form.
- `admin.py`, `apps.py`, `tests.py`, `migrations/`.

### `customers/` (legacy)
- `models.py` — `Customer`, `Account`, `Transaction`, `Loan` (old models).
- `serializers.py`, `views.py`, `urls.py` — Generic CRUD; only `/customers/`
  is still reachable (the rest is overridden by newer apps).
- `admin.py`, `apps.py`, `tests.py`, `migrations/`.

---

## 9. API endpoint quick reference

Base URL (production): `https://vikoba-kidigitali-api.onrender.com/api/v1/`

### Auth — `/api/v1/auth/`
| Method | Path | What |
|---|---|---|
| POST | `login` | Email + password → access & refresh tokens |
| POST | `refresh-token` | Exchange refresh token for a new access token |
| POST | `register` | Create staff (Admin/Manager only) |
| GET | `logout` | Session logout |
| POST | `request-password-reset` | Email a reset link |
| POST | `password-reset` | Set new password (uid + token) |
| POST | `change-password` | Change your password (logged in) |
| GET/PUT/PATCH | `me` | Your own profile |
| GET/POST | `users/` | List / create staff |
| GET/PUT/PATCH/DELETE | `users/{id}/` | Read / update / delete a staff user |

### Members — `/api/v1/`
| Method | Path | What |
|---|---|---|
| GET, POST | `members/` | List / create members |
| GET, PUT, PATCH | `members/{membership_number}/` | Read / update a member |
| POST | `members/{membership_number}/kyc-documents/` | Upload a KYC file |

### Accounts & transactions — `/api/v1/`
| Method | Path | What |
|---|---|---|
| GET, POST | `accounts/` | List / open savings accounts |
| GET, PUT, PATCH | `accounts/{account_number}/` | Read / update an account |
| GET | `accounts/member/{member_id}/` | A member's accounts |
| GET, POST | `products/` | List / create savings products |
| GET, POST | `transactions/` | List / post a savings transaction |
| GET | `transactions/account/{account_number}/` | An account's transactions |
| GET | `transactions/member/{member_id}/` | A member's transactions |

### Loans — `/api/v1/`
| Method | Path | What |
|---|---|---|
| GET, POST | `loan-types/` | List / create loan products |
| GET, POST | `loans/` | List / create loan applications |
| GET, PUT, PATCH | `loans/{application_number}/` | Read / update (draft) |
| GET | `loans/dashboard/` | Status counts + recent applications |
| POST | `loans/{application_number}/submit/` | Submit application |
| POST | `loans/{application_number}/review/` | Move to review |
| POST | `loans/{application_number}/approve/` | Approve |
| POST | `loans/{application_number}/reject/` | Reject |
| POST | `loans/{application_number}/disburse/` | Disburse to savings |
| POST | `loans/{application_number}/repay/` | Repay an installment |
| GET, POST | `loans/{application_number}/guarantors/` | List / add guarantors |
| DELETE | `loans/{application_number}/guarantors/{id}/` | Remove guarantor |
| GET, POST | `loans/{application_number}/documents/` | List / upload documents |
| DELETE | `loans/{application_number}/documents/{id}/` | Delete document |

### Legacy
- `GET/POST /api/v1/customers/` — old customer CRUD (still works).

---

## 10. Run it locally (for testing)

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env           # then edit SECRET_KEY if you like
python manage.py migrate       # create the database tables
python manage.py seed_demo_data# optional: create admin@example.com / admin12345
python manage.py runserver     # http://localhost:8000
```
The API will be at `http://localhost:8000/api/v1/`. The admin panel is at
`/admin/`.

> Use `DATABASE_MODE=sqlite` (the default) for a zero‑setup local database.

---

## 11. Deployment (Render) — short version

Everything is already configured for Render (see `render.yaml` at the repo
root). To deploy: in Render pick **New → Blueprint Instance**, connect the
`vikoba` repo, and let Render create the service + free Postgres automatically.
Leave the root directory as `backend` (set by `rootDir`) — do **not** select the
Docker environment; this app deploys on the native Python runtime:

- **Build command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- **Start command:** `bash start-server.sh` (runs migrations, then Gunicorn)
- **Database:** a free PostgreSQL instance is attached; its `DATABASE_URL` is
  injected automatically.
- **Settings:** `DEBUG=False`, a generated `DJANGO_SECRET_KEY`, allowed host
  `vikoba-kidigitali-api.onrender.com`, and CORS allowing the Vercel frontend.
- **First admin (free plan):** Render's free tier has no interactive Shell. On
  start, `start-server.sh` runs `python manage.py ensure_admin`, which creates
  the initial superuser from `DJANGO_ADMIN_USERNAME`, `DJANGO_ADMIN_EMAIL` and
  `DJANGO_ADMIN_PASSWORD`. It only creates when no superuser exists yet — it
  never modifies an existing admin. Set those three variables, deploy, log in,
  then delete them from the dashboard.

**One thing you must do for the full system to work:** the frontend must point
to this backend. The production setting `VITE_API_URL` in
`web-app/.env.production` is already set to
`https://vikoba-kidigitali-api.onrender.com/api/v1`. After the backend is live,
**redeploy the Vercel frontend** (or set `VITE_API_URL` in Vercel's environment
variables and redeploy) so the website actually calls the API.

---

## 12. Things worth knowing (limitations)

1. **Two data models exist.** The new system is `members` + `accounts` +
   `loans`. The `customers` app is old/legacy and mostly unused.
2. **Media files** (KYC scans, avatars) are stored on the server's local disk.
   On Render that disk is reset on each deploy, so uploads won't persist long‑
   term. For real use you'd move them to object storage (e.g. S3/R2). In
   production (`DEBUG=False`) uploaded files are also not served by the API
   unless that storage is configured.
3. **Logout does not revoke JWTs** (tokens keep working until they expire).
4. **Loan eligibility is advisory only** — it shows warnings, it never blocks
   an application.
5. **Password‑reset email** uses a `from@example.com` sender. The reset link now
   honours `FRONTEND_URL` (default `http://localhost:3000`), but you should set a
   real sender address before relying on email reset in production.
6. **The `Dockerfile` uses Python 3.13** while `runtime.txt` says 3.12. Both
   work, but keep them consistent if you change versions.

---

## 13. Security notes (audit + fixes)

A security pass over the backend found several issues. Fixes that have already
been applied are marked **FIXED**; the rest are known limitations you should be
aware of.

### Fixed

- **Committed secrets** — `.env.example` contained a real Gmail app password and
  a real (now known) Django `SECRET_KEY`. Both are scrubbed and replaced with
  placeholders. If you ever copied those old values into a live account, **rotate
  them now** (Django secret: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`).
- **Production secret guard** — `settings.py` refuses to boot when `DEBUG=False`
  and no `DJANGO_SECRET_KEY` is set, instead of silently using a known-insecure
  fallback. JWTs can be signed with a separate `JWT_SIGNING_KEY`.
- **Security headers** — `X_FRAME_OPTIONS=DENY`, `SECURE_CONTENT_TYPE_NOSNIFF`,
  `SECURE_BROWSER_XSS_FILTER`, `SECURE_REFERRER_POLICY` always on; HSTS, TLS
  redirect and secure cookies are enforced when `DEBUG=False`.
- **API denies by default** — DRF `DEFAULT_PERMISSION_CLASSES` is now
  `IsAuthenticated`; open endpoints opt in with `AllowAny` explicitly.
- **Rate limiting** — login, registration and password-reset views throttle to
  `30/min` (scope `auth`); anonymous traffic is capped at `100/min`.
- **Browsable session-auth removed** — the `rest_framework.urls` include under
  `/api/v1/auth` is gone (no more session-login page).
- **Logout now requires authentication** — `LogoutView` is `IsAuthenticated`.
- **Password reset** — uid is now URL-safe base64 (no raw primary keys), the
  email link honours `FRONTEND_URL`, `print()` statements leaked reset URLs in
  logs (removed), and the endpoint no longer reveals whether an email exists.
- **`seed_demo_data` guard** — refuses to run when not in local development
  (`DEBUG=False` against a non-SQLite database), so the well-known
  `admin@example.com / admin12345` account can't be seeded on a live database.
- **Upload validation** — KYC and loan documents are validated (extension whitelist
  + 10 MB cap) via `members/validators.py`.
- **Account-number races** — `generate_account_number()` now locks the last row
  with `select_for_update()` inside the existing transaction.
- **Admin atomicity** — loan approve/disburse/repay admin actions run inside a
  single transaction.
- **Customer delete restricted** — only Admin/Manager roles can DELETE customer
  records.

### Known limitations (not fixed)

- **JWTs are not blacklisted.** Logout clears the frontend token but an already
  issued access token keeps working until expiry (60 min), and refresh tokens are
  not rotated. Enabling rotation/blacklist needs the SimpleJWT "blacklist" app.
- **Admin loan actions don't post to savings** — the Django admin approve/disburse/
  repay buttons update loan records only; they do not credit/debit a member's
  savings account. The API flow (`disburse`/`repay` endpoints) does this correctly
  via `post_savings_transaction`.
- **Legacy `customers/` transactions allow negative balances** — the old app's
  `Transaction.save()` doesn't check for overdrafts. Only used by the retired UI.
- **CORS regex is broad** — `https://*.vercel.app` is allowed (covers preview
  deploys). Tighten to explicit origins if you don't need previews.
- **Member PII in responses** — national ID, KRA and contact data are returned to
  any authenticated business-role user. This is required by the current UI
  (e.g. loan officers search members by national ID) but is a data-minimisation
  trade-off.
- **Reset tokens are cheap to mint** — the anti-enumeration guard plus the
  30/min throttle mitigate abuse, but there is no lockout/backoff beyond that.
- **Separation of duties** — the same role can approve and disburse a loan.
  Consider splitting these for higher-value portfolios.
- **No content security policy (CSP) or upload object-storage** — media stays on
  the local disk and is only served in `DEBUG=True`. Move uploads to S3/R2 and
  serve them through an authenticated route before real production use.
