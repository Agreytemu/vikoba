from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuditEventViewSet,
    FinancialAccountViewSet,
    FinancialTransactionViewSet,
    JournalView,
    MemberFinancialTransactionsView,
)

app_name = "finance"

router = DefaultRouter()
router.register(r"accounts", FinancialAccountViewSet, basename="finance-accounts")
router.register(r"transactions", FinancialTransactionViewSet, basename="finance-transactions")
router.register(r"audit", AuditEventViewSet, basename="finance-audit")
router.register(r"me", MemberFinancialTransactionsView, basename="finance-me")

urlpatterns = [
    path("journal/", JournalView.as_view({"post": "create"}), name="finance-journal"),
    *router.urls,
]