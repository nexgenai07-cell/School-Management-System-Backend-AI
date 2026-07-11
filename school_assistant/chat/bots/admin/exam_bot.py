"""
Exam Bot ("The Academic Evaluator")
Scope: result analysis, top scorers, fail rates by class.
Example: "Who's the Math topper in Term 2 finals?"
"""
from django.db.models import F, ExpressionWrapper, FloatField

from chat.bots.base import BaseBot
from chat.bots.utils import extract_exam_type, resolve_class_section, resolve_subject

PASS_PERCENTAGE = 40  # school pass threshold, used for fail-rate reporting


class ExamBot(BaseBot):
    def system_prompt(self) -> str:
        return (
            "You are 'The Academic Evaluator', the School ERP's Exam Bot. You analyze "
            "results: top scorers, fail rates, and subject/class performance. Speak "
            "like an academic coordinator presenting results, precise with numbers "
            "and names. State which exam type and subject/section you used."
        )

    def build_context(self) -> str:
        from academics.models import Grade

        exam_type = extract_exam_type(self.message)
        subject = resolve_subject(self.message)
        section = resolve_class_section(self.message)

        grades_qs = Grade.objects.select_related("student__user", "student__class_section", "subject")
        if exam_type:
            grades_qs = grades_qs.filter(exam_type=exam_type)
        if subject:
            grades_qs = grades_qs.filter(subject=subject)
        if section:
            grades_qs = grades_qs.filter(student__class_section=section)

        grades_qs = grades_qs.annotate(
            percentage=ExpressionWrapper(F("obtained_marks") * 100.0 / F("total_marks"), output_field=FloatField())
        )

        lines = []
        lines.append(f"Exam type filter: {exam_type or 'all types'}")
        lines.append(f"Subject filter: {subject.subject_name if subject else 'all subjects'}")
        lines.append(f"Class section filter: {section or 'all sections'}")

        total_count = grades_qs.count()
        lines.append(f"Total matching grade records: {total_count}")
        if total_count == 0:
            lines.append("No grade records found for this filter.")
            return "\n".join(lines)

        top_scorers = grades_qs.order_by("-percentage")[:10]
        lines.append("Top scorers (up to 10):")
        for g in top_scorers:
            lines.append(
                f"- {g.student.user.full_name} (Class: {g.student.class_section}, {g.subject.subject_name}, "
                f"{g.exam_type}): {g.obtained_marks}/{g.total_marks} ({g.percentage:.1f}%)"
            )

        failing = grades_qs.filter(percentage__lt=PASS_PERCENTAGE)
        fail_count = failing.count()
        fail_rate = round((fail_count / total_count) * 100, 1) if total_count else 0
        lines.append(f"Fail rate (below {PASS_PERCENTAGE}%): {fail_count}/{total_count} = {fail_rate}%")

        if 0 < fail_count <= 20:
            lines.append("Failing students:")
            for g in failing.order_by("percentage")[:20]:
                lines.append(
                    f"- {g.student.user.full_name} (Class: {g.student.class_section}, {g.subject.subject_name}): "
                    f"{g.obtained_marks}/{g.total_marks} ({g.percentage:.1f}%)"
                )

        return "\n".join(lines)