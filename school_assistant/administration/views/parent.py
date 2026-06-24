"""
ADMINISTRATION -- ADMIN-ROLE VIEWS
=====================================
"""

from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StudentProfile
from accounts.permissions import IsAdmin
from administration.models import Complaint, Inventory, SchoolEvent, EventParticipation, Certificate
from administration.serializers.admin import (
    ComplaintSerializer, InventorySerializer, SchoolEventSerializer,
    EventParticipationSerializer, CertificateSerializer, CertificateGenerateSerializer,
)


class ComplaintViewSet(viewsets.ModelViewSet):
    """
    Master Complaint Board (Page 13) -- shows complaints from EVERY role.

    Permission split (this was a bug in an earlier draft -- IsAdmin alone
    blocked Teacher/Student/Parent from filing their own complaints,
    which the spec explicitly requires via Pages 22/30/39):
      - create  -> any authenticated user (anyone can file a complaint)
      - list/retrieve/update -> Admin only (Master Complaint Board, status updates)
    """
    queryset = Complaint.objects.select_related("reporter__role", "against_user").all().order_by("-created_at")
    serializer_class = ComplaintSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        return [IsAdmin()]

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class InventoryViewSet(viewsets.ModelViewSet):
    """CRUD /api/admin/inventory"""
    serializer_class = InventorySerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        qs = Inventory.objects.all()
        room = self.request.query_params.get("room")  # supports Page 10's "filter by room" requirement
        if room:
            qs = qs.filter(assigned_to_room=room)
        return qs


class InventorySummaryView(APIView):
    """GET /api/admin/inventory/summary"""
    permission_classes = [IsAdmin]

    def get(self, request):
        items = Inventory.objects.all()
        return Response({
            "total_items": items.count(),
            "total_quantity": sum(i.total_quantity for i in items),
            "by_room": list(items.values("assigned_to_room").distinct()),
        })


class SchoolEventViewSet(viewsets.ModelViewSet):
    """
    CRUD /api/admin/events -- Admin only.
    Also backs GET /api/events/upcoming -- that one must be readable by
    EVERY role (Pages 27/34: Student/Parent read-only events list), so
    permissions are split by action rather than one fixed class.
    """
    queryset = SchoolEvent.objects.all().order_by("-event_date")
    serializer_class = SchoolEventSerializer

    def get_permissions(self):
        if self.action == "list" or self.action == "retrieve":
            return [IsAuthenticated()]
        return [IsAdmin()]

    def perform_create(self, serializer):
        # "automatically triggers alert notifications to students and
        # parents" (spec, Page 11) -- TODO: dispatch Notification rows
        # here once the notification-dispatch helper is built.
        serializer.save(created_by_admin=self.request.user)


class EventParticipationViewSet(viewsets.ModelViewSet):
    """Register participants per event, assign position/certificate."""
    queryset = EventParticipation.objects.select_related("student__user", "event").all()
    serializer_class = EventParticipationSerializer
    permission_classes = [IsAdmin]


class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/admin/certificates, GET /api/admin/certificates/{id}"""
    queryset = Certificate.objects.select_related("student__user").all().order_by("-created_at")
    serializer_class = CertificateSerializer
    permission_classes = [IsAdmin]


class CertificateGenerateView(APIView):
    """
    POST /api/admin/certificates/generate

    Currently fills a plain template -- NOT yet AI-drafted. The spec's
    "Certificates Bot" (AI-generated text) is part of the chatbot work
    planned separately; swap the body of this method for a call to that
    LLM service once it exists, keeping everything else (saving the
    Certificate row) the same.
    """
    permission_classes = [IsAdmin]

    TEMPLATES = {
        "leaving": "This is to certify that {name} (Roll No. {roll}) has been a student of this institution and is granted leave to pursue further studies.",
        "merit": "This certificate is proudly awarded to {name} (Roll No. {roll}) in recognition of outstanding academic merit.",
        "clearance": "This is to certify that {name} (Roll No. {roll}) has cleared all dues and has no outstanding obligations to the institution.",
        "appreciation": "This certificate of appreciation is presented to {name} (Roll No. {roll}) for their valuable contribution.",
        "event": "This certificate is awarded to {name} (Roll No. {roll}) for their participation and achievement in the school event.",
    }

    def post(self, request):
        serializer = CertificateGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        student = StudentProfile.objects.select_related("user").get(id=data["student_id"])
        text = self.TEMPLATES[data["cert_type"]].format(
            name=student.user.full_name, roll=student.roll_number or "N/A"
        )
        if data.get("custom_note"):
            text += " " + data["custom_note"]

        certificate = Certificate.objects.create(
            student=student, cert_type=data["cert_type"],
            generated_text=text, generated_by_admin=request.user,
        )
        return Response(CertificateSerializer(certificate).data, status=201)


class CertificateDownloadView(APIView):
    """
    GET /api/admin/certificates/{id}/download
    Returns the certificate text for the frontend to render as a PDF
    (or wire up a PDF library here directly -- left as a TODO, since PDF
    generation is a separate concern from the data layer).
    """
    permission_classes = [IsAdmin]

    def get(self, request, id):
        certificate = Certificate.objects.select_related("student__user").get(id=id)
        return Response(CertificateSerializer(certificate).data)from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from accounts.permissions import IsParent
from administration.models import Complaint, EventParticipation, Certificate
from administration.serializers.parent import (
    ParentComplaintSerializer, ParentEventParticipationSerializer, ParentCertificateSerializer
)

class ParentComplaintViewSet(viewsets.ModelViewSet):
    """Parents can file complaints and view their own complaints."""
    serializer_class = ParentComplaintSerializer
    permission_classes = [IsAuthenticated, IsParent]

    def get_queryset(self):
        return Complaint.objects.filter(reporter=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)


class ParentEventParticipationViewSet(viewsets.ReadOnlyModelViewSet):
    """Parents can view their child's event participations."""
    serializer_class = ParentEventParticipationSerializer
    permission_classes = [IsAuthenticated, IsParent]

    def get_queryset(self):
        return EventParticipation.objects.filter(student__parents__user=self.request.user)


class ParentCertificateViewSet(viewsets.ReadOnlyModelViewSet):
    """Parents can view their child's certificates."""
    serializer_class = ParentCertificateSerializer
    permission_classes = [IsAuthenticated, IsParent]

    def get_queryset(self):
        return Certificate.objects.filter(student__parents__user=self.request.user).order_by("-created_at")
