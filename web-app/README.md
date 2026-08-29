# Vikoba Kidigitali — Frontend (`web-app`)

The frontend for **Vikoba Kidigitali**, a savings-and-credit cooperative (vikoba / SACCO) management platform. It is a single-page application (SPA) that drives the staff workflow — members, savings accounts, transactions, and a full loan-application pipeline — against the Django REST Framework API in the sibling `backend/` folder.

This document covers **only the frontend**. For the API, the backend, deployment and the full staff guide see the repository root (`README.md`, `USER_GUIDE.md`) and `backend/README.md`.

---

## 1. Overview

- **Type:** React 18 SPA bootstrapped with Vite 5
- **Language:** TypeScript (strict mode)
- **UI:** Tailwind CSS + shadcn/ui-style components (Radix primitives) + lucide-react icons
- **State / data:** TanStack Query (react-query) for server state, `react-hook-form` + `zod` for forms
- **Tables:** TanStack Table (`@tanstack/react-table`) with a reusable `DataTable`
- **Charts:** Recharts (bar, pie, line)
- **Routing:** `react-router-dom` v6 (`createBrowserRouter`)
- **HTTP:** Axios with request/response interceptors, automatic token refresh
- **i18n:** i18next with 10 languages, country-based default detection
- **Notifications:** react-toastify

> The app exposes a **public marketing landing page** plus an **authenticated staff app shell** (top navbar + sidebar) that gates every module behind the signed-in user's role.

---

## 2. Project structure

```
web-app/
├── index.html                     # HTML entry
├── package.json                   # deps + scripts
├── vite.config.ts                 # Vite config, @ → ./src alias
├── tsconfig.json / tsconfig.node.json
├── tailwind.config.js             # theme, fonts, colours
├── postcss.config.js
├── .eslintrc.cjs
├── .env.example                   # VITE_API_URL, VITE_APP_NAME
├── .env.production                # production API base (Vercel build)
├── components.json                # shadcn/ui config
├── Dockerfile                     # node:22-alpine dev container
├── vercel.json                    # SPA rewrites for Vercel
├── public/
│   └── vikoba-kidigitali--logo.png
└── src/
    ├── main.tsx                   # bootstrap: fonts, query client, i18n, router
    ├── App.tsx                    # authenticated app shell (navbar + sidebar)
    ├── RootLayout.tsx             # wraps all routes in Providers
    ├── index.css                  # Tailwind + global styles + chart palette
    ├── constants.ts               # apiBaseUrl from env
    ├── types.ts                   # shared TS types (Profile, UserProps, etc.)
    ├── routes/index.tsx           # every route definition
    ├── lib/                       # api client, utils, access control, system info
    ├── contexts/                  # Auth, Theme, Providers
    ├── hooks/                     # generic + react-query API hooks
    ├── services/                  # typed Axios API layer per resource
    ├── i18n/                      # i18next config + locale JSON files
    ├── components/                # shared components, feature components, ui/ primitives
    ├── pages/                     # route pages
    └── assets/                    # images (login/marketing art, placeholder)
```

---

## 3. Getting started

Prerequisites: Node.js 18+ (Docker image uses Node 22), npm.

```bash
# 1. Install dependencies
npm install

# 2. Configure the environment (copy the example)
cp .env.example .env
#   VITE_API_URL=http://localhost:8000/api/v1   <- Django API base
#   VITE_APP_NAME=Vikoba Kidigitali

# 3. Start the dev server (port 3000)
npm run dev
```

The Vite dev server proxies `/` traffic to the Django backend (`"proxy": "http://127.0.0.1:8000"` in `package.json`) so the frontend can talk to the API in development.

### Scripts

| Script | Command | Purpose |
|---|---|---|
| `dev` | `vite --port 3000 --host 0.0.0.0` | Dev server on port 3000 |
| `build` | `tsc && vite build` | Type-check then production build |
| `lint` | `eslint . --ext ts,tsx ...` | ESLint with zero warnings policy |
| `preview` | `vite preview` | Preview the built app |

### Environment variables

