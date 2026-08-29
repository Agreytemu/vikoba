from django.urls import path

from .views import (
    WhatsAppSessionListCreateView,
    WhatsAppSessionDetailView,
    WhatsAppSessionPairView,
    WhatsAppSessionSendTestView,
    WhatsAppSessionBulkSendView,
    WhatsAppSessionRescanView,
)

app_name = "whatsapp"

urlpatterns = [
    path("whatsapp/sessions/", WhatsAppSessionListCreateView.as_view()),
    path("whatsapp/sessions/<str:session_id>/", WhatsAppSessionDetailView.as_view()),
    path("whatsapp/sessions/<str:session_id>/pair/", WhatsAppSessionPairView.as_view()),
    path("whatsapp/sessions/<str:session_id>/rescan/", WhatsAppSessionRescanView.as_view()),
    path("whatsapp/sessions/<str:session_id>/send-test/", WhatsAppSessionSendTestView.as_view()),
    path("whatsapp/sessions/<str:session_id>/bulk/", WhatsAppSessionBulkSendView.as_view()),
]