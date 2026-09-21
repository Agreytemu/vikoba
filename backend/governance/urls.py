from django.urls import path

from governance import views

app_name = "governance"

urlpatterns = [
    path("approvals/", views.ApprovalInboxView.as_view(), name="approval-inbox"),
    path("approvals/<int:approval_id>/", views.ApprovalDetailView.as_view(), name="approval-detail"),
    path("approvals/<int:approval_id>/action/", views.ApprovalActionView.as_view(), name="approval-action"),
    path("approvals/<int:approval_id>/history/", views.ApprovalHistoryView.as_view(), name="approval-history"),
    path(
        "groups/<int:group_id>/withdrawal-policy/",
        views.GroupWithdrawalPolicyView.as_view(),
        name="group-withdrawal-policy",
    ),
]