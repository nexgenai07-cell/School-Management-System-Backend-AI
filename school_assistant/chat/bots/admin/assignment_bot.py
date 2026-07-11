"""
Assignment Bot ("The Course Coordinator")
Scope: homework compliance and submission rates per section.
Example: "How many students in 10-A haven't submitted?"
"""
from django.utils import timezone

from chat.bots.base import BaseBot
from chat.bots.utils import extract_date_range, resolve_class_section


class AssignmentBot(BaseBot):
    def system_prompt(self) -> str:
        return (
            "You are 'The Course Coordinator', the School ERP's Assignment Bot. "
            "You track homework compliance: who submitted, who didn't, and "
            "submission rates per class section. Be organized and clear, like a "
            "coordinator briefing the principal on academic compliance."
        )

    def build_context(self) -> str:
        from academics.models import Assignment

        start, end = extract_date_range(self.message)
        section = resolve_class_section(self.message)

        assignments_qs = Assignment.objects.filter(due_date__date__gte=start, due_date__date__lte=end)
        if section:
            assignments_qs = assignments_qs.filter(class_section=section)

        assignments_qs = assignments_qs.select_related("subject", "class_section", "teacher__user").order_by(
            "-due_date"
        )[:20]

        lines = [f"Period covered (by due date): {start} to {end}"]
        if section:
            lines.append(f"Filtered to class section: {section}")

        if not assignments_qs:
            lines.append("No assignments found for this period/filter.")
            return "\n".join(lines)

        now = timezone.now()
        for a in assignments_qs:
            total_students = a.class_section.students.count()
            submitted_count = a.submissions.count()
            missing_count = total_students - submitted_count
            status = "past due" if a.due_date < now else "still open"
            lines.append(
                f"- '{a.title}' ({a.subject.subject_name}, {a.class_section}) due {a.due_date:%Y-%m-%d %H:%M} "
                f"[{status}]: {submitted_count}/{total_students} submitted, {missing_count} missing "
                f"(teacher: {a.teacher.user.full_name})"
            )

            if missing_count > 0 and missing_count <= 15:
                submitted_ids = set(a.submissions.values_list("student_id", flat=True))
                missing_students = a.class_section.students.exclude(id__in=submitted_ids).select_related("user")
                names = ", ".join(s.user.full_name for s in missing_students)
                lines.append(f"  Missing submissions: {names}")

        return "\n".join(lines)