| Variable | Used by | Example |
|---|---|---|
| `VITE_API_URL` | Axios base URL (`src/lib/api.ts`, `src/constants.ts`) | `http://localhost:8000/api/v1` |
| `VITE_APP_NAME` | Brand name in `src/lib/system.ts` (falls back to "Vikoba Kidigitali") | `Vikoba Kidigitali` |
| `VITE_APP_TAGLINE` | Tagline on the landing page (falls back to default) | `Savings & credit, rebuilt for the communities of 2026` |

---

## 4. Entry points

### `src/main.tsx`
- Sets the document title from `SYSTEM_NAME`.
- Imports self-hosted fonts (`Inter`, `Fraunces`) via `@fontsource/*` so no runtime external requests occur.
- Creates the QueryClient with: `staleTime: 15s`, refetch on mount, refetch on window focus/reconnect ("always"), and a background `refetchInterval` of 30 s so tables stay fresh.
- Mounts `<QueryClientProvider>` → `<RouterProvider router={router}>` → `<ToastContainer>`.

### `src/RootLayout.tsx`
Wraps every route in `<Providers>` (Theme → Auth) and renders `<Outlet/>`.

### `src/App.tsx` — authenticated app shell
- Local state `showMobileMenu` toggles the mobile sidebar.
- Renders `NavBar` (fixed top bar, 64px) and a layout grid: a 280px desktop sidebar with `<SidebarLinks/>` and the scrollable content area (`max-w-7xl`) that hosts the routed pages via `<Outlet/>`.
- On mobile, clicking the hamburger shows a floating sidebar menu.

---

## 5. Routing (`src/routes/index.tsx`)

All routes are defined here with `createBrowserRouter`, under a single root layout, and an `errorElement={ErrorPage}`.

| Path | Component | Guard |
|---|---|---|
| `/login` | `SignIn` | public |
| `/register` | `SignUp` | public |
| `/forgot-password` | `ForgotPassword` | public |
| `/reset-password` | `PasswordResetConfirm` | public |
| `/landing` | `LandingPage` | public |
| `/` | `HomeEntry` — shows `App` (dashboard) when authenticated, otherwise `LandingPage` | — |
| `/` (index) | `DashBoard` | — |
| `/members` | `Members` | `members` |
| `/members/edit/:memberId?` | `MembersEdit` | `members` |
| `/members/view/:memberId?` | `MembersView` | `members` |
| `/accounts` | `Accounts` | `accounts` |
| `/accounts/edit/:accountNo?` | `AccountsEdit` | `accounts` |
| `/accounts/view/:accountNo` | `AccountsView` | `accounts` |
| `/transactions` | `Transactions` | `transactions` |
| `/transactions/edit/:transactionId?` | `TransactionsEdit` | `transactions` |
| `/loans` | `Loans` | `loans` |
| `/loans/edit/:loanId?` | `LoansEdit` | `loans` |
| `/loans/view/:loanId` | `LoansView` | `loans` |
| `/expenses` | `Expenses` | `expenses` |
| `/settings` | `Settings` | signed in |
| `/help` | `Help` | signed in |
| `/users` | `Users` | `users` |
| `/profile` | `Profile` | signed in |
| `/sms` | `BulkSMS` | `communications` |
| `/emails` | `BulkEmail` | `communications` |

Module-protected routes are wrapped with `<RequireModuleAccess module=.../>` (see section 7).

---

## 6. Authentication & session

### `src/contexts/AuthContext.tsx`
- Exposes `{ isAuthenticated, login(), logout(), isLoading }` via `Auth()`.
- **Session:** 12 hours (`SESSION_DURATION`); tokens stored in `localStorage` under `accessToken`, `refreshToken`, `expiresAt`.
- On mount it checks for a refresh token. If there is an access token it authenticates immediately; otherwise it calls `useRefreshToken` to obtain a new one, or `logout()` on failure.
- `login(data)` stores tokens and flips auth state. `logout()` clears storage and navigates to `/login`.
- `PUBLIC_PATHS = ["/", "/landing"]` are reachable without authentication.
- While resolving initial state it shows a full-screen `Spinner`.

