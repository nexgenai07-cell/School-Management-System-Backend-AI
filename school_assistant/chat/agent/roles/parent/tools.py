"""
Parent's 8 READ + 1 WRITE tools. Built fresh per-request via
make_parent_tools(user, session) so user/session stay out of the LLM's
reach.

SECURITY PATTERN: Parent tools NEVER accept a student_id from the LLM.
They use `session.active_child` from the closure. The parent must first
use `set_active_child` to choose which child they're talking about.

BUG FIXES (moved here from chat/agent/tools/parent_tools.py):
1. _propose() used to write action_name/summary to PendingAction --
   fields that don't exist on the model. Now uses the shared,
   centrally-fixed propose() builder (see shared/propose.py).
2. The top-level permission gate called check(user, "parent", "read"),
   but conf/policy.csv has no such row -- the actual policy is
   "p, parent, child_data, read, allow" (resource = "child_data", not
   "parent"). This ALWAYS returned False -- make_parent_tools() was
   returning {"read": [], "write": []} on every single request. Fixed
   to check "child_data".
"""
from langchain_core.tools import tool
from chat.agent.permissions import check
from chat.agent.roles.shared.propose import make_propose
from chat.agent.roles.shared.complaint_tool import build_file_complaint_tool

from accounts.services import get_parent_profile_service
from accounts.services import get_my_children_service, set_active_child_service
from attendance.services import get_child_attendance_service
from academics.services import get_child_grades_service, get_child_report_card_service, get_child_timetable_service
from finance.services import get_child_fee_status_service
from academics.services import get_child_assignments_service


def make_parent_tools(user, session):
    # BUG FIX: was check(user, "parent", "read") -- see module docstring.
    if not check(user, "child_data", "read"):
        return {"read": [], "write": []}

    _propose = make_propose(session)

    def _get_active_child():
        """Returns the active child from session, or None."""
        return session.active_child

    def _resolve_child_by_name(child_name: str):
        """Resolve a child from the parent's linked children by name."""
        from accounts.models import ParentStudentLink
        link = ParentStudentLink.objects.filter(
            parent=user.parent_profile,
            student__user__full_name__icontains=child_name
        ).select_related("student__user").first()
        if not link:
            return None
        return link.student

    # ---------------- READ (8) ----------------

    @tool
    def get_my_profile() -> str:
        """Get your parent profile."""
        r = get_parent_profile_service(user.id)
        children_count = r.get("children_count", 0)
        return f"{r['full_name']} | {children_count} children registered"

    @tool
    def get_my_children() -> str:
        """Get the list of children linked to your parent account."""
        r = get_my_children_service(user.id)
        if not r:
            return "Koi bachcha linked nahi hai."
        return f"Your children: " + "; ".join(f"{c['full_name']} (Class: {c['class_section']})" for c in r)

    @tool
    def set_active_child(child_name: str) -> str:
        """Switch to a specific child. Use this first before asking about a child's data."""
        child = _resolve_child_by_name(child_name)
        if not child:
            return f"'{child_name}' naam ka bachcha aapke account mein linked nahi hai."
        set_active_child_service(session, child.id)
        return f"✅ Now viewing {child.user.full_name}'s data."

    @tool
    def get_child_attendance(date_from: str = None, date_to: str = None) -> str:
        """Get attendance of the currently selected child. Dates: YYYY-MM-DD."""
        child = _get_active_child()
        if not child:
            return "Pehle set_active_child karein."
        r = get_child_attendance_service(child.id, date_from, date_to)
        return f"{child.user.full_name}: {r['present']} present, {r['absent']} absent, {r['leave']} leave out of {r['total']} days."

    @tool
    def get_child_grades(exam_type: str = None) -> str:
        """Get grades of the currently selected child. exam_type: Quiz/Mid-Term/Final/Assignment."""
        child = _get_active_child()
        if not child:
            return "Pehle set_active_child karein."
        r = get_child_grades_service(child.id, exam_type)
        if not r:
            return f"{child.user.full_name} ki koi grades nahi mile."
        return f"{child.user.full_name}: " + "; ".join(f"{g['subject']}: {g['obtained_marks']}/{g['total_marks']}" for g in r)

    @tool
    def get_child_report_card(term: str = None) -> str:
        """Get the report card of the currently selected child. term: Mid-Term/Final."""
        child = _get_active_child()
        if not child:
            return "Pehle set_active_child karein."
        r = get_child_report_card_service(child.id, term)
        return f"{child.user.full_name} (Class: {r['class_section']}) | GPA: {r['gpa']}\n" + "; ".join(
            f"{s['subject']}: {s['grade']}" for s in r["subjects"]
        )

    @tool
    def get_child_timetable() -> str:
        """Get the timetable of the currently selected child."""
        child = _get_active_child()
        if not child:
            return "Pehle set_active_child karein."
        r = get_child_timetable_service(child.class_section_id)
        if not r:
            return f"{child.user.full_name} ka koi timetable nahi mila."
        return f"{child.user.full_name}: " + "; ".join(f"{s['day']} {s['start_time']}-{s['end_time']}: {s['subject']}" for s in r)

    @tool
    def get_child_fee_status() -> str:
        """Get fee status of the currently selected child."""
        child = _get_active_child()
        if not child:
            return "Pehle set_active_child karein."
        r = get_child_fee_status_service(child.id)
        return f"{child.user.full_name}: {r['status']} | Paid: Rs.{r['paid']} of Rs.{r['total']} due."

    @tool
    def get_child_assignments(status: str = None) -> str:
        """Get assignments of the currently selected child. status: Pending/Submitted/Graded."""
        child = _get_active_child()
        if not child:
            return "Pehle set_active_child karein."
        r = get_child_assignments_service(child.id, status)
        if not r:
            return f"{child.user.full_name} ki koi assignments nahi mile."
        return f"{child.user.full_name}: " + "; ".join(f"{a['title']} ({a['status']})" for a in r)

    # ---------------- WRITE (1) ----------------

    file_complaint = build_file_complaint_tool(user, _propose)

    return {
        "read": [get_my_profile, get_my_children, set_active_child, get_child_attendance,
                 get_child_grades, get_child_report_card, get_child_timetable,
                 get_child_fee_status, get_child_assignments],
        "write": [file_complaint],
    }
