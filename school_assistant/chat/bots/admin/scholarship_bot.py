"""
Scholarship Bot ("The Financial Aid Officer")
Scope: tracks concessions and audits fee reductions.
Example: "How many students are on merit scholarship?"
"""
from django.db.models import Count

from chat.bots.base import BaseBot
from chat.bots.utils import extract_date_range, resolve_class_section


class ScholarshipBot(BaseBot):
    def system_prompt(self) -> str:
        return (
            "You are 'The Financial Aid Officer', the School ERP's Scholarship Bot. "
            "You track scholarship/concession distribution and audit fee-reduction "
            "history. Be precise and audit-minded, like someone accountable for "
            "where discounts were applied and why."
        )

    def build_context(self) -> str:
        from accounts.models import StudentProfile
        from finance.models import FeeHistory

        section = resolve_class_section(self.message)

        students_qs = StudentProfile.objects.select_related("user", "class_section")
        if section:
            students_qs = students_qs.filter(class_section=section)

        breakdown = students_qs.values("scholarship_percentage").annotate(count=Count("id")).order_by(
            "-scholarship_percentage"
        )

        lines = [f"Class section filter: {section or 'all sections'}"]
        lines.append("Scholarship distribution:")
        for row in breakdown:
            label = f"{row['scholarship_percentage']}%"
            lines.append(f"- {label} scholarship: {row['count']} students")

        on_scholarship = students_qs.filter(scholarship_percentage__gt=0)
        count_on_scholarship = on_scholarship.count()
        lines.append(f"Total students on any scholarship (>0%): {count_on_scholarship}")

        if 0 < count_on_scholarship <= 30:
            lines.append("Students on scholarship:")
            for s in on_scholarship.order_by("-scholarship_percentage")[:30]:
                lines.append(
                    f"- {s.user.full_name} (Roll: {s.roll_number}, Class: {s.class_section}): "
                    f"{s.scholarship_percentage}% scholarship"
                )

        start, end = extract_date_range(self.message)
        history_qs = (
            FeeHistory.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
            .exclude(old_amount=None)
            .select_related("fee__student__user", "changed_by_admin")
            .order_by("-created_at")[:15]
        )
        if history_qs:
            lines.append(f"Recent fee-amount changes ({start} to {end}):")
            for h in history_qs:
                lines.append(
                    f"- {h.fee.student.user.full_name}: PKR {h.old_amount} -> PKR {h.new_amount} "
                    f"(reason: {h.reason or 'not stated'})"
                )

        return "\n".join(lines)