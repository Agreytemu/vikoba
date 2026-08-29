from rest_framework import generics, mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.permissions import HasCommunityAccess

from .models import Announcement, Meeting
from .serializers import AnnouncementSerializer, MeetingSerializer

STAFF_ROLES = {"ADMIN", "MANAGER", "OPERATION", "FINANCE", "ACCOUNTANT", "LOAN_OFFICER"}


def _is_staff(user):
    return bool(user.is_authenticated) and (user.is_staff or user.role in STAFF_ROLES)


class AnnouncementViewSet(viewsets.ReadOnlyModelViewSet):
    """Members read published announcements; staff can read/create/update/publish."""

    permission_classes = [IsAuthenticated]
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        if _is_staff(self.request.user):
            return Announcement.objects.all()
        return Announcement.objects.filter(status=Announcement.Status.PUBLISHED)

    def get_permissions(self):
        if self.action in ("create", "partial_update", "destroy"):
            self.permission_classes = [HasCommunityAccess]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class MeetingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """All authenticated users see meetings; staff create/edit/delete."""

    permission_classes = [IsAuthenticated]
    serializer_class = MeetingSerializer
    queryset = Meeting.objects.all()

    def get_permissions(self):
        if self.action in ("create", "partial_update", "destroy"):
            self.permission_classes = [HasCommunityAccess]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)