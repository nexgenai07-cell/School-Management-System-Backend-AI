'''
PERSON 1 -- services.py for 'finance' app
Business logic + Casbin permission checks live here.
Existing models.py/views/serializers in this app are NOT touched.
'''
from datetime import datetime, timedelta
from django.db.models import Sum
from finance.models import Fee, FeeStructure, Payment
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


def get_student_fee_status_service(student_id):
    fees = Fee.objects.filter(student_id=student_id)
    total_due = fees.aggregate(t=Sum("amount"))["t"] or 0
    total_paid = fees.aggregate(t=Sum("amount_paid"))["t"] or 0
    status = "Paid" if total_due == total_paid and total_due > 0 else ("Partial" if total_paid > 0 else "Unpaid")
    return {"total": float(total_due), "paid": float(total_paid), "status": status}


def get_student_fee_history_service(student_id):
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
    """Alias for get_student_fee_status_service."""
    return get_student_fee_status_service(child_id)


def get_child_fee_history_service(child_id):
    """Alias for get_student_fee_history_service."""
    return get_student_fee_history_service(child_id)


# ============================================================
# NEW (59-tool plan)
# ============================================================

def create_fee_structure_service(class_section, monthly_fee):
    cs = parse_class_section(class_section)
    fs, created = FeeStructure.objects.get_or_create(
        class_section=cs, defaults={"monthly_fee": monthly_fee}
    )
    if not created:
        raise ValueError(f"{class_section} ke liye fee structure pehle se hai.")
    return fs


def update_fee_structure_service(class_section, monthly_fee):
    cs = parse_class_section(class_section)
    fs = FeeStructure.objects.get(class_section=cs)
    fs.monthly_fee = monthly_fee
    fs.save()
    return fs


def delete_fee_structure_service(class_section):
    cs = parse_class_section(class_section)
    fs = FeeStructure.objects.get(class_section=cs)
    fs.delete()  # raises ProtectedError if linked Fee challans exist -- by design
    return True


def generate_monthly_challans_service(month):
    """month: 'YYYY-MM'. Generates one Fee challan per student based on
    their class's FeeStructure and scholarship discount."""
    from accounts.models import StudentProfile
    month_date = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    due_date = month_date + timedelta(days=10)
    created_count = 0
    for student in StudentProfile.objects.select_related("class_section").all():
        try:
            fs = FeeStructure.objects.get(class_section=student.class_section)
        except FeeStructure.DoesNotExist:
            continue
        discount = student.scholarship_percentage or 0
        original = fs.monthly_fee
        payable = original * (100 - discount) / 100
        fee, was_created = Fee.objects.get_or_create(
            student=student, month=month_date,
            defaults={
                "fee_structure": fs, "original_amount": original,
                "amount": payable, "due_date": due_date, "status": "Unpaid",
            },
        )
        if was_created:
            created_count += 1
    return created_count


def get_challans_service(month=None, student_name=None, status=None):
    qs = Fee.objects.select_related("student__user")
    if month:
        month_date = datetime.strptime(month, "%Y-%m").date().replace(day=1)
        qs = qs.filter(month=month_date)
    if student_name:
        qs = qs.filter(student__user__full_name__icontains=student_name)
    if status:
        qs = qs.filter(status__iexact=status)
    return list(qs.values("id", "student__user__full_name", "month", "amount", "amount_paid", "status")[:30])


def update_challan_service(challan_id, amount=None, status=None):
    fee = Fee.objects.get(id=challan_id)
    if amount is not None:
        fee.amount = amount
    if status is not None:
        fee.status = status
    fee.save()
    return fee


def delete_challan_service(challan_id):
    fee = Fee.objects.get(id=challan_id)
    fee.delete()
    return True


def record_payment_service(challan_id, amount_paid, payment_method, payment_date):
    fee = Fee.objects.get(id=challan_id)
    payment = Payment.objects.create(
        fee=fee, amount_paid=amount_paid, payment_method=payment_method, payment_date=payment_date,
    )
    total_paid = fee.payments.aggregate(t=Sum("amount_paid"))["t"] or 0
    fee.amount_paid = total_paid
    fee.status = "Paid" if total_paid >= fee.amount else ("Partial" if total_paid > 0 else "Unpaid")
    if fee.status == "Paid":
        fee.paid_date = payment_date
    fee.save()
    return payment


def get_payments_service(student_name=None, date_from=None, date_to=None):
    qs = Payment.objects.select_related("fee__student__user")
    if student_name:
        qs = qs.filter(fee__student__user__full_name__icontains=student_name)
    if date_from:
        qs = qs.filter(payment_date__gte=date_from)
    if date_to:
        qs = qs.filter(payment_date__lte=date_to)
    return list(qs.values("fee__student__user__full_name", "amount_paid", "payment_method", "payment_date")[:30])