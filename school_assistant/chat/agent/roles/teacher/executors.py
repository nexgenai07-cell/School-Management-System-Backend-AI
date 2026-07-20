"""
Teacher's WRITE-tool executors -- run only after the user replies "yes"
to a CONFIRM message.
"""
from academics.services import upload_grades_service, create_assignment_service
from attendance.services import mark_attendance_service
from chat.agent.roles.shared.executors import _execute_file_complaint


def _execute_mark_attendance(class_section_id, date, present_roll_numbers):
    """present_roll_numbers arrives as a comma-separated string from the
    tool -- parse into a list before calling the service."""
    roll_list = [r.strip() for r in present_roll_numbers.split(",") if r.strip()]
    mark_attendance_service(class_section_id, date, roll_list)
    return f"Attendance mark ho gayi {date} ke liye."

def _execute_upload_grades(class_section_id, subject_id, exam_type, marks_data):
    """marks_data arrives as 'roll:marks,roll:marks' -- parse into the list
    of dicts upload_grades_service expects."""
    entries = []
    for pair in marks_data.split(","):
        pair = pair.strip()
        if not pair:
            continue
        roll, marks = pair.split(":")
        entries.append({"roll_number": roll.strip(), "marks": float(marks.strip())})
    upload_grades_service(class_section_id, subject_id, exam_type, entries)
    return f"Grades upload ho gaye {exam_type} ke liye."

def _execute_create_assignment(class_section_id, subject_id, title, description, due_date, teacher_id):
    create_assignment_service(class_section_id, subject_id, title, description, due_date, teacher_id)
    return f"Assignment '{title}' ban gaya."


TOOL_REGISTRY = {
    "mark_attendance": _execute_mark_attendance,
    "upload_grades": _execute_upload_grades,
    "create_assignment": _execute_create_assignment,
    "file_complaint": _execute_file_complaint,  # shared
}
