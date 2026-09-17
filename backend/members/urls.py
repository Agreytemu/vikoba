from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    MemberViewSet,
    MemberMeView,
    MemberMeVerificationStatusView,
    MemberMeNextOfKinView,
    MemberMeKYCDocumentsView,
    MemberMePhoneOTPRequestView,
    MemberMePhoneOTPVerifyView,
    MemberMeSubmitForReviewView,
    MemberMeOnboardingView,
    MemberKYCVerifyView,
)
app_name = "members"

# allow the urlconf to be automatically generated.
router = DefaultRouter()
# router.register(r'members', MemberViewSet, basename='members')
# urlpatterns = router.urls

urlpatterns = [
    # Self-service endpoints must be declared BEFORE the parameterised member
    # routes, otherwise 'me' would be captured as a membership_number.
    path('members/me/verification-status/', MemberMeVerificationStatusView.as_view()),
    path('members/me/request-otp/', MemberMePhoneOTPRequestView.as_view()),
    path('members/me/verify-otp/', MemberMePhoneOTPVerifyView.as_view()),
    path('members/me/next-of-kin/', MemberMeNextOfKinView.as_view()),
    path('members/me/kyc-documents/', MemberMeKYCDocumentsView.as_view()),
    path('members/me/submit-for-review/', MemberMeSubmitForReviewView.as_view()),
    path('members/me/onboarding/', MemberMeOnboardingView.as_view()),
    path('members/me/', MemberMeView.as_view()),
    path('members/', MemberViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('members/<str:membership_number>/', MemberViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update' })),
    path('members/<str:membership_number>/kyc-documents/', MemberViewSet.as_view({'post': 'upload_kyc_document'})),
    path('members/<str:membership_number>/kyc-documents/<int:doc_id>/verify/', MemberKYCVerifyView.as_view()),
]