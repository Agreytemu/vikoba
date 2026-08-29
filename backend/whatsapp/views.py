from django.shortcuts import get_object_or_404
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from groups.models import VikobaGroup, GroupMembership
from members.models import Member
from .models import WhatsAppSession
from .service import (
    list_bridge_sessions,
    start_session,
    session_status,
    send_whatsapp,
    send_bulk,
    pair_session,
)
from .serializers import (
    WhatsAppSessionSerializer,
    WhatsAppSessionCreateSerializer,
    WhatsAppTestSendSerializer,
    WhatsAppBulkSendSerializer,
    WhatsAppSessionPairSerializer,
)

STAFF_ROLES = {"AD", "MA", "OP", "FI", "LO", "AC"}


def _is_staff(user):
    return bool(getattr(user, "role", "") in STAFF_ROLES)


def _is_chair_of(user, group):
    if not group or not user.is_authenticated:
        return False
    try:
        member = user.member
    except Member.DoesNotExist:
        return False
    return group.memberships.filter(
        member=member, role=GroupMembership.Role.CHAIRPERSON, is_active=True
    ).exists()


def _is_admin_owner(user, session):
    """The requesting staff member owns the admin device (legacy rows are ours)."""
    if session.owner_type != WhatsAppSession.OwnerType.ADMIN or not _is_staff(user):
        return False
    if session.owner_id is None:
        return True
    return session.owner_id == user.id


def _can_manage(user, session):
    """Who can pair/manage a device:
    - admin devices: the staff member whose account owns them only;
    - chair devices: the chairperson of the group only (never staff).
    """
    if not user or not user.is_authenticated:
        return False
    if session.owner_type == WhatsAppSession.OwnerType.ADMIN:
        return _is_admin_owner(user, session)
    if session.owner_type != WhatsAppSession.OwnerType.CHAIR:
        return False
    if not _is_chair_of(user, session.group):
        return False
    if session.owner_id is None:
        return True
    return session.owner_id == user.id


def _can_see(user, session):
    """Who may see a device listed at all."""
    if _is_staff(user):
        return True
    return _can_manage(user, session)


def _new_session_id(owner_type, group=None, display_name=""):
    import uuid

    token = uuid.uuid4().hex[:10]
    if owner_type == WhatsAppSession.OwnerType.ADMIN:
        prefix = "admin"
    else:
        prefix = f"group-{group.id if group else 'x'}"
    return f"{prefix}-{token}"


