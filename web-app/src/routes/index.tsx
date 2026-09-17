import { createBrowserRouter } from "react-router-dom";
// Layout component
import { RootLayout } from "@/RootLayout.tsx";
// pages
import App from "../App.tsx";
import ErrorPage from "../pages/ErrorPage.tsx";
import DashBoard from "../pages/DashBoard.tsx";
import LandingPage from "@/pages/LandingPage.tsx";
import { Auth } from "@/contexts/AuthContext.tsx";
// authentication
import SignIn from "../pages/auth/SignIn.tsx";
import SignUp from "../pages/auth/SignUp.tsx";
import ForgotPassword from "../pages/auth/ForgotPassword.tsx";
import PasswordResetConfirm from "../pages/auth/PasswordResetConfirm.tsx";
import VerifyEmail from "../pages/auth/VerifyEmail.tsx";
import PinSetup from "../pages/auth/PinSetup.tsx";
import GroupsPage from "@/pages/member/GroupsPage";
import InviteAccept from "@/pages/groups/InviteAccept.tsx";
import MemberLoans from "@/pages/member/MemberLoans";
import GroupDetailPage from "@/pages/member/GroupDetailPage.tsx";
import Wallet from "@/pages/member/Wallet";
import Notifications from "@/pages/member/Notifications";
import Community from "@/pages/member/Community";
import ShareOuts from "@/pages/member/ShareOuts";
// Members
import Members from "@/pages/members/Members.tsx";
import MembersEdit from "@/pages/members/MembersEdit.tsx";
import MembersView from "@/pages/members/MembersView.tsx";
// accounts
import Accounts from "../pages/accounts/Accounts.tsx";
import AccountsEdit from "../pages/accounts/AccoutsEdit.tsx";
import AccountsView from "../pages/accounts/AccountsView.tsx";
// Transactions
import Transactions from "../pages/transactions/Transactions.tsx";
import TransactionsEdit from "../pages/transactions/TransactionsEdit.tsx";
import Settings from "../pages/Settings.tsx";
import Loans from "../pages/loans/Loans.tsx";
import Users from "../pages/Users.tsx";
import Profile from "../pages/Profile.tsx";

import LoansEdit from "../pages/loans/LoansEdit.tsx";
import LoansView from "../pages/loans/LoansView.tsx";
import Help from "../pages/Help.tsx";
import { BulkSMS } from "@/pages/sms/BulkSMS.tsx";
import { BulkEmail } from "@/pages/emails/BulkEmail.tsx";
import { WhatsApp } from "@/pages/whatsapp/WhatsApp.tsx";
import { Expenses } from "@/pages/expenses/index.tsx";
import RequireModuleAccess from "@/components/RequireModuleAccess.tsx";
import { AppModule } from "@/lib/access-control.ts";
import PwaGate from "@/components/PwaGate.tsx";
import MemberHome from "@/pages/member/MemberHome.tsx";
import Onboarding from "@/pages/member/Onboarding.tsx";
import RequireVerified from "@/components/RequireVerified.tsx";
import { useUserProfileInfo } from "@/hooks/useUserProfile";

const protectedModulePage = (module: AppModule, element: JSX.Element) => (
  <RequireModuleAccess module={module}>{element}</RequireModuleAccess>
);

// Public home: shows the marketing landing page to visitors, and the
// authenticated app shell (dashboard) to signed-in members.
// eslint-disable-next-line react-refresh/only-export-components
const HomeEntry = () => {
  const { isAuthenticated } = Auth();
  return isAuthenticated ? (
    <PwaGate>
      <App />
    </PwaGate>
  ) : (
    <LandingPage />
  );
};

