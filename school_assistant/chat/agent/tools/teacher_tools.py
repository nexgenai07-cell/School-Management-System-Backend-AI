"""
Teacher's 3 READ + 4 WRITE tools.
"""
from langchain_core.tools import tool
from chat.agent.permissions import check
from chat.models import PendingAction

from accounts.services import get_teacher_profile_service, update_teacher_profile_service
from academics.services import (
    get_teacher_classes_service, get_teacher_timetable_service,
    get_class_list_service, create_assignment_service, update_assignment_service,
    delete_assignment_service,
)
from attendance.services import mark_attendance_service, lock_attendance_service, get_class_attendance_summary_service
from academics.services import upload_grades_service, update_grade_service, get_class_grades_service
from administration.services import file_complaint_service, get_my_complaints_service


def make_teacher_tools(user, session):
    if not check(user, "teacher", "read"):
        return {"read": [], "write": []}

    def _propose(action_name, params, summary):
        PendingAction.objects.update_or_create(
            session=session, defaults={"action_name": action_name, "params": params, "summary": summary}
        )
        return f"CONFIRM: {summary} (yes/no)"

    def _resolve_teacher_profile():
        return user.teacher_profile

    def _resolve_class_section(class_name: str):
        from academics.models import ClassSection
        parts = class_name.split("-")
        if len(parts) != 2:
            return None, f"Class name format should be '10-A', not '{class_name}'."
        return ClassSection.objects.filter(class_name=parts[0], section=parts[1]).first(), None

    def _check_teacher_owns_class(teacher, class_section):
        return teacher.subjects_taught.filter(class_section=class_section).exists()

    # ---------------- READ (3) ----------------

    @tool
    def get_my_profile() -> str:
        """Get your teacher profile."""
        teacher = _resolve_teacher_profile()
        r = get_teacher_profile_service(teacher.id)
        return f"{r['full_name']} | {r['qualification']} | Specialization: {r['specialization']}"

    @tool
    def get_my_classes() -> str:
        """Get all classes you are assigned to teach."""
        teacher = _resolve_teacher_profile()
        r = get_teacher_classes_service(teacher.id)
        if not r:
            return "Koi class assign nahi hai."
        return f"You teach {len(r)} classes: " + "; ".join(f"{c['class_name']}-{c['section']}" for c in r)

    @tool
    def get_my_timetable() -> str:
        """Get your own timetable (all your teaching slots)."""
        teacher = _resolve_teacher_profile()
        r = get_teacher_timetable_service(teacher.id)
        if not r:
            return "Koi timetable nahi mila."
        return "; ".join(f"{s['day']} {s['start_time']}-{s['end_time']}: {s['subject']} ({s['class_section']})" for s in r)

    # ---------------- WRITE (4) ----------------

    @tool
    def mark_attendance(class_name: str, date: str, present_roll_numbers: str) -> str:
        """Mark attendance for a class. class_name: '10-A', date: 'YYYY-MM-DD'.
        present_roll_numbers: comma-separated list of roll numbers (e.g., '10-A-001,10-A-002')."""
        teacher = _resolve_teacher_profile()
        class_section, error = _resolve_class_section(class_name)
        if error:
            return error
        if not class_section:
            return f"Class '{class_name}' nahi mili."
        if not _check_teacher_owns_class(teacher, class_section):
            return f"Aap class {class_name} ke teacher nahi hain."
        return _propose("mark_attendance",
                         {"class_section_id": class_section.id, "date": date, "present_roll_numbers": present_roll_numbers},
                         f"Attendance mark karna {class_name} for {date}")

    @tool
    def upload_grades(class_name: str, subject_name: str, exam_type: str, marks_data: str) -> str:
        """Upload grades for a class/subject. exam_type: Quiz/Mid-Term/Final/Assignment.
        marks_data: 'roll_number:marks' comma-separated, e.g., '10-A-001:85,10-A-002:92'."""
        teacher = _resolve_teacher_profile()
        from academics.models import Subject
        class_section, error = _resolve_class_section(class_name)
        if error:
            return error
        if not class_section:
            return f"Class '{class_name}' nahi mili."
        subject = Subject.objects.filter(subject_name__iexact=subject_name, class_section=class_section).first()
        if not subject:
            return f"Subject '{subject_name}' class {class_name} mein nahi mila."
        if subject.assigned_teacher_id != teacher.id:
            return f"Aap subject '{subject_name}' ke teacher nahi hain."
        return _propose("upload_grades",
                         {"class_section_id": class_section.id, "subject_id": subject.id,
                          "exam_type": exam_type, "marks_data": marks_data},
                         f"Grades upload karna {subject_name} for {class_name} ({exam_type})")

    @tool
    def create_assignment(class_name: str, subject_name: str, title: str, due_date: str, description: str = "") -> str:
        """Create a new assignment. class_name: '10-A', subject_name: 'Mathematics', due_date: 'YYYY-MM-DD'."""
        teacher = _resolve_teacher_profile()
        class_section, error = _resolve_class_section(class_name)
        if error:
            return error
        if not class_section:
            return f"Class '{class_name}' nahi mili."
        from academics.models import Subject
        subject = Subject.objects.filter(subject_name__iexact=subject_name, class_section=class_section).first()
        if not subject:
            return f"Subject '{subject_name}' class {class_name} mein nahi mila."
        if subject.assigned_teacher_id != teacher.id:
            return f"Aap subject '{subject_name}' ke teacher nahi hain."
        # FIXED: teacher_id was missing -- create_assignment_service requires it.
        return _propose("create_assignment",
                         {"class_section_id": class_section.id, "subject_id": subject.id,
                          "title": title, "description": description, "due_date": due_date,
                          "teacher_id": teacher.id},
                         f"Assignment '{title}' create karna for {class_name}")

    @tool
    def file_complaint(complaint_type: str, description: str, against_user_name: str = None) -> str:
        """File a complaint. complaint_type: infrastructure, behavioral, other."""
        return _propose("file_complaint",
                         {"reporter_id": user.id, "complaint_type": complaint_type,
                          "description": description, "against_user_name": against_user_name},
                         f"Complaint file karna: {complaint_type}")

    return {
        "read": [get_my_profile, get_my_classes, get_my_timetable],
        "write": [mark_attendance, upload_grades, create_assignment, file_complaint],
    }