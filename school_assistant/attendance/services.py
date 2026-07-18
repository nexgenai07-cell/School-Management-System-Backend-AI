'''
PERSON 1 -- services.py for 'attendance' app
Business logic + Casbin permission checks live here.
Existing models.py/views/serializers in this app are NOT touched.
'''
from attendance.models import Attendance
from academics.services import parse_class_section


def get_attendance_stats_service(class_section=None, date_from=None, date_to=None):
    qs = Attendance.objects.all()
    if class_section:
        qs = qs.filter(class_section=parse_class_section(class_section))
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    total = qs.count()
    present = qs.filter(status="Present").count()
    absent = qs.filter(status="Absent").count()
    leave = qs.filter(status="Leave").count()
    pct = round(present / total * 100, 1) if total else 0
    return {"total": total, "present": present, "absent": absent, "leave": leave, "attendance_pct": pct}


# ============================================================
# NEW SERVICES (ADD AT THE END)
# ============================================================

from datetime import datetime
from django.utils import timezone


def get_student_attendance_service(student_id, date_from=None, date_to=None):
    from attendance.models import Attendance
    qs = Attendance.objects.filter(student_id=student_id)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    total = qs.count()
    present = qs.filter(status="Present").count()
    absent = qs.filter(status="Absent").count()
    leave = qs.filter(status="Leave").count()
    return {"total": total, "present": present, "absent": absent, "leave": leave}


def get_student_attendance_summary_service(student_id):
    r = get_student_attendance_service(student_id)
    pct = round(r["present"] / r["total"] * 100, 1) if r["total"] else 0
    return {"percentage": pct, "present": r["present"], "total": r["total"]}


def get_child_attendance_service(child_id, date_from=None, date_to=None):
    return get_student_attendance_service(child_id, date_from, date_to)


def get_child_attendance_summary_service(child_id):
    return get_student_attendance_summary_service(child_id)


def mark_attendance_service(class_section_id, date, present_roll_numbers):
    from attendance.models import Attendance
    from accounts.models import StudentProfile
    students = StudentProfile.objects.filter(
        class_section_id=class_section_id,
        roll_number__in=present_roll_numbers
    )
    created = []
    for student in students:
        attendance, _ = Attendance.objects.update_or_create(
            student=student,
            date=date,
            defaults={"status": "Present", "class_section_id": class_section_id}
        )
        created.append(attendance)
    all_students = StudentProfile.objects.filter(class_section_id=class_section_id)
    present_ids = set(students.values_list("id", flat=True))
    for student in all_students:
        if student.id not in present_ids:
            Attendance.objects.update_or_create(
                student=student,
                date=date,
                defaults={"status": "Absent", "class_section_id": class_section_id}
            )
    return created


def lock_attendance_service(class_section_id, date):
    from attendance.models import Attendance
    updated = Attendance.objects.filter(class_section_id=class_section_id, date=date).update(is_locked=True)
    return updated


def get_class_attendance_summary_service(class_section_id, date_from=None, date_to=None):
    from attendance.models import Attendance
    from accounts.models import StudentProfile
    qs = Attendance.objects.filter(class_section_id=class_section_id)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    total_students = StudentProfile.objects.filter(class_section_id=class_section_id).count()
    present = qs.filter(status="Present").count()
    return {"total_students": total_students, "present": present}