class WhatsAppSessionListCreateView(APIView):
    """List devices I can manage; staff can also register a new admin device."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if _is_staff(user):
            # Staff see every device: their own admin device(s) plus all the
            # group chairperson devices (read-only for them).
            sessions = WhatsAppSession.objects.select_related("group").all()
        else:
            # Chairs see the devices of groups they actually chair.
            scoped = []
            for session in WhatsAppSession.objects.select_related("group").filter(
                owner_type=WhatsAppSession.OwnerType.CHAIR
            ):
                if session.group and _is_chair_of(user, session.group):
                    scoped.append(session)
            sessions = scoped

        payload = {}
        try:
            payload = list_bridge_sessions()
        except Exception:
            payload = {}

        data = []
        for session in sessions:
            if not _can_see(user, session):
                continue
            merged = payload.get(session.session_id, {}) or {}
            if merged.get("phone"):
                session.phone = merged["phone"]
            if merged.get("status"):
                session.status = merged["status"]
            session.can_manage = _can_manage(user, session)
            data.append(WhatsAppSessionSerializer(session).data)
        return Response(data)

    def post(self, request):
        user = request.user
        serializer = WhatsAppSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        owner_type = serializer.validated_data["owner_type"]
        group = serializer.validated_data.get("group")
        if owner_type == WhatsAppSession.OwnerType.ADMIN:
            if not _is_staff(user):
                return Response(
                    {"detail": "Only staff can create admin WhatsApp devices."},
                    status=http_status.HTTP_403_FORBIDDEN,
                )
        else:
            group = serializer.validated_data["group"]
            if not _is_chair_of(user, group):
                return Response(
                    {"detail": "Only this group's chairperson can connect a device."},
                    status=http_status.HTTP_403_FORBIDDEN,
                )
            existing = (
                WhatsAppSession.objects.filter(
                    owner_type=WhatsAppSession.OwnerType.CHAIR, group=group
                )
                .order_by("-is_primary")
                .first()
            )
            if existing:
                start_session(existing)
                return Response(
                    WhatsAppSessionSerializer(existing).data
                )

        session = WhatsAppSession.objects.create(
            session_id=_new_session_id(owner_type, group),
            owner=user,
            owner_type=owner_type,
            group=group,
            created_by=user,
            display_name=serializer.validated_data.get("display_name", "") or "",
        )
        start_session(session)
        return Response(
            WhatsAppSessionSerializer(session).data,
            status=http_status.HTTP_201_CREATED,
        )


class WhatsAppSessionDetailView(APIView):
    """Single session status (includes the live pairing code while awaiting)."""

    permission_classes = [IsAuthenticated]

    def get_object(self, request, session_id):
        session = get_object_or_404(WhatsAppSession, session_id=session_id)
        if not _can_manage(request.user, session):
            raise PermissionError
        return session

    def get(self, request, session_id):
        try:
            session = self.get_object(request, session_id)
        except PermissionError:
            return Response(
                {"detail": "You do not manage this device."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        merged = session_status(session, want_pairing=True)
        session.refresh_from_bridge(merged)
        session.can_manage = True
        return Response({
            **WhatsAppSessionSerializer(session).data,
            "pairing_code": merged.get("pairing_code"),
            "qr": merged.get("qr"),
        })

    def patch(self, request, session_id):
        try:
            session = self.get_object(request, session_id)
        except PermissionError:
            return Response(
                {"detail": "You do not manage this device."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        if request.data.get("is_primary") is True:
            if session.owner_type == WhatsAppSession.OwnerType.ADMIN:
                scope = {"owner_type": session.owner_type, "group__isnull": True}
            else:
                scope = {"owner_type": session.owner_type, "group": session.group}
            if session.owner_id is not None:
                scope["owner"] = session.owner
            WhatsAppSession.objects.filter(**scope).update(is_primary=False)
            session.is_primary = True
        if "display_name" in request.data:
            session.display_name = request.data["display_name"]
        session.save()
        return Response(WhatsAppSessionSerializer(session).data)

    def delete(self, request, session_id):
        try:
            session = self.get_object(request, session_id)
        except PermissionError:
            return Response(
                {"detail": "You do not manage this device."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        try:
            from .service import _bridge_call

            _bridge_call("DELETE", f"/sessions/{session.session_id}?clear=1")
        except Exception:
            pass
        session.delete()
        return Response({"detail": "Device removed."})


class WhatsAppSessionPairView(APIView):
    """Request a WhatsApp pairing code for this device.

    The backend also supports the standard QR device-link flow: when Baileys
    emits a QR code, the frontend polls it and connects once the phone scans it.
    The pairing-code response remains as a fallback option.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = get_object_or_404(WhatsAppSession, session_id=session_id)
            if not _can_manage(request.user, session):
                raise PermissionError
        except PermissionError:
            return Response(
                {"detail": "You do not manage this device."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        serializer = WhatsAppSessionPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # The bridge may have restarted and forgotten the in-memory session;
        # re-starting is idempotent and guarantees a socket exists to pair on.
        start_session(session)
        result = pair_session(
            session.session_id, serializer.validated_data["phone"]
        )
        if result.get("ok"):
            return Response(result)
        return Response(result, status=http_status.HTTP_400_BAD_REQUEST)


class WhatsAppSessionSendTestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = get_object_or_404(WhatsAppSession, session_id=session_id)
            if not _can_manage(request.user, session):
                raise PermissionError
        except PermissionError:
            return Response(
                {"detail": "You do not manage this device."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        serializer = WhatsAppTestSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = send_whatsapp(
            session.session_id,
            serializer.validated_data["to"],
            serializer.validated_data["text"],
        )
        return Response(result)


class WhatsAppSessionBulkSendView(APIView):
    """Send a broadcast from one device to a group's active members (or a list)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = get_object_or_404(WhatsAppSession, session_id=session_id)
            if not _can_manage(request.user, session):
                raise PermissionError
        except PermissionError:
            return Response(
                {"detail": "You do not manage this device."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        serializer = WhatsAppBulkSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phones = list(serializer.validated_data.get("phones") or [])
        group_id = serializer.validated_data.get("group_id")
        if group_id:
            group = get_object_or_404(VikobaGroup, pk=group_id)
            phones += list(
                group.memberships.filter(
                    member__phone_number__isnull=False, is_active=True
                ).values_list("member__phone_number", flat=True)
            )
        phones = list(dict.fromkeys(phones))
        if not phones:
            return Response(
                {"detail": "No recipients resolved."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        result = send_bulk(
            session.session_id,
            phones,
            serializer.validated_data["text"],
        )
        return Response(result)


class WhatsAppSessionRescanView(APIView):
    """Restart an existing device's WhatsApp socket to regenerate its QR code.

    Reuses the same session id (no new database row, no extra bridge session)
    so repeatedly re-scanning a half-linked device does not pile up sessions.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = get_object_or_404(WhatsAppSession, session_id=session_id)
            if not _can_manage(request.user, session):
                raise PermissionError
        except PermissionError:
            return Response(
                {"detail": "You do not manage this device."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        # The bridge may have dropped the socket; re-starting is idempotent and
        # regenerates a fresh QR on the same session id.
        start_session(session)
        merged = session_status(session, want_pairing=True)
        session.refresh_from_bridge(merged)
        session.can_manage = True
        return Response(
            {
                **WhatsAppSessionSerializer(session).data,
                "pairing_code": merged.get("pairing_code"),
                "qr": merged.get("qr"),
            }
        )