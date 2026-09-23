from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuditEventViewSet,
    FinancialAccountViewSet,
    FinancialDashboardView,
    FinancialIntegrityView,
    FinancialTransactionViewSet,
    JournalView,
    MemberFinancialDashboardView,
    MemberFinancialTransactionsView,
    MemberStatementView,
    StaffLoanStatementView,
    StaffMemberStatementView,
    StaffWithdrawalReportView,
)

app_name = "finance"

router = DefaultRouter()
router.register(r"accounts", FinancialAccountViewSet, basename="finance-accounts")
router.register(r"transactions", FinancialTransactionViewSet, basename="finance-transactions")
router.register(r"audit", AuditEventViewSet, basename="finance-audit")
router.register(r"me", MemberFinancialTransactionsView, basename="finance-me")
router.register(r"integrity", FinancialIntegrityView, basename="finance-integrity")

urlpatterns = [
    path("journal/", JournalView.as_view({"post": "create"}), name="finance-journal"),
    path("dashboard/", FinancialDashboardView.as_view({"get": "list"}), name="finance-dashboard"),
    path("me/dashboard/", MemberFinancialDashboardView.as_view({"get": "list"}), name="finance-me-dashboard"),
    path("me/statement/", MemberStatementView.as_view({"get": "list"}), name="finance-me-statement"),
    path(
        "statements/<uuid:member_id>/",
        StaffMemberStatementView.as_view({"get": "list"}),
        name="finance-member-statement",
    ),
    path(
        "reports/withdrawals/",
        StaffWithdrawalReportView.as_view({"get": "list"}),
        name="finance-withdrawal-report",
    ),
    path(
        "loans/<str:loan_number>/statement/",
        StaffLoanStatementView.as_view({"get": "list"}),
        name="finance-loan-statement",
    ),
    *router.urls,
]