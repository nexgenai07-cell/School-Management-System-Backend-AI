'''
PERSON 1 -- services.py for 'communication' app
Business logic + Casbin permission checks live here.
Existing models.py/views/serializers in this app are NOT touched.
'''
from communication.models import Notification
from accounts.models import User


def get_notification_history_service(receiver_role=None, limit=20):
    qs = Notification.objects.select_related("sender", "receiver").order_by("-created_at")
    if receiver_role:
        qs = qs.filter(receiver__role__role_name__iexact=receiver_role)
    return list(qs.values("message", "type", "receiver__full_name", "created_at")[:limit])


def send_notification_service(sender, target_role, message):
    targets = User.objects.filter(role__role_name__iexact=target_role, status="Active")
    if not targets.exists():
        raise ValueError(f"'{target_role}' role ke koi active users nahi hain.")
    notifications = [
        Notification(sender=sender, receiver=u, message=message, type="in_app") for u in targets
    ]
    Notification.objects.bulk_create(notifications)
    return len(notifications)


# ============================================================
# NEW SERVICES (ADD AT THE END)
# ============================================================

def get_my_notifications_service(user_id, unread_only=False):
    from communication.models import Notification
    qs = Notification.objects.filter(receiver_id=user_id).order_by("-created_at")
    if unread_only:
        qs = qs.filter(is_read=False)
    return list(qs.values("id", "message", "type", "is_read", "created_at")[:20])


def mark_notification_read_service(user_id, notification_id):
    from communication.models import Notification
    notification = Notification.objects.get(id=notification_id, receiver_id=user_id)
    notification.is_read = True
    notification.save()
    return notification


def mark_all_notifications_read_service(user_id):
    from communication.models import Notification
    updated = Notification.objects.filter(receiver_id=user_id, is_read=False).update(is_read=True)
    return updated