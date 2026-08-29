from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    AccountViewSet,
    DepositRequestDecisionView,
    MemberAccountTransactionsView,
    MemberDepositRequestView,
    MemberWithdrawalRequestView,
    ProductViewSet,
    TransactionViewSet,
    MyAccountsView,
    WithdrawalRequestDecisionView,
)
app_name = "accounts"

# allow the urlconf to be automatically generated.
router = DefaultRouter()
router.register(r'accounts', AccountViewSet, basename='accounts')
router.register(r'products', ProductViewSet, basename='products')
router.register(r'transactions', TransactionViewSet, basename='transactions')

urlpatterns = [
    path("accounts/me/", MyAccountsView.as_view(), name="my-accounts"),
    path("accounts/me/deposits/", MemberDepositRequestView.as_view(), name="my-deposits"),
    path("accounts/me/withdrawals/", MemberWithdrawalRequestView.as_view(), name="my-withdrawals"),
    path(
        "accounts/me/<str:account_number>/transactions/",
        MemberAccountTransactionsView.as_view(),
        name="my-account-transactions",
    ),
    path("accounts/deposits/<int:deposit_id>/decision/", DepositRequestDecisionView.as_view(),
         name="deposit-decision"),
    path("accounts/withdrawals/<int:withdrawal_id>/decision/", WithdrawalRequestDecisionView.as_view(),
         name="withdrawal-decision"),
    *router.urls,
]