### `src/contexts/ThemeContext.tsx`
- `darkTheme` initialised from `localStorage("darkMode")` or the OS `prefers-color-scheme`.
- `toggleDarkTheme()` flips and persists it; applies/removes the `dark` class on `<html>`.

### `src/contexts/providers.tsx`
- Composes `<ThemeContextProvider><AuthProvider>{children}</AuthProvider></ThemeContextProvider>`.

### `src/lib/api.ts` — Axios instance
- Base URL: `import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"`.
- **Request interceptor:** attaches `Authorization: Bearer <accessToken>`; if the payload is `FormData` it deletes the default JSON `Content-Type` so the browser sets the multipart boundary (required for DRF file uploads).
- **Response interceptor:** unwraps `response.data`, and handles **401s** with a single-flight refresh: queues concurrent failed requests, calls `/auth/refresh-token`, retries the original request with the new token, and clears storage + redirects to `/login` when the refresh itself fails.

---

## 7. Role-based access control

### `src/lib/access-control.ts`
- Defines the union type `AppModule` (`members | accounts | transactions | loans | users | expenses | communications`) and user roles `AD | MA | OP | FI | LO | AC`.
- Permission matrix (`hasModuleAccess(role, module)`):

| Module | Allowed roles |
|---|---|
| members | AD, MA, OP, FI, LO, AC |
| accounts | AD, MA, OP, FI, LO, AC |
| transactions | AD, MA, OP, FI, LO, AC |
| loans | AD, MA, OP, LO |
| users | AD, MA |
| expenses | AD, MA, OP, FI |
| communications | AD, MA, OP, FI |

Role display labels (`src/services/users.ts`):
`AD` Admin · `MA` Manager · `OP` Operations Manager · `FI` Finance Officer · `LO` Loan Officer · `AC` Accountant.

### `src/components/RequireModuleAccess.tsx`
Route guard. Waits for the user profile (`useUserProfileInfo`), and if `hasModuleAccess` fails renders an "Access denied" screen instead of the page.

### `src/components/SidebarLinks.tsx`
Renders the sidebar navigation from a static `sidebarItems` array (icon + label + optional module). Items the user cannot access are filtered out. Bottom of the sidebar has a **Logout** button that calls the server `useLogout` mutation and the local `logout()` immediately (so a network failure can never leave a stale local session).

---

## 8. API layer

### `src/services/*` — typed service objects

| Service | Endpoints | Summary |
|---|---|---|
| `auth.ts` | `POST /auth/register`, `POST /auth/login`, `GET /auth/logout`, `POST /auth/refresh-token`, `POST /auth/request-password-reset`, `POST /auth/password-reset`, `POST /auth/change-password` | All auth flows |
| `accounts.ts` | `GET /accounts`, `GET /accounts/:accountNo`, `GET /accounts/member/:memberId`, `GET /products`, `POST /accounts/`, `PATCH /accounts/:accountNo/` | Accounts + product catalog |
| `loans.ts` | `GET /loan-types/`, `GET /loans/?filters`, `GET /loans/dashboard/`, `GET/POST /loans/:appNo`, `PATCH /loans/:appNo/`, `POST .../submit|review|approve|reject|disburse|repay/`, `POST .../guarantors/`, `DELETE .../guarantors/:id/`, `POST .../documents/` (FormData), `DELETE .../documents/:id/` | Full loan pipeline |
| `members.ts` | `GET /members`, `GET /members/:memberId`, `POST /members/`, `PUT /members/:memberId/`, `POST /members/:memberId/kyc-documents/` (FormData) | Members + KYC uploads |
| `transactions.ts` | `GET /transactions`, `POST /transactions/`, `GET /transactions/member/:memberId`, `GET /transactions/account/:accountNumber/` | Transactions |
| `profile.ts` | `GET /auth/me`, `PATCH /auth/me` (FormData) | Current user profile |
| `users.ts` | `GET /auth/users`, `GET /auth/users/:id` + `normalizeUser()` | Staff user list |

### `src/hooks/api/*` — TanStack Query hooks per resource

