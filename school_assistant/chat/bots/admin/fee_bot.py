"""
Fee Bot ("The Accountant")
Scope: monthly revenue, pending balances, unpaid lists, payment methods.
Example: "How much fee was collected this month?"
"""
from django.db.models import Sum, Count

from chat.bots.base import BaseBot
from chat.bots.utils import extract_date_range, resolve_class_section, resolve_student


class FeeBot(BaseBot):
    def system_prompt(self) -> str:
        return (
            "You are 'The Accountant', the School ERP's Fee Bot. You help the Admin "
            "understand fee collection, pending balances, and payment activity. "
            "Speak like a precise, no-nonsense school accountant. When listing unpaid "
            "students, format as a clean bullet list with amount due. Always mention "
            "the date range your figures cover."
        )

    def build_context(self) -> str:
        from finance.models import Fee, Payment

        start, end = extract_date_range(self.message)
        section = resolve_class_section(self.message)
        student = resolve_student(self.message)

        lines = [f"Period covered: {start} to {end}"]

        fees_qs = Fee.objects.filter(month__gte=start, month__lte=end)
        if section:
            fees_qs = fees_qs.filter(student__class_section=section)
            lines.append(f"Filtered to class section: {section}")
        if student:
            fees_qs = fees_qs.filter(student=student)
            lines.append(f"Filtered to student: {student.user.full_name} (Roll: {student.roll_number})")

        totals = fees_qs.aggregate(
            total_payable=Sum("amount"),
            total_collected=Sum("amount_paid"),
        )
        payable = totals["total_payable"] or 0
        collected = totals["total_collected"] or 0
        lines.append(f"Total fee payable in period: PKR {payable}")
        lines.append(f"Total fee collected in period: PKR {collected}")
        lines.append(f"Outstanding balance in period: PKR {payable - collected}")

        status_counts = fees_qs.values("status").annotate(count=Count("id"))
        breakdown = ", ".join(f"{s['status']}={s['count']}" for s in status_counts)
        lines.append("Status breakdown: " + (breakdown or "no fee records in this period"))

        unpaid = fees_qs.filter(status__in=["Unpaid", "Partial"]).select_related("student__user")[:25]
        if unpaid:
            lines.append("Unpaid / partially-paid students (up to 25):")
            for fee in unpaid:
                due_left = fee.amount - fee.amount_paid
                lines.append(
                    f"- {fee.student.user.full_name} (Roll: {fee.student.roll_number}, "
                    f"month: {fee.month}): due PKR {due_left}, status={fee.status}"
                )
        else:
            lines.append("No unpaid/partial fees found for this period/filter.")

        payments_qs = Payment.objects.filter(payment_date__gte=start, payment_date__lte=end)
        method_counts = payments_qs.values("payment_method").annotate(
            total=Sum("amount_paid"), count=Count("id")
        )
        if method_counts:
            lines.append("Payment method breakdown for the period:")
            for m in method_counts:
                lines.append(f"- {m['payment_method']}: {m['count']} payments, PKR {m['total']} total")

        return "\n".join(lines)