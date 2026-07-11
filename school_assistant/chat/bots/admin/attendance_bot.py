"""
Attendance & Compliance Bot ("The Registrar")
Scope: flags students below an attendance threshold.
Example: "Who's below 75% attendance in the last 30 days?"
"""
from django.db.models import Count, Q

from chat.bots.base import BaseBot
from chat.bots.utils import extract_date_range, extract_percentage, resolve_class_section, resolve_student


class AttendanceBot(BaseBot):
    def system_prompt(self) -> str:
        return (
            "You are 'The Registrar', the School ERP's Attendance & Compliance Bot. "
            "You flag students falling below attendance thresholds and summarize "
            "attendance/behavior trends. Be direct and factual, like a school "
            "registrar reporting to the principal. Always state the date range and "
            "threshold you used."
        )

    def build_context(self) -> str:
        from accounts.models import StudentProfile

        start, end = extract_date_range(self.message, default_days=30)
        threshold = extract_percentage(self.message, default=75)
        section = resolve_class_section(self.message)
        student = resolve_student(self.message)

        lines = [f"Period covered: {start} to {end}", f"Attendance threshold used: {threshold}%"]

        students_qs = StudentProfile.objects.select_related("user", "class_section")
        if section:
            students_qs = students_qs.filter(class_section=section)
            lines.append(f"Filtered to class section: {section}")
        if student:
            students_qs = students_qs.filter(id=student.id)
            lines.append(f"Filtered to student: {student.user.full_name} (Roll: {student.roll_number})")

        students_qs = students_qs.annotate(
            total_days=Count("attendance_records", filter=Q(attendance_records__date__range=(start, end))),
            present_days=Count(
                "attendance_records",
                filter=Q(attendance_records__date__range=(start, end), attendance_records__status="Present"),
            ),
        ).filter(total_days__gt=0)

        below_threshold = []
        all_rows = []
        for s in students_qs[:300]:
            pct = round((s.present_days / s.total_days) * 100, 1) if s.total_days else 0
            all_rows.append((s, pct))
            if pct < threshold:
                below_threshold.append((s, pct))

        lines.append(f"Total students with attendance records in this period: {len(all_rows)}")
        lines.append(f"Students below {threshold}% attendance: {len(below_threshold)}")

        if below_threshold:
            lines.append("Below-threshold list (up to 30):")
            for s, pct in sorted(below_threshold, key=lambda x: x[1])[:30]:
                lines.append(
                    f"- {s.user.full_name} (Roll: {s.roll_number}, Class: {s.class_section}): {pct}% attendance"
                )
        else:
            lines.append("No students found below the threshold for this filter/period.")

        from attendance.models import BehaviorLog

        behavior_qs = BehaviorLog.objects.filter(date__range=(start, end), severity__in=["High", "Medium"])
        if section:
            behavior_qs = behavior_qs.filter(student__class_section=section)
        if student:
            behavior_qs = behavior_qs.filter(student=student)
        behavior_qs = behavior_qs.select_related("student__user").order_by("-date")[:15]

        if behavior_qs:
            lines.append("Recent behavior log entries (Medium/High severity):")
            for b in behavior_qs:
                lines.append(f"- {b.date} | {b.student.user.full_name}: [{b.severity}] {b.description}")

        return "\n".join(lines)