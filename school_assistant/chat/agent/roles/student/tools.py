"""
Student's 14 READ + 8 WRITE tools (22 total, matching the full tool-list
spec). Built fresh per-request via make_student_tools(user, session) so
user/session stay out of the LLM's reach (closure, not a param the LLM
can set).

SECURITY PATTERN: Student tools NEVER accept a student_id or user_id
parameter from the LLM. All reads use `student_profile` from the closure
(user.student_profile), not from the message text. This prevents prompt
injection where a student says "show me roll number 5's data".
"""
from langchain_core.tools import tool
from chat.agent.permissions import check
from chat.agent.roles.shared.propose import make_propose
from chat.agent.roles.shared.complaint_tool import build_file_complaint_tool

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
    # BUG FIX: policy.csv has "p, student, own_data, read, allow" -- the
    # resource is "own_data", NOT "student". check(user, "student", "read")
    # was calling enforcer.enforce("student", "student", "read"), which never
    # matches any policy row (Casbin's matcher needs an exact object match
    # unless the policy object is "*", which only Admin has). This silently
    # returned {"read": [], "write": []} for EVERY student request -- the
    # agent had zero tools bound, hence the "I don't have that option" replies.
    if not check(user, "own_data", "read"):
        return {"read": [], "write": []}

    _propose = make_propose(session)

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

    # NEW: 5 tools below use services that were already imported at the top
    # of this file but were never wrapped -- the backend work was done,
    # just the @tool layer was missing.

    @tool
    def get_my_fee_history() -> str:
        """Get your month-by-month fee history. For every month, shows the
        total amount due, how much has been paid, the outstanding balance,
        and a clear paid/unpaid verdict -- so the assistant can't compress
        this into an ambiguous single number."""
        student = _resolve_student_profile()
        r = get_student_fee_history_service(student.id)
        if not r:
            return "Koi fee history nahi mili."
        lines = []
        for h in r:
            outstanding = round(h["amount"] - h["amount_paid"], 2)
            verdict = "Is mahine ki fee poori paid hai." if outstanding <= 0 else \
                      (f"Is mahine ki fee mein Rs.{outstanding} outstanding hai." if h["amount_paid"] > 0
                       else "Is mahine ki fee abhi paid nahi hui.")
            lines.append(
                f"{h['month']} -- Total due: Rs.{h['amount']}, Paid: Rs.{h['amount_paid']}, "
                f"Outstanding: Rs.{outstanding} ({h['status']}). {verdict}"
            )
        return "\n".join(lines)

    @tool
    def get_assignment_details(assignment_id: int) -> str:
        """Get full details of one of your assignments, including whether you've submitted it."""
        student = _resolve_student_profile()
        r = get_assignment_details_service(assignment_id, student.id)
        submitted = "haan" if r.get("submitted") else "nahi"
        return (f"{r['title']} ({r['subject']}) | Due: {r['due_date']} | "
                f"Submitted: {submitted}\n{r['description']}")

    @tool
    def get_my_scholarship_status() -> str:
        """Get your current scholarship percentage and status."""
        student = _resolve_student_profile()
        r = get_student_scholarship_status_service(student.id)
        return f"Scholarship: {r['scholarship_percentage']}%" + (" (active)" if r["is_on_scholarship"] else "")

    @tool
    def get_my_certificate_status() -> str:
        """Get the status of all your certificate requests."""
        student = _resolve_student_profile()
        r = get_student_certificate_status_service(student.id)
        if not r:
            return "Aapne koi certificate request nahi ki."
        return "; ".join(f"{c['cert_type']}: {c['status']}" for c in r)

    @tool
    def get_my_complaints(status: str = None) -> str:
        """Get the complaints you've filed, optionally filtered by status (Open/Resolved)."""
        r = get_my_complaints_service(user.id, status)
        if not r:
            return "Aapne koi complaint file nahi ki."
        return "; ".join(f"{c['complaint_type']}: {c['status']}" for c in r)

    # ---------------- WRITE (2) ----------------

    @tool
    def request_certificate(cert_type: str) -> str:
        """Request a certificate. Types: bonafide, character, leaving, merit, fee_clearance.
        Requires confirmation. fee_clearance auto-checks if you have outstanding fees."""
        student = _resolve_student_profile()
        # service will auto-check fee_clearance eligibility
        return _propose("request_certificate", {"student_id": student.id, "cert_type": cert_type},
                         f"{cert_type} certificate request bhejna")

    file_complaint = build_file_complaint_tool(user, _propose)

    # ---------------- Certificate Delete (Extra) ----------------

    @tool
    def cancel_certificate_request(cert_type: str) -> str:
        """Cancel a pending certificate request identified by cert_type."""
        student = _resolve_student_profile()
        return _propose("cancel_certificate_request", {"student_id": student.id, "cert_type": cert_type},
                         f"{cert_type} certificate request cancel karna")

    # ---------------- NEW WRITE tools (5) ----------------
    # SECURITY NOTE on update_my_profile: update_student_profile_service also
    # accepts class_section_id and scholarship_percentage, but a student must
    # NEVER be able to change their own class or scholarship -- so this tool's
    # signature deliberately only exposes the 3 safe self-editable fields.
    # The tool_name passed to _propose is "update_my_profile_student" (not
    # "update_student_profile") so it never collides with the Admin tool of
    # a similar name in TOOL_REGISTRY.

    @tool
    def update_my_profile(guardian_name: str = None, guardian_phone: str = None, date_of_birth: str = None) -> str:
        """Update your own profile. Only guardian_name, guardian_phone, and date_of_birth
        (YYYY-MM-DD) can be changed -- class and scholarship are Admin-only fields."""
        student = _resolve_student_profile()
        return _propose(
            "update_my_profile_student",
            {"student_id": student.id, "guardian_name": guardian_name,
             "guardian_phone": guardian_phone, "date_of_birth": date_of_birth},
            "Profile update karna",
        )

    @tool
    def submit_assignment(assignment_id: int, file_url: str) -> str:
        """Submit (or resubmit) your work for an assignment, given the uploaded file's URL."""
        student = _resolve_student_profile()
        return _propose(
            "submit_assignment",
            {"assignment_id": assignment_id, "student_id": student.id, "file_url": file_url},
            f"Assignment #{assignment_id} submit karna",
        )

    @tool
    def delete_submission(assignment_id: int) -> str:
        """Delete your submission for an assignment. Only works if it hasn't been graded yet."""
        student = _resolve_student_profile()
        return _propose(
            "delete_submission",
            {"assignment_id": assignment_id, "student_id": student.id},
            f"Assignment #{assignment_id} ki submission delete karna",
        )

    @tool
    def mark_notification_read(notification_id: int) -> str:
        """Mark a single notification as read."""
        return _propose(
            "mark_notification_read",
            {"user_id": user.id, "notification_id": notification_id},
            f"Notification #{notification_id} ko read mark karna",
        )

    @tool
    def mark_all_notifications_read() -> str:
        """Mark all of your notifications as read."""
        return _propose(
            "mark_all_notifications_read",
            {"user_id": user.id},
            "Saari notifications ko read mark karna",
        )

    return {
        "read": [get_my_profile, get_my_attendance, get_my_attendance_summary,
                 get_my_grades, get_my_report_card, get_my_timetable,
                 get_my_assignments, get_assignment_details, get_my_fee_status,
                 get_my_fee_history, get_my_scholarship_status, get_my_certificate_status,
                 get_my_notifications, get_my_complaints],
        "write": [request_certificate, file_complaint, cancel_certificate_request,
                  update_my_profile, submit_assignment, delete_submission,
                  mark_notification_read, mark_all_notifications_read],
    }