'''
PERSON 1 -- services.py for 'administration' app
Business logic + Casbin permission checks live here.
Existing models.py/views/serializers in this app are NOT touched.
'''
from administration.models import Inventory, SchoolEvent, Complaint
from django.utils import timezone


def get_inventory_status_service(item=None, room=None):
    qs = Inventory.objects.all()
    if item:
        qs = qs.filter(item_name__icontains=item)
    if room:
        qs = qs.filter(assigned_to_room__icontains=room)
    return list(qs.values("item_name", "category", "total_quantity", "assigned_to_room"))


def get_events_service(upcoming=True):
    qs = SchoolEvent.objects.all()
    now = timezone.now()
    qs = qs.filter(event_date__gte=now) if upcoming else qs.filter(event_date__lt=now)
    return list(qs.order_by("event_date").values("event_name", "event_date", "venue")[:10])


def get_open_tickets_service(keyword=None):
    qs = Complaint.objects.exclude(status="Resolved").select_related("reporter")
    if keyword:
        qs = qs.filter(description__icontains=keyword)
    return list(qs.values("id", "complaint_type", "status", "reporter__full_name")[:20])


def get_certificate_requests_service(status=None):
    from chat.models import CertificateRequest
    qs = CertificateRequest.objects.select_related("student__user")
    if status:
        qs = qs.filter(status__iexact=status)
    return list(qs.values("id", "cert_type", "status", "student__user__full_name"))


def resolve_ticket_service(ticket_id, remarks=None):
    complaint = Complaint.objects.get(id=ticket_id)
    if complaint.status == "Resolved":
        raise ValueError("Ye complaint pehle se resolved hai.")
    complaint.status = "Resolved"
    complaint.resolved_at = timezone.now()
    if remarks:
        complaint.admin_remarks = remarks
        complaint.remarks_updated_at = timezone.now()
    complaint.save()
    return complaint


def create_event_service(name, date, venue=""):
    return SchoolEvent.objects.create(event_name=name, event_date=date, venue=venue)


def update_inventory_service(item_name, new_quantity, room=None):
    """FIXED: uses filter().count() instead of get() -- the same item_name
    can exist in multiple rooms (e.g. two 'Projector' rows), which was
    crashing with MultipleObjectsReturned. room disambiguates when needed."""
    qs = Inventory.objects.filter(item_name__iexact=item_name)
    if room:
        qs = qs.filter(assigned_to_room__iexact=room)
    count = qs.count()
    if count == 0:
        raise ValueError(f"'{item_name}' inventory mein nahi mila.")
    if count > 1:
        rooms = ", ".join(i.assigned_to_room or "unassigned" for i in qs)
        raise ValueError(f"'{item_name}' {count} rooms mein hai ({rooms}). Room specify karo.")
    item = qs.first()
    item.total_quantity = new_quantity
    item.save()
    return item


def approve_certificate_request_service(request_id):
    from chat.models import CertificateRequest
    req = CertificateRequest.objects.select_related("student__user").get(id=request_id)
    if req.status != "Pending":
        raise ValueError(f"Ye request already {req.status} hai.")
    req.status = "Approved"
    req.save()
    return req


# ============================================================
# NEW SERVICES
# ============================================================

def file_complaint_service(reporter_id, complaint_type, description, against_user_name=None):
    from administration.models import Complaint
    from accounts.models import User
    against_user = None
    if against_user_name:
        against_user = User.objects.filter(full_name__icontains=against_user_name).first()
    complaint = Complaint.objects.create(
        reporter_id=reporter_id,
        complaint_type=complaint_type,
        description=description,
        against_user=against_user,
        status="Open",
    )
    return complaint


def get_my_complaints_service(reporter_id, status=None):
    from administration.models import Complaint
    qs = Complaint.objects.filter(reporter_id=reporter_id).order_by("-created_at")
    if status:
        qs = qs.filter(status__iexact=status)
    return list(qs.values("id", "complaint_type", "description", "status", "created_at", "admin_remarks"))


def get_student_certificate_status_service(student_id):
    from chat.models import CertificateRequest
    requests = CertificateRequest.objects.filter(student_id=student_id).order_by("-requested_at")
    return [
        {
            "id": r.id,
            "cert_type": r.cert_type,
            "status": r.status,
            "requested_at": r.requested_at,
        }
        for r in requests
    ]


def request_certificate_service(student_id, cert_type):
    from chat.models import CertificateRequest
    from finance.models import Fee
    if cert_type == "fee_clearance":
        outstanding = Fee.objects.filter(student_id=student_id, status__in=["Unpaid", "Partial"]).exists()
        if outstanding:
            raise ValueError("Outstanding fees exist, cannot request fee_clearance certificate.")
    req = CertificateRequest.objects.create(
        student_id=student_id,
        cert_type=cert_type,
        status="Pending",
    )
    return req


def cancel_certificate_request_service(student_id, cert_type):
    from chat.models import CertificateRequest
    req = CertificateRequest.objects.get(student_id=student_id, cert_type=cert_type, status="Pending")
    req.delete()
    return True