- **auth.ts:** `useRegister`, `useLogin` (also stores tokens), `useRequestPasswordReset`, `usePasswordReset`, `useChangePassword`, `useLogout`, `useRefreshToken` — mutations over `authService`.
- **accounts.ts:** `useGetAccounts`, `useGetAccountById`, `useGetMemberAccounts`, `useGetProducts`, `useCreateAccount`, `useUpdateAccount` (invalidates `accounts`, `account`, `memberAccounts`).
- **loans.ts:** `useLoanTypes`, `useLoans(filters)`, `useLoanDashboard`, `useLoan(applicationNumber)`, `useCreateLoan`, `useUpdateLoan`, `useLoanAction` (submit/review/approve/reject/disburse/repay), `useGuarantorMutations` (add/remove), `useDocumentMutations` (upload/remove). A shared `invalidateLoans` clears loan, dashboard, account, and transaction caches.
- **members.ts:** `useCreateMember`, `useUpdateMember` (invalidates member, accounts, transactions of the member), `useGetMemberById`, `useGetMembers`.
- **transactions.ts:** `useGetTransactions`, `usePostTransaction` (invalidates transactions + all account queries because balances change), `useGetMemberTransactions`, `useGetAccountTransactions`.
- **profile.ts:** `useGetUserProfile`, `useUpdateUserProfile` (invalidates `profile` + `users`).
- **users.ts:** `useGetUsers`.

### Generic hooks

- `src/hooks/useDataFetch.ts` — `useDataFetch<T>(endpoint)`: plain-axios list fetcher returning `{ data, loading, error }` (used by the dashboard).
- `src/hooks/useDashboardData.ts` — `useDashboardData()`: aggregates customers/accounts/loans/transactions into `totalCustomers`, `totalAccountBalance`, `totalLoans`, `totalWithdrawals`.
- `src/hooks/useFetchSingleObject.ts` — `useFetchSingleObject<T>(endpoint, editItem)`; fetches only when `editItem` is `true`.
- `src/hooks/useInView.ts` — `useInView<T>(options)`; `IntersectionObserver` that reports once the element is 15% visible, then disconnects.
- `src/hooks/useUserProfile.ts` — `useUserProfileInfo()` wraps `useGetUserProfile`.

---

## 9. Pages (functions)

### Auth pages (`src/pages/auth/`)
All auth pages share a two-panel layout (brand panel with illustration + form panel) and use `FormInput` + `Button` components.

- **SignIn** (`SignIn.tsx`): email + password form. On submit calls `useLogin` → `login(data)` (AuthContext) + success toast. Provides a **demo login** hint box (`admin@example.com / admin12345`) that only renders in development builds (`import.meta.env.DEV`), a "Forgot password?" link, and a link to `/register`. Handles errors through `getApiErrorMessage`.
- **SignUp** (`SignUp.tsx`): username, email, password, confirm password. Validates passwords match, calls `useRegister`, toasts result, navigates to `/login`.
- **ForgotPassword** (`ForgotPassword.tsx`): accepts an email, calls `useRequestPasswordReset`, toasts the server message.
- **PasswordResetConfirm** (`PasswordResetConfirm.tsx`): reads `uid` and `token` from the URL (`?user=...&token=...`), collects a new password + confirmation, calls `usePasswordReset`, then navigates to `/login`.

### `src/pages/LandingPage.tsx` — public marketing page
A single scrolling marketing page (header nav, hero, animated stat counters, "Vision" section, "How a circle works", features grid, quote, final CTA, footer). Uses `Reveal` for scroll animations, `Counter` for count-up stats, and `SYSTEM_NAME`/`SYSTEM_TAGLINE`/`CURRENT_YEAR`/`LOGO_URL` from `lib/system`. Sets `document.title` on mount.

