from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    LoanApplicationViewSet,
    LoanTypeViewSet,
    MemberEligibilityView,
    MemberLoanAccountViewSet,
    MemberLoanApplicationViewSet,
)


app_name = "loans"

router = DefaultRouter()
router.register(r"loan-types", LoanTypeViewSet, basename="loan-type")
router.register(r"loans", LoanApplicationViewSet, basename="loan-application")

# Member self-service matches must precede the staff `loans/<application_number>/`
# detail routes, otherwise "me"/"accounts"/"eligibility" would be treated as an
# application number.
member_accounts_router = DefaultRouter()
member_accounts_router.register(r"loans/me/accounts", MemberLoanAccountViewSet, basename="my-loan-account")

member_router = DefaultRouter()
member_router.register(r"loans/me", MemberLoanApplicationViewSet, basename="my-loan")

urlpatterns = [
    *member_accounts_router.urls,
    path("loans/me/eligibility/", MemberEligibilityView.as_view(), name="my-eligibility"),
    *member_router.urls,
    *router.urls,
]