// Members (role ME) land on their own self-service account page; staff see the
// operations dashboard.
// eslint-disable-next-line react-refresh/only-export-components
const HomeIndex = () => {
  const { profile } = useUserProfileInfo();
  if (profile?.role === "ME") {
    return <MemberHome />;
  }
  return <DashBoard />;
};

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    errorElement: <ErrorPage />,

    children: [
      // ---------- AUTH ROUTES (PWA-gated on mobile) ----------
      {
        path: "/login",
        element: (
          <PwaGate>
            <SignIn />
          </PwaGate>
        ),
      },
      {
        path: "/register",
        element: (
          <PwaGate>
            <SignUp />
          </PwaGate>
        ),
      },
      {
        path: "/forgot-password",
        element: (
          <PwaGate>
            <ForgotPassword />
          </PwaGate>
        ),
      },
      {
        path: "/reset-password",
        element: (
          <PwaGate>
            <PasswordResetConfirm />
          </PwaGate>
        ),
      },
      {
        path: "/verify-email",
        element: (
          <PwaGate>
            <VerifyEmail />
          </PwaGate>
        ),
      },
      {
        path: "/pin-setup",
        element: (
          <PwaGate>
            <PinSetup />
          </PwaGate>
        ),
      },
      {
        path: "/groups/invite/:token",
        element: (
          <PwaGate>
            <InviteAccept />
          </PwaGate>
        ),
      },

      // ---------- STANDALONE ONBOARDING WIZARD ----------
      // Rendered outside the app shell so the member never sees the sidebar or
      // navigation during phone verification → profile → KYC → plan.
      {
        path: "/onboarding",
        element: (
          <PwaGate>
            <Onboarding />
          </PwaGate>
        ),
      },

      // ---------- PUBLIC MARKETING ----------
      {
        path: "/landing",
        element: <LandingPage />,
      },

      // ---------- APP LAYOUT (PWA-gated on mobile) ----------
      {
        path: "/",
        element: <HomeEntry />,
        children: [
          // Home index: member home requires verification/onboarding for ME role
          {
            index: true,
            element: (
              <RequireVerified>
                <HomeIndex />
              </RequireVerified>
            ),
          },
          { path: "profile", element: <Profile /> },
          { path: "help", element: <Help /> },
          { path: "settings", element: <Settings /> },
          // Protected member routes — require verified + onboarded
          {
            element: <RequireVerified />,
            children: [
              { path: "groups", element: <GroupsPage /> },
              { path: "groups/:groupId", element: <GroupDetailPage /> },
              { path: "loans-me", element: <MemberLoans /> },
              { path: "wallet", element: <Wallet /> },
              { path: "notifications", element: <Notifications /> },
              { path: "community", element: <Community /> },
              { path: "share-outs", element: <ShareOuts /> },
            ],
          },
          { path: "members", element: protectedModulePage("members", <Members />) },
          { path: "members/edit/:memberId?", element: protectedModulePage("members", <MembersEdit />) },
          { path: "members/view/:memberId?", element: protectedModulePage("members", <MembersView />) },
          { path: "accounts", element: protectedModulePage("accounts", <Accounts />) },
          { path: "accounts/edit/:accountNo?", element: protectedModulePage("accounts", <AccountsEdit />) },
          { path: "accounts/view/:accountNo", element: protectedModulePage("accounts", <AccountsView />) },
          { path: "transactions", element: protectedModulePage("transactions", <Transactions />) },
          {
            path: "transactions/edit/:transactionId?",
            element: protectedModulePage("transactions", <TransactionsEdit />),
          },
          { path: "loans", element: protectedModulePage("loans", <Loans />) },
          { path: "loans/edit/:loanId?", element: protectedModulePage("loans", <LoansEdit />) },
          { path: "loans/view/:loanId", element: protectedModulePage("loans", <LoansView />) },
          { path: "expenses", element: protectedModulePage("expenses", <Expenses />) },
          { path: "users", element: protectedModulePage("users", <Users />) },
          {path: "sms", element: protectedModulePage("communications", <BulkSMS />)},
          {path: "emails", element: protectedModulePage("communications", <BulkEmail />)},
          {path: "whatsapp", element: protectedModulePage("communications", <WhatsApp />)}
        ],
      },
    ],
  },
]);