### `src/pages/DashBoard.tsx` — operations dashboard
Greets the user and shows, gated by role access:
- **KPI cards:** active members, savings held (sum of active account balances), net flow this month (deposits − withdrawals), loans awaiting review.
- **Cash flow trend:** 6-month bar chart of deposits vs withdrawals (Recharts).
- **Loan pipeline:** donut chart of applications by status with a coloured legend.
- **Recent transactions** table (last 6).
- **Savings by product:** vertical line chart of the top 6 product balances.
- **Recent loan applications:** cards that link to edit (draft) or view (submitted) pages.
- Helpers: `money()` formats KES, `statusLabels`/`statusColours` maps loan states.

### `src/pages/ErrorPage.tsx`
`useRouteError` + "Oops! …" screen with a link home.

### `src/pages/Help.tsx`
Static page describing the core staff workflow (create member → open account → post transactions → draft loan, add documents/guarantors → submit for review/approval), links to the repository `USER_GUIDE.md`.

### `src/pages/Profile.tsx`
Self-editable profile: visually shows the avatar (with inline preview on pick), and a form for `username`, `email` (disabled `role_display`). Profile image must be < 7 MB. Calls `useUpdateUserProfile` (multipart).

### `src/pages/Settings.tsx`
Tabbed page: **Update Profile** (renders `Profile`) and **Change Password** (renders `components/settings/tabs/change-password.tsx` — current/new/confirm password with show/hide toggles, calls `useChangePassword`).

### `src/pages/Users.tsx`
Staff user table (`Users`) with columns Image (avatar with placeholder fallback), User Name, Email, Role. Search filters by username. "Create User" shows a toast ("Creating staff users is not available yet") instead of linking to a non-existent route.

### `src/pages/members/`
- **Members.tsx:** searchable DataTable (membership number, first name, last name, email, phone, national ID, status pill, edit action). Clicking the membership number copies it to the clipboard and links to the member view. "Create Member" → `/members/edit`.
- **MembersEdit.tsx:** create/edit member form (zod-validated). Sections: **Personal Details** (salutation, names, national ID, phone, email, date of birth, KRA PIN, status); **Address** (country, county, city); **Employment Details** (type-driven dynamic fields — employed/self-employed/business/unemployed, with monthly income for non-unemployed); **Next of Kin** (repeatable rows via `useFieldArray`); **KYC Documents** (repeatable rows: type, file, verified). Submit logic: choose **Save** or **Save & Continue**; after saving to the backend it uploads any newly added KYC files in parallel via `membersService.uploadKycDocument`.
- **MembersView.tsx:** member detail page. Left column: personal, employment, and next-of-kin cards. Right column: **Accounts** (up to 10, with per-row edit + transaction actions, "Add Account" modal with `AddAccountForm`), **Transactions History**, and **Loan Applications** (role-gated) with "New application" link. Uses modals for add-account and create-transaction.

### `src/pages/accounts/`
- **Accounts.tsx:** DataTable of accounts (account number with copy+view link, member, product, balance, active flag, edit action) with a combined search filter and a "Create Account" button that opens the `AddAccountForm` modal (also used for editing via the pen icon).
- **AccountsEdit.tsx:** standalone create (and populate) form — membership number, product (from `GET /products`), account status; creates via `useCreateAccount`.
- **AccountsView.tsx:** account detail: KPI strip (current balance, status badge, product, member link), transaction history DataTable (date, reference, type badge, amount, narration, processed-by), and a "New transaction" button that opens the `TransactionForm` modal (disabled for inactive accounts).

### `src/pages/transactions/`
- **Transactions.tsx:** DataTable (reference, account number, type badge, amount, narration, served by, date, "View" details) with a combined search filter, "Create Transaction" modal (`TransactionForm`), and a transaction-details `Modal`.
- **TransactionsEdit.tsx:** a "New Transaction" page wrapping the shared `TransactionForm`; navigating to `/transactions/edit` (no id) opens this page, and it redirects back to `/transactions` after a successful save.

