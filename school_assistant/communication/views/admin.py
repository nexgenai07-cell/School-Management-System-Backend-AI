"""
COMMUNICATION -- ADMIN-ROLE VIEWS
====================================
"""

from rest_framework import generics, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from accounts.permissions import IsAdmin
from accounts.models import User
from communication.models import Notification, MediaCampaignLog
from communication.serializers.admin import (
    NotificationSerializer, MediaCampaignLogSerializer, AdminNotificationCreateSerializer
)


class NotificationListView(generics.ListAPIView):
    """GET /api/support/notifications"""
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(receiver=self.request.user).order_by("-created_at")

    @swagger_auto_schema(
        operation_description="Get all notifications for the logged-in user",
        responses={200: NotificationSerializer(many=True)},
        tags=['support']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class UnreadNotificationListView(generics.ListAPIView):
    """GET /api/notifications/unread"""
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(receiver=self.request.user, is_read=False).order_by("-created_at")

    @swagger_auto_schema(
        operation_description="Get unread notifications for the logged-in user",
        responses={200: NotificationSerializer(many=True)},
        tags=['support']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class MarkNotificationReadView(APIView):
    """PUT /api/notifications/read/{id}"""

    @swagger_auto_schema(
        operation_description="Mark a specific notification as read",
        responses={200: openapi.Response("Marked as read")},
        tags=['support']
    )
    def put(self, request, id):
        Notification.objects.filter(id=id, receiver=request.user).update(is_read=True)
        return Response({"detail": "Marked as read."})


class MarkAllNotificationsReadView(APIView):
    """PUT /api/notifications/read-all"""

    @swagger_auto_schema(
        operation_description="Mark all notifications as read for the logged-in user",
        responses={200: openapi.Response("All notifications marked as read")},
        tags=['support']
    )
    def put(self, request):
        Notification.objects.filter(receiver=request.user, is_read=False).update(is_read=True)
        return Response({"detail": "All notifications marked as read."})


# ✅ NEW: Admin Manual Notification Create
class AdminNotificationCreateView(APIView):
    """
    POST /api/admin/notifications
    Admin can send manual notifications to:
    - Specific user (receiver_id)
    - All users of a specific role (target_role)
    """
    permission_classes = [IsAdmin]

    @swagger_auto_schema(
        operation_description="Admin manually create notifications (specific user or role-based)",
        request_body=AdminNotificationCreateSerializer,
        responses={201: "Notification(s) created"},
        tags=['admin']
    )
    def post(self, request):
        serializer = AdminNotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        message = data.get('message')
        target_role = data.get('target_role')
        receiver_id = data.get('receiver_id')
        sender = request.user

        receivers = []

        # CASE 1: Specific user
        if receiver_id:
            try:
                user = User.objects.get(id=receiver_id, is_active=True)
                receivers = [user]
            except User.DoesNotExist:
                return Response(
                    {"detail": f"User with id {receiver_id} not found or inactive."},
                    status=404
                )

        # CASE 2: Role-based
        elif target_role:
            if target_role == 'All':
                receivers = User.objects.filter(is_active=True, status='Active')
            else:
                receivers = User.objects.filter(
                    role__role_name=target_role,
                    is_active=True,
                    status='Active'
                )

        if not receivers:
            return Response(
                {"detail": "No active users found for the given criteria."},
                status=400
            )

        notifications = []
        for receiver in receivers:
            notifications.append(Notification(
                sender=sender,
                receiver=receiver,
                message=message,
                type='in_app',
                reference_type='Admin'
            ))

        Notification.objects.bulk_create(notifications)

        return Response({
            "detail": f"Notification sent to {len(notifications)} user(s).",
            "count": len(notifications)
        }, status=201)


class MediaCampaignViewSet(viewsets.ModelViewSet):
    """GET/POST /api/admin/campaigns"""
    queryset = MediaCampaignLog.objects.all().order_by("-created_at")
    serializer_class = MediaCampaignLogSerializer
    permission_classes = [IsAdmin]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['platform', 'status']
    search_fields = ['post_content', 'post_type']
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(created_by_admin=self.request.user)


class PublishCampaignView(APIView):
    """POST /api/admin/campaigns/publish"""
    permission_classes = [IsAdmin]

    @swagger_auto_schema(
        operation_description="Publish a campaign (draft → published)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'campaign_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the campaign to publish'),
            }
        ),
        responses={200: openapi.Response("Campaign published")},
        tags=['admin']
    )
    def post(self, request):
        campaign_id = request.data.get("campaign_id")
        campaign = MediaCampaignLog.objects.filter(id=campaign_id).first()
        if not campaign:
            return Response({"detail": "Campaign not found."}, status=404)
        campaign.status = "published"
        campaign.save()
        return Response({"detail": "Campaign published.", "status": campaign.status})


class CampaignLogListView(generics.ListAPIView):
    """GET /api/admin/campaigns/logs"""
    queryset = MediaCampaignLog.objects.all().order_by("-created_at")
    serializer_class = MediaCampaignLogSerializer
    permission_classes = [IsAdmin]

    @swagger_auto_schema(
        operation_description="Get campaign logs",
        responses={200: MediaCampaignLogSerializer(many=True)},
        tags=['admin']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)