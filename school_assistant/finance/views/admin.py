"""
FINANCE -- ADMIN-ROLE VIEWS
==============================
"""

from decimal import Decimal

from django.db.models import Sum
from rest_framework import viewsets, generics
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import StudentProfile
from accounts.permissions import IsAdmin
from finance.models import FeeStructure, Fee, Payment, Expense, FeeHistory
from finance.serializers.admin import (
    FeeStructureSerializer, FeeSerializer, PaymentSerializer, ExpenseSerializer, FeeHistorySerializer,
)


class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.select_related("class_section").all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAdmin]


class FeeViewSet(viewsets.ModelViewSet):
    """
    CRUD /api/finance/challans
    Fee.amount_paid/status are read-only here -- they only change through
    PaymentCreateView below, which keeps Payment (the real ledger) and
    Fee (the cached summary) in sync, and writes a FeeHistory row.
    """
    queryset = Fee.objects.select_related("student__user", "fee_structure").all()
    serializer_class = FeeSerializer
    permission_classes = [IsAdmin]

    def perform_create(self, serializer):
        fee = serializer.save()
        FeeHistory.objects.create(
            fee=fee, new_status=fee.status, new_amount=fee.amount,
            changed_by_admin=self.request.user, reason="Challan manually created by Admin.",
        )

    def perform_update(self, serializer):
        old_fee = self.get_object()
        old_status, old_amount = old_fee.status, old_fee.amount
        fee = serializer.save()
        if old_status != fee.status or old_amount != fee.amount:
            FeeHistory.objects.create(
                fee=fee, old_status=old_status, new_status=fee.status,
                old_amount=old_amount, new_amount=fee.amount,
                changed_by_admin=self.request.user, reason="Challan manually corrected by Admin.",
            )


class GenerateMonthlyChallansView(APIView):
    """
    POST /api/finance/generate-monthly-challans
    Manual trigger for the same logic the Celery cron job runs
    automatically at the start of each month (see project tech stack:
    "fee challans are automatically generated... cron job at backend").
    Fetches each student's class fee, applies their scholarship discount,
    and creates a Fee row -- skips students who already have one for
    that month (Fee has a unique_together on student+month).
    """
    permission_classes = [IsAdmin]

    def post(self, request):
        month = request.data.get("month")  # expected format: "YYYY-MM-01"
        if not month:
            return Response({"month": "Required, e.g. 2026-07-01"}, status=400)

        created_count, skipped_count = 0, 0

        for student in StudentProfile.objects.select_related("class_section").all():
            fee_structure = FeeStructure.objects.filter(class_section=student.class_section).first()
            if not fee_structure:
                continue  # no fee structure defined for this class yet

            if Fee.objects.filter(student=student, month=month).exists():
                skipped_count += 1
                continue

            discount = Decimal(student.scholarship_percentage) / Decimal(100)
            original_amount = fee_structure.monthly_fee
            amount = original_amount * (Decimal(1) - discount)

            Fee.objects.create(
                student=student, fee_structure=fee_structure, month=month,
                original_amount=original_amount, amount=amount,
                due_date=month, status="Unpaid",
            )
            created_count += 1

        return Response({"created": created_count, "skipped_existing": skipped_count})


class PaymentCreateView(generics.CreateAPIView):
    """
    POST /api/finance/payments
    Records one payment transaction and keeps Fee.amount_paid / status
    and FeeHistory in sync -- see Payment's docstring in models.py.
    """
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAdmin]

    def perform_create(self, serializer):
        payment = serializer.save()
        fee = payment.fee

        old_status = fee.status
        total_paid = fee.payments.aggregate(total=Sum("amount_paid"))["total"] or Decimal(0)
        fee.amount_paid = total_paid
        fee.status = "Paid" if total_paid >= fee.amount else ("Partial" if total_paid > 0 else "Unpaid")
        if fee.status == "Paid":
            fee.paid_date = payment.payment_date
        fee.save()

        if old_status != fee.status:
            FeeHistory.objects.create(
                fee=fee, old_status=old_status, new_status=fee.status,
                old_amount=fee.amount, new_amount=fee.amount,
                changed_by_admin=self.request.user,
                reason=f"Payment of {payment.amount_paid} recorded.",
            )


class PaymentListView(generics.ListAPIView):
    """GET /api/finance/payments/{fee_id}"""
    serializer_class = PaymentSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return Payment.objects.filter(fee_id=self.kwargs["fee_id"]).order_by("-payment_date")


class ExpenseViewSet(viewsets.ModelViewSet):
    """CRUD /api/admin/expenses"""
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    permission_classes = [IsAdmin]

    def perform_create(self, serializer):
        serializer.save(paid_by_admin=self.request.user)


class FeeHistoryListView(generics.ListAPIView):
    """GET /api/finance/fee-history/{fee_id}"""
    serializer_class = FeeHistorySerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return FeeHistory.objects.filter(fee_id=self.kwargs["fee_id"]).order_by("-created_at")