### `src/pages/loans/`
- **Loans.tsx:** loan application list with status-count filter buttons from `useLoanDashboard` (click to filter by status), a DataTable (application number link, member, loan type, amount, status badge, loan officer, approver, action), and an "Apply loan" button visible to `LO`/`AD` roles (draft applications get an "Edit draft" action).
- **LoansEdit.tsx:** a **6-step wizard** for creating/editing a loan draft:
  1. **Member** — searchable member picker.
  2. **Loan details** — loan type (rate shown), requested amount, repayment period months, purpose; inline limits (min/max amount, max term, multiplier, guarantor requirement).
  3. **Employment** — employer, payroll number, gross/net salary.
  4. **Security** — security type (self guarantee / guarantors / collateral / mixed), collateral description, and a guarantor manager (search members, add/remove, guaranteed amount).
  5. **Documents** — upload/remove supporting documents (PDF/images/Office) with a document-type picker.
  6. **Review** — remarks, then **Save draft** or **Submit for review**.
  - Draft readiness validation (`isDraftReady`) checks member, type, amount within min/max, integer term within max, purpose, and collateral description when needed. Once an application leaves the `draft` state the page refuses editing.
- **LoansView.tsx:** single application detail with status-driven **workflow actions** (submit, start review, approve, reject, disburse, post repayment — the last three via a modal that needs an active member account, and repayment also selects an unpaid installment). Shows loan details, member summary, **eligibility summary** (membership months, contributions, indicative limit, guaranteed, estimated installment/interest/repayable) with amber **review warnings**, the generated **repayment schedule** table (paid / due / overdue badges), guarantors, supporting documents, and a full audit history (with approval/rejection/disbursement notes).

### Placeholder pages (backend APIs not implemented yet)
- `src/pages/emails/BulkEmail.tsx` — informative "not available yet" card with a link back to the dashboard.
- `src/pages/expenses/index.tsx` — informative "not available yet" card with a link back to the dashboard.
- `src/pages/sms/BulkSMS.tsx` — informative "not available yet" card with a link back to the dashboard.

---

## 10. Components

### Feature components

| Component | Purpose |
|---|---|
| `components/accounts/AddAccountForm.tsx` | Create/edit an account (member, product from catalog, active flag). Used in a modal by Accounts / MembersView and pre-fills the selected account for editing or a member's number for new accounts. |
| `components/transactions/transactionForm.tsx` | Deposit / withdrawal form (account number, type, amount, narration). Optionally locks the account number and calls `onSuccess` after posting. |
| `components/settings/tabs/change-password.tsx` | Current/new/confirm password card with visibility toggles (see Settings). |
| `components/landing/Counter.tsx` | Count-up animation to `to` once in view (eased, RAF-driven). |
| `components/landing/Reveal.tsx` | Scroll-reveal wrapper (fade + lift via `useInView`). |

### Shared/components

| Component | Purpose |
|---|---|
| `Button.tsx` | Legacy styled button (primary/secondary). |
| `FormInput.tsx` | Labelled input with built-in password show/hide (`LucideIcon` Eye/EyeOff), file `accept`, disabled, ref support. |
| `LanguageSwitcher.tsx` | `<select>` of every `supportedLanguages` entry; calls `i18n.changeLanguage`. |
| `LucideIcon.tsx` | Renders any lucide icon by name string. |
| `NavBar.tsx` | Fixed top bar: logo + system name, mobile menu toggle, `LanguageSwitcher`, dark-mode toggle, user dropdown (avatar, username + role badge, email, Profile link, Logout with confirmation modal). Closes on outside click. |
| `RequireModuleAccess.tsx` | Route guard (see section 7). |
| `SidebarLinks.tsx` | Nav list / logout (see section 7). |
| `Spinner.tsx` | Branded CSS spinner. |
| `DataTable` (`data-table.tsx`) | Generic TanStack table wrapper with column search, optional header title + create button (link or callback), sorting, pagination controls (« ‹ › »), "Go to page", and page-size selector (10/25/50/75/100). |
| `CopyToClipboard` (`ui/clipboard.tsx`) | Link + copy icon with a "Copied" tooltip. |

