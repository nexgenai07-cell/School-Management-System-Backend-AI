"""
Student's 8 READ + 2 WRITE tools. Built fresh per-request via
make_student_tools(user, session) so user/session stay out of the LLM's
reach (closure, not a param the LLM can set).

SECURITY PATTERN: Student tools NEVER accept a student_id or user_id
parameter from the LLM. All reads use `student_profile` from the closure
(user.student_profile), not from the message text. This prevents prompt
injection where a student says "show me roll number 5's data".
"""
from langchain_core.tools import tool
from chat.agent.permissions import check
from chat.models import PendingAction

from accounts.services import get_student_profile_service, update_student_profile_service
from attendance.services import get_student_attendance_service, get_student_attendance_summary_service
from academics.services import (
    get_student_grades_service, get_student_report_card_service,
    get_student_timetable_service, get_student_assignments_service,
    get_assignment_details_service, submit_assignment_service,
    delete_submission_service,
)
from finance.services import get_student_fee_status_service, get_student_fee_history_service
from accounts.services import get_student_scholarship_status_service
from administration.services import (
    get_student_certificate_status_service,
    request_certificate_service,
    cancel_certificate_request_service,
)
from communication.services import get_my_notifications_service, mark_notification_read_service, mark_all_notifications_read_service
from administration.services import file_complaint_service, get_my_complaints_service


def make_student_tools(user, session):
    if not check(user, "student", "read"):
        return {"read": [], "write": []}

    def _propose(action_name, params, summary):
        PendingAction.objects.update_or_create(
            session=session, defaults={"action_name": action_name, "params": params, "summary": summary}
        )
        return f"CONFIRM: {summary} (yes/no)"

    def _resolve_student_profile():
        """Returns the current student's profile from the closure."""
        return user.student_profile

    # ---------------- READ (8) ----------------

    @tool
    def get_my_profile() -> str:
        """Get your own student profile details."""
        student = _resolve_student_profile()
        r = get_student_profile_service(student.id)
        return f"{r['full_name']} | Class: {r['class_section']} | Roll: {r['roll_number']} | Reg: {r['registration_number']}"

    @tool
    def get_my_attendance(date_from: str = None, date_to: str = None) -> str:
        """Get your attendance for a date range. Dates: YYYY-MM-DD."""
        student = _resolve_student_profile()
        r = get_student_attendance_service(student.id, date_from, date_to)
        return f"{r['present']} present, {r['absent']} absent, {r['leave']} leave out of {r['total']} days."

    @tool
    def get_my_attendance_summary() -> str:
        """Get a summary of your overall attendance percentage."""
        student = _resolve_student_profile()
        r = get_student_attendance_summary_service(student.id)
        return f"{r['percentage']}% attendance ({r['present']} present out of {r['total']} days)."

    @tool
    def get_my_grades(exam_type: str = None) -> str:
        """Get your grades, optionally filtered by exam_type (Quiz/Mid-Term/Final/Assignment)."""
        student = _resolve_student_profile()
        r = get_student_grades_service(student.id, exam_type)
        if not r:
            return "Koi grades nahi mile."
        return "; ".join(f"{g['subject']}: {g['obtained_marks']}/{g['total_marks']} ({g['exam_type']})" for g in r)

    @tool
    def get_my_report_card(term: str = None) -> str:
        """Get your report card. term can be 'Mid-Term' or 'Final'."""
        student = _resolve_student_profile()
        r = get_student_report_card_service(student.id, term)
        return f"Class: {r['class_section']} | GPA: {r['gpa']}\n" + "; ".join(
            f"{s['subject']}: {s['grade']}" for s in r["subjects"]
        )

    @tool
    def get_my_timetable() -> str:
        """Get your class timetable."""
        student = _resolve_student_profile()
        r = get_student_timetable_service(student.class_section_id)
        if not r:
            return "Koi timetable nahi mila."
        return "; ".join(f"{s['day']} {s['start_time']}-{s['end_time']}: {s['subject']} ({s['teacher']})" for s in r)

    @tool
    def get_my_assignments(status: str = None) -> str:
        """Get your assignments, optionally filtered by status (Pending/Submitted/Graded)."""
        student = _resolve_student_profile()
        r = get_student_assignments_service(student.id, status)
        if not r:
            return "Koi assignments nahi mile."
        return "; ".join(f"{a['title']} ({a['status']}, due {a['due_date']})" for a in r)

    @tool
    def get_my_fee_status() -> str:
        """Get your current fee status."""
        student = _resolve_student_profile()
        r = get_student_fee_status_service(student.id)
        return f"{r['status']} | Paid: Rs.{r['paid']} of Rs.{r['total']} due."

    @tool
    def get_my_notifications(unread_only: bool = False) -> str:
        """Get your notifications. Set unread_only=True for unread count."""
        r = get_my_notifications_service(user.id, unread_only)
        if not r:
            return "Koi notifications nahi hain."
        return "; ".join(f"{n['message'][:40]} ({'unread' if not n['is_read'] else 'read'})" for n in r)

    # ---------------- WRITE (2) ----------------

    @tool
    def request_certificate(cert_type: str) -> str:
        """Request a certificate. Types: bonafide, character, leaving, merit, fee_clearance.
        Requires confirmation. fee_clearance auto-checks if you have outstanding fees."""
        student = _resolve_student_profile()
        # service will auto-check fee_clearance eligibility
        return _propose("request_certificate", {"student_id": student.id, "cert_type": cert_type},
                         f"{cert_type} certificate request bhejna")

    @tool
    def file_complaint(complaint_type: str, description: str, against_user_name: str = None) -> str:
        """File a complaint. complaint_type: infrastructure, behavioral, other.
        against_user_name: optional name of the person you're complaining about."""
        student = _resolve_student_profile()
        return _propose("file_complaint",
                         {"reporter_id": user.id, "complaint_type": complaint_type,
                          "description": description, "against_user_name": against_user_name},
                         f"Complaint file karna: {complaint_type}")

    # ---------------- Certificate Delete (Extra) ----------------

    @tool
    def cancel_certificate_request(cert_type: str) -> str:
        """Cancel a pending certificate request identified by cert_type."""
        student = _resolve_student_profile()
        return _propose("cancel_certificate_request", {"student_id": student.id, "cert_type": cert_type},
                         f"{cert_type} certificate request cancel karna")

    return {
        "read": [get_my_profile, get_my_attendance, get_my_attendance_summary,
                 get_my_grades, get_my_report_card, get_my_timetable,
                 get_my_assignments, get_my_fee_status, get_my_notifications],
        "write": [request_certificate, file_complaint, cancel_certificate_request],
    }