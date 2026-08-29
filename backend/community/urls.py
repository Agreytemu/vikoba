from rest_framework.routers import DefaultRouter

from .views import AnnouncementViewSet, MeetingViewSet

app_name = "community"

router = DefaultRouter()
router.register(r"announcements", AnnouncementViewSet, basename="announcement")
router.register(r"meetings", MeetingViewSet, basename="meeting")

urlpatterns = [
    *router.urls,
]