### shadcn/ui primitives (`src/components/ui/`)
`badge.tsx` (variants: default/secondary/destructive/outline), `button.tsx` (variants default/destructive/outline/secondary/ghost/link, sizes sm/lg/icon, `asChild`), `calendar.tsx` (react-day-picker wrapper), `card.tsx`, `chart.tsx` (Recharts helpers: `ChartContainer`, `ChartTooltip`, `ChartLegend` + content), `form.tsx` (react-hook-form context bindings), `input.tsx`, `label.tsx`, `Modal.tsx` (fixed overlay, backdrop click + Esc to close, title + separator + children), `popover.tsx`, `select.tsx` (Radix select with scroll buttons), `separator.tsx`, `switch.tsx`, `table.tsx`, `tabs.tsx`.

---

## 11. Internationalisation (`src/i18n/`)

- **Supported languages (10):** English (`en`), Kiswahili (`sw`), Français (`fr`), Español (`es`), Português (`pt`), Deutsch (`de`), Italiano (`it`), العربية (`ar`), हिन्दी (`hi`), 中文 (`zh`).
- Locale files in `src/i18n/locales/*.json` follow the same key structure: `brand`, `nav`, `common`, `auth`, `language`, `footer`.
- **Language resolution order:** ① manual choice stored in `localStorage("i18nextLng")` → ② country detected from the browser locale (or timezone fallback) via `countryLanguageMap` (e.g. KE/TZ/RW/UG → sw, FRA → fr, SA/EG → ar, IN → hi, CN → zh, ...) → ③ English fallback.
- A custom `countryBased` detector drives the initial language; users can always switch via the `LanguageSwitcher` in the navbar. English is the fallback language.

---

## 12. Styling & theming

- Tailwind CSS with `darkMode: ["class"]`; the `dark` class toggles the dark theme (managed by `ThemeContext`).
- Custom palette in `tailwind.config.js`: both `green` and `blue` palettes map to a single **brand-green scale** (`50–950`, anchors `500:#1f9a66` / `700:#106342` / `800:#115036`), so legacy `blue-*` classes and semantic `green-*`/status classes all render as the brand green; plus `paper`/`ink` surfaces; fonts **Inter** (sans) and **Fraunces** (display/serif headings); `shadow-soft`/`shadow-card`.
- Global styles (`index.css`): chart CSS variables for light/dark, `color-scheme` handling, heading font-family rules, `.spinner`, and the landing `reveal` animation (reduced-motion aware).

---

## 13. Utilities & error handling (`src/lib/utils.ts`)

- `cn(...inputs)` — clsx + tailwind-merge.
- `formatDate(dateString)` — `Date.toLocaleString()`.
- `getApiErrorMessage(error, fallback)` — converts DRF validation responses into a single toast-friendly message: cleans whitespace, never exposes stack traces / DB internals / long or HTML payloads, prefers `detail`/`message`, then joins per-field errors as `Field: message`.

---

## 14. Deployment

- **Vercel:** `vercel.json` sets framework `vite`, `buildCommand: npm run build`, `outputDirectory: dist`, and SPA rewrites to `index.html`. `.env.production` points `VITE_API_URL` at the hosted API and can be overridden via Vercel environment variables.
- **Docker:** `Dockerfile` (node:22-alpine) installs deps and runs the dev server on port 3000; the repo root `compose.yaml` wires services together.

---

## 15. Known issues, leaks & gaps — audit + fixes applied

Section 15 documents the findings of a source audit and the fixes that were
applied. Items marked **FIXED** have been changed in the code; **REMAINING**
items are intentional or blocked on backend APIs.

### 15.1 Data & secrets leaking to the browser console — FIXED

All `console.log`/`console.error(data)` calls were removed so tokens and
sensitive payloads can no longer reach the dev console:

| Location | Fix |
|---|---|
| `src/hooks/api/auth.ts` | Removed `console.log("Login successful", data)` (tokens). |
| `src/pages/auth/PasswordResetConfirm.tsx` | Removed logging of reset URL (contains uid + reset token). |
| `src/components/transactions/transactionForm.tsx` | Removed `console.log(values)` (transaction payload). |
| `src/pages/members/MembersView.tsx` | Removed `console.log("members account", …)`. |
| `src/components/NavBar.tsx` | Removed the dead `console.log("Logged out")`. |

### 15.2 Session & token handling — FIXED

1. **AuthContext FIXME resolved:** the access token is now **verified against
   the backend** (`GET /auth/me`) on restore. A tampered token is rejected
   there, the response interceptor refreshes it, and only a failed refresh logs
   the user out (`src/contexts/AuthContext.tsx`).
2. **`expiresAt` is now enforced:** if the local access token is missing or
   past its 12-hour expiry, the app refreshes the token instead of trusting it.
3. **`useLogin` no longer double-writes or logs tokens** — storage happens once
   in `AuthContext.login()`.
4. **REMAINING (trade-off):** tokens still live in `localStorage` (XSS-exposed;
   the standard SPA trade-off). **REMAINING:** `AuthContext` refresh on mount
   and the `lib/api.ts` 401 refresh queue are independent flows; both mutate the
   same storage keys but are idempotent in practice.
5. **Hardcoded demo credentials are now DEV-only** — the `admin@example.com /
   admin12345` hint only renders when `import.meta.env.DEV === true`
   (`SignIn.tsx`), so it never appears in a production build.

### 15.3 Broken or inaccessible UI — FIXED

1. **Navbar dropdown restored:** the avatar trigger is enabled, shows the
   user's profile image (with placeholder fallback) and username, and opens the
   Profile / Logout menu.
2. **Logout actually logs out:** the dropdown "Log out" item opens a
   **confirmation modal**, then ends the server session (`useLogout`) and clears
   the local session immediately (`AuthContext.logout()`).
3. **Role badge restored:** the user's role (`role_display`) shows next to the
   username in the dropdown.

### 15.4 Routes & pages that lead nowhere — FIXED

1. **Users "Create User" no longer 404s:** the button now shows an informative
   toast instead of linking to the non-existent `/users/edit`
   (`src/pages/Users.tsx`).
2. **`/transactions/edit/:transactionId?` is a real page:** `TransactionsEdit`
   now renders a "New Transaction" page reusing the shared `TransactionForm`.
3. **Placeholder routes improved:** `/sms`, `/emails` and `/expenses` now show a
   consistent "not available yet — API not implemented" screen with a link
   back to the dashboard (the backend endpoints do not exist yet, so these stay
   stubs).
4. **Member → new loan prefill:** "New application" on a member page links to
   `/loans/edit?member=<membership_number>`, and `LoansEdit` now reads the
   `?member=` query parameter and pre-selects that member in step 1.

### 15.5 Dead / legacy code — FIXED

1. **Legacy hooks rewired:** `useDataFetch`, `useFetchSingleObject` and
   `useDashboardData` now use the shared authenticated `api` client (they
   previously called bare `axios` with no `Authorization` header) and respect
   `useEffect` cleanup + dependency arrays.
2. **Base-URL is now a single source of truth:** `src/constants.ts` exports
   `apiBaseUrl` with a fallback (and trailing slashes stripped); `src/lib/api.ts`
   consumes it, so a missing `VITE_API_URL` can no longer produce `undefined/...`
   requests.
3. **Dead components removed:** `components/AuthLayout.tsx`,
   `components/ReactTable.tsx` and `components/settings/tabs/update-profile.tsx`
   (the stub Settings never used — its "Update Profile" tab renders
   `pages/Profile.tsx`).
4. **Withdrawal detection fixed:** `useDashboardData` compares
   `transaction_type === "withdrawal"` (previously `includes("Withdrawal")`).

### 15.6 REMAINING items

1. **i18n coverage is partial:** all 10 languages are wired with identical key
   sets, but only the navbar/sidebar/login/footer consume `i18next` — tables,
   forms, dashboard cards, modals and toasts are hard-coded English. Translating
   the whole UI is a separate, large workstream.
2. **Placeholder modules depend on backend APIs** (bulk SMS/email, expenses)
   and cannot be implemented without them.
3. **`useDashboardData`, `useDataFetch`, `useFetchSingleObject` remain unused**
   by any page (now safe to use); they are kept as utilities.
4. **Logout relies on `GET /auth/logout`** succeeding; local logout always
   happens regardless of the network result.