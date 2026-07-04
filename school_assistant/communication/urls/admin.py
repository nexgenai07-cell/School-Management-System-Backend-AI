from django.urls import path

from communication.views.admin import (
    NotificationListView, UnreadNotificationListView, MarkNotificationReadView,
    MarkAllNotificationsReadView, MediaCampaignViewSet, PublishCampaignView, CampaignLogListView,
    AdminNotificationCreateView,  # ✅ New import
)

urlpatterns = [
    # --- Notification Endpoints (Frontend) ---
    path("support/notifications", NotificationListView.as_view(), name="support-notifications-list"),
    path("notifications/unread", UnreadNotificationListView.as_view(), name="notifications-unread-list"),
    path("notifications/read/<int:id>", MarkNotificationReadView.as_view(), name="notifications-read"),
    path("notifications/read-all", MarkAllNotificationsReadView.as_view(), name="notifications-read-all"),

    # --- Admin Manual Notification (NEW) ---
    path("admin/notifications", AdminNotificationCreateView.as_view(), name="admin-notifications-create"),

    # --- Campaigns ---
    path("admin/campaigns", MediaCampaignViewSet.as_view({"get": "list", "post": "create"}), name="admin-campaigns"),
    path("admin/campaigns/publish", PublishCampaignView.as_view(), name="admin-campaigns-publish"),
    path("admin/campaigns/logs", CampaignLogListView.as_view(), name="admin-campaigns-logs"),
]