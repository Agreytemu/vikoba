from django.urls import path

from kyc import views

app_name = "kyc"

urlpatterns = [
    path("kyc/me/", views.MeKYCProfileView.as_view(), name="kyc-me"),
    path("kyc/me/verify/", views.MeKYCVerifyView.as_view(), name="kyc-me-verify"),
    path("kyc/me/requests/", views.MeKYCRequestsView.as_view(), name="kyc-me-requests"),
    path("kyc/me/timeline/", views.MeKYCTimelineView.as_view(), name="kyc-me-timeline"),
    path("kyc/admin/", views.KYCAdminOverviewView.as_view(), name="kyc-admin"),
    path(
        "kyc/admin/<str:membership_number>/",
        views.KYCAdminDetailView.as_view(),
        name="kyc-admin-detail",
    ),
    path(
        "kyc/admin/<str:membership_number>/review/",
        views.KYCAdminReviewView.as_view(),
        name="kyc-admin-review",
    ),
]