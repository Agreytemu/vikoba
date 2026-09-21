from django.urls import path

from . import views

urlpatterns = [
    path("webhooks/snippe/", views.snippe_webhook, name="snippe-webhook"),
    path("subscriptions/checkout/", views.SubscriptionCheckoutView.as_view(), name="subscription-checkout"),
    path("subscriptions/me/", views.MySubscriptionView.as_view(), name="my-subscription"),
    path("contributions/pay/", views.ContributionPaymentView.as_view(), name="contribution-pay"),
    path("loans/repay/", views.LoanRepaymentPaymentView.as_view(), name="loan-repay"),
    path("savings/deposit/", views.SavingsDepositPaymentView.as_view(), name="savings-deposit"),
    path("withdrawals/auto/", views.AutoWithdrawalView.as_view(), name="withdrawal-auto"),
    path(
        "withdrawals/<uuid:withdrawal_id>/dispatch/",
        views.WithdrawalPayoutView.as_view(),
        name="withdrawal-dispatch",
    ),
    path(
        "transactions/<str:internal_reference>/",
        views.PaymentTransactionStatusView.as_view(),
        name="payment-status",
    ),
    path("transactions/", views.MyPaymentTransactionsView.as_view(), name="my-payments"),
    path(
        "reconciliation/",
        views.ReconciliationListView.as_view(),
        name="reconciliation-list",
    ),
    path(
        "reconciliation/<int:pk>/resolve/",
        views.ReconciliationResolveView.as_view(),
        name="reconciliation-resolve",
    ),
]