'''
PERSON 1 -- services.py for 'finance' app
Business logic + Casbin permission checks live here.
Existing models.py/views/serializers in this app are NOT touched.
'''
from datetime import datetime
from django.db.models import Sum
from finance.models import Fee
from academics.services import parse_class_section


def get_fee_summary_service(month=None, class_section=None):
    qs = Fee.objects.all()
    if month:
        month_date = datetime.strptime(month, "%Y-%m").date().replace(day=1)
        qs = qs.filter(month=month_date)
    if class_section:
        qs = qs.filter(student__class_section=parse_class_section(class_section))
    total_due = qs.aggregate(t=Sum("amount"))["t"] or 0
    total_collected = qs.aggregate(t=Sum("amount_paid"))["t"] or 0
    pending_count = qs.exclude(status="Paid").count()
    return {
        "month": month, "total_due": float(total_due),
        "total_collected": float(total_collected), "pending_count": pending_count,
    }


# ============================================================
# NEW SERVICES (ADD AT THE END)
# ============================================================

def get_student_fee_status_service(student_id):
    from finance.models import Fee
    fees = Fee.objects.filter(student_id=student_id)
    total_due = fees.aggregate(t=Sum("amount"))["t"] or 0
    total_paid = fees.aggregate(t=Sum("amount_paid"))["t"] or 0
    status = "Paid" if total_due == total_paid and total_due > 0 else ("Partial" if total_paid > 0 else "Unpaid")
    return {"total": float(total_due), "paid": float(total_paid), "status": status}


def get_student_fee_history_service(student_id):
    from finance.models import Fee
    fees = Fee.objects.filter(student_id=student_id).order_by("-month")
    return [
        {
            "month": f.month.strftime("%Y-%m"),
            "amount": float(f.amount),
            "amount_paid": float(f.amount_paid),
            "status": f.status,
        }
        for f in fees
    ]


def get_child_fee_status_service(child_id):
    return get_student_fee_status_service(child_id)


def get_child_fee_history_service(child_id):
    return get_student_fee_history_service(child_id)
def get_child_fee_status_service(child_id):
    """Alias for get_student_fee_status_service."""
    return get_student_fee_status_service(child_id)


def get_child_fee_history_service(child_id):
    """Alias for get_student_fee_history_service."""
    return get_student_fee_history_service(child_id)