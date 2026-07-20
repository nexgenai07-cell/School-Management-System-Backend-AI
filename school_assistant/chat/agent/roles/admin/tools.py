"""
Admin's complete tools (31 tools). Built fresh per-request via
make_admin_tools(user, session) so user/session stay out of the LLM's
reach (closure, not a param the LLM can set).

TOOL COUNT: 31 total
- READ: 13
- WRITE: 18

IMPORTANT PATTERN: any WRITE tool that acts on a specific record must be
able to resolve that record WITHOUT the LLM inventing an ID. Two ways
this is done here:
  1. The matching READ tool includes the real ID in its response text
     (get_pending_users, get_open_tickets, get_certificate_requests) --
     so the LLM has a real ID to quote back.
  2. The WRITE tool itself accepts a human-readable identifier (name)
     and resolves it to the DB row itself (assign_scholarship,
     update_inventory) -- so the LLM never needs an ID at all.

BUG FIX (moved here from chat/agent/tools/admin_tools.py): this file used
to define its own local _propose() that wrote action_name/summary to
PendingAction -- fields that don't exist on the model (see
migrations/0004_sync_pendingaction_schema.py). Every single WRITE tool
was crashing. Now uses the shared, centrally-fixed propose() builder.
"""
from langchain_core.tools import tool

from chat.agent.roles.shared.propose import make_propose

from accounts.services import (
    get_pending_users_service, approve_user_service, reject_user_service,
    get_scholarship_distribution_service, assign_scholarship_service,
    get_student_profile_service, update_student_profile_service,
    get_teacher_profile_service, update_teacher_profile_service,
    get_parent_profile_service, update_parent_profile_service,
    delete_student_profile_service, delete_teacher_profile_service,
    delete_parent_profile_service,
)
from finance.services import get_fee_summary_service
from attendance.services import get_attendance_stats_service
from academics.services import (
    get_exam_results_service, get_assignment_compliance_service,
    create_class_section_service, create_subject_service, create_timetable_entry_service,
    update_assignment_service, delete_assignment_service,
)
from administration.services import (
    get_inventory_status_service, get_events_service, get_open_tickets_service,
    get_certificate_requests_service, resolve_ticket_service, create_event_service,
    update_inventory_service, approve_certificate_request_service,
)
from communication.services import get_notification_history_service, send_notification_service


def make_admin_tools(user, session):
    _propose = make_propose(session)

    def _resolve_pending_user(user_name, role=None):
        """Shared lookup for approve_user/reject_user -- returns (target_dict, error_message)."""
        users = get_pending_users_service(role)
        matches = [u for u in users if user_name.lower() in u["full_name"].lower()]
        if not matches:
            return None, f"'{user_name}' naam ka koi pending user nahi mila."
        if len(matches) > 1:
            names = ", ".join(f"{m['full_name']} ({m['role__role_name']})" for m in matches)
            return None, f"Multiple pending users '{user_name}' se match karte hain: {names}. Poora naam ya role batayein."
        return matches[0], None

    def _resolve_student(student_name):
        """Resolve a student by name."""
        from accounts.models import StudentProfile
        matches = StudentProfile.objects.filter(
            user__full_name__icontains=student_name
        ).select_related("user")
        count = matches.count()
        if count == 0:
            return None, f"'{student_name}' naam ka koi student nahi mila."
        if count > 1:
            names = ", ".join(f"{m.user.full_name} (roll {m.roll_number})" for m in matches)
            return None, f"Multiple students mile '{student_name}' se match karte hain: {names}. Poora naam ya roll number batayein."
        return matches.first(), None

    # ---------------- READ (13) ----------------

    @tool
    def get_pending_users(role: str = None) -> str:
        """List users awaiting admin approval, optionally filtered by role (Teacher/Student/Parent)."""
        users = get_pending_users_service(role)
        if not users:
            return "Koi pending user nahi hai."
        lines = "; ".join(f"{u['full_name']} ({u['role__role_name']})" for u in users)
        return f"{len(users)} pending users hain: {lines}"

    @tool
    def get_fee_summary(month: str = None, class_section: str = None) -> str:
        """Get fee collection summary. month format 'YYYY-MM', class_section like '10-A'."""
        r = get_fee_summary_service(month, class_section)
        return (f"{r['month'] or 'Overall'}: Rs.{r['total_collected']} collected of Rs.{r['total_due']} due, "
                f"{r['pending_count']} pending challans.")

    @tool
    def get_attendance_stats(class_section: str = None, date_from: str = None, date_to: str = None) -> str:
        """Attendance stats (dates as YYYY-MM-DD), optionally filtered by class_section like '10-A'."""
        r = get_attendance_stats_service(class_section, date_from, date_to)
        return f"{r['attendance_pct']}% attendance ({r['present']} present, {r['absent']} absent, {r['leave']} leave out of {r['total']})."

    @tool
    def get_exam_results(class_section: str = None, exam_type: str = None, subject: str = None) -> str:
        """Exam results summary. exam_type: Quiz/Mid-Term/Final/Assignment."""
        r = get_exam_results_service(class_section, exam_type, subject)
        if not r["count"]:
            return "Koi results nahi mile."
        return f"{r['count']} results, average {r['average']}, top scorer: {r['top_scorer']} ({r['top_score']})."

    @tool
    def get_assignment_compliance(class_section: str = None) -> str:
        """Assignment submission compliance for a class_section like '10-A'."""
        r = get_assignment_compliance_service(class_section)
        if not r:
            return "Koi assignments nahi mile."
        lines = "; ".join(f"{a['title']}: {a['submitted']}/{a['total_students']} submitted" for a in r)
        return lines

    @tool
    def get_inventory_status(item: str = None, room: str = None) -> str:
        """Check inventory items, optionally filtered by item name or room."""
        r = get_inventory_status_service(item, room)
        if not r:
            return "Koi inventory item nahi mila."
        return "; ".join(f"{i['item_name']}: {i['total_quantity']} ({i['assigned_to_room'] or 'unassigned'})" for i in r)

    @tool
    def get_events(upcoming: bool = True) -> str:
        """List upcoming or past school events."""
        r = get_events_service(upcoming)
        if not r:
            return "Koi events nahi mile."
        return "; ".join(f"{e['event_name']} on {e['event_date']}" for e in r)

    @tool
    def get_open_tickets(keyword: str = None) -> str:
        """List open/in-progress complaints, optionally filtered by keyword."""
        r = get_open_tickets_service(keyword)
        if not r:
            return "Koi open complaint nahi hai."
        return "; ".join(f"{c['complaint_type']} by {c['reporter__full_name']} ({c['status']})" for c in r)

    @tool
    def get_scholarship_distribution(class_section: str = None) -> str:
        """Scholarship distribution (0%/50%/100%) across students."""
        r = get_scholarship_distribution_service(class_section)
        return f"0%: {r[0]} students, 50%: {r[50]} students, 100%: {r[100]} students."

    @tool
    def get_certificate_requests(status: str = None) -> str:
        """List certificate requests, optionally filtered by status (Pending/Approved)."""
        r = get_certificate_requests_service(status)
        if not r:
            return "Koi certificate requests nahi hain."
        return "; ".join(f"{c['cert_type']} for {c['student__user__full_name']} ({c['status']})" for c in r)

    @tool
    def get_notification_history(receiver_role: str = None) -> str:
        """Recent notification history, optionally filtered by receiver role."""
        r = get_notification_history_service(receiver_role)
        if not r:
            return "Koi notifications nahi mili."
        return f"{len(r)} recent notifications mili hain, sabse nayi: {r[0]['message'][:80]}"

    @tool
    def get_student_profile(student_name: str) -> str:
        """Get full profile of a student by name."""
        student, error = _resolve_student(student_name)
        if error:
            return error
        return (f"{student.user.full_name} | Roll: {student.roll_number} | Reg: {student.registration_number} | "
                f"Class: {student.class_section} | Guardian: {student.guardian_name} | "
                f"Phone: {student.guardian_phone} | Scholarship: {student.scholarship_percentage}%")

    @tool
    def get_teacher_profile(teacher_name: str) -> str:
        """Get full profile of a teacher by name."""
        from accounts.models import TeacherProfile
        teacher = TeacherProfile.objects.filter(user__full_name__icontains=teacher_name).select_related("user").first()
        if not teacher:
            return f"'{teacher_name}' naam ka koi teacher nahi mila."
        return (f"{teacher.user.full_name} | CNIC: {teacher.cnic} | "
                f"Qualification: {teacher.qualification} | Specialization: {teacher.specialization} | "
                f"Joining: {teacher.joining_date}")

    @tool
    def get_parent_profile(parent_name: str) -> str:
        """Get full profile of a parent by name."""
        from accounts.models import ParentProfile, ParentStudentLink
        parent = ParentProfile.objects.filter(user__full_name__icontains=parent_name).select_related("user").first()
        if not parent:
            return f"'{parent_name}' naam ka koi parent nahi mila."
        children_count = ParentStudentLink.objects.filter(parent=parent).count()
        return f"{parent.user.full_name} | Email: {parent.user.email} | {children_count} children linked."

    # ---------------- WRITE (18) ----------------

    @tool
    def approve_user(user_name: str, roll_number: str = None) -> str:
        """Propose approving a pending user, identified by name. Requires user confirmation."""
        target, error = _resolve_pending_user(user_name)
        if error:
            return error
        return _propose("approve_user", {"user_id": target["id"], "roll_number": roll_number},
                         f"{target['full_name']} ko approve karna")

    @tool
    def reject_user(user_name: str) -> str:
        """Propose rejecting a pending user, identified by name. Requires user confirmation."""
        target, error = _resolve_pending_user(user_name)
        if error:
            return error
        return _propose("reject_user", {"user_id": target["id"]}, f"{target['full_name']} ko reject karna")

    @tool
    def resolve_ticket(reporter_name: str, complaint_type: str = None, remarks: str = None) -> str:
        """Propose resolving a complaint by reporter's name. Requires confirmation."""
        tickets = get_open_tickets_service()
        matches = [t for t in tickets if reporter_name.lower() in t["reporter__full_name"].lower()]
        if complaint_type:
            matches = [t for t in matches if t["complaint_type"].lower() == complaint_type.lower()]
        if not matches:
            return f"'{reporter_name}' ki koi open complaint nahi mili."
        if len(matches) > 1:
            types = ", ".join(m["complaint_type"] for m in matches)
            return f"{reporter_name} ki {len(matches)} open complaints hain ({types}). Konsa type resolve karna hai?"
        ticket = matches[0]
        return _propose("resolve_ticket", {"ticket_id": ticket["id"], "remarks": remarks},
                         f"{ticket['reporter__full_name']} ki {ticket['complaint_type']} complaint resolve karna")

    @tool
    def assign_scholarship(student_name: str, percentage: int) -> str:
        """Propose assigning scholarship % (0/50/100) to a student by name. Requires confirmation."""
        student, error = _resolve_student(student_name)
        if error:
            return error
        return _propose("assign_scholarship", {"student_id": student.id, "percentage": percentage},
                         f"{student.user.full_name} ko {percentage}% scholarship dena")

    @tool
    def approve_certificate_request(student_name: str, cert_type: str = None) -> str:
        """Propose approving a certificate request by student name. Requires confirmation."""
        requests_ = get_certificate_requests_service(status="Pending")
        matches = [r for r in requests_ if student_name.lower() in r["student__user__full_name"].lower()]
        if cert_type:
            matches = [r for r in matches if r["cert_type"].lower() == cert_type.lower()]
        if not matches:
            return f"'{student_name}' ki koi pending certificate request nahi mili."
        if len(matches) > 1:
            types = ", ".join(m["cert_type"] for m in matches)
            return f"{student_name} ki {len(matches)} pending requests hain ({types}). Konsa cert_type approve karna hai?"
        req = matches[0]
        return _propose("approve_certificate_request", {"request_id": req["id"]},
                         f"{req['student__user__full_name']} ki {req['cert_type']} certificate request approve karna")

    @tool
    def send_notification(target_role: str, message: str) -> str:
        """Propose sending a notification to all users of a role. Requires confirmation."""
        return _propose("send_notification", {"target_role": target_role, "message": message},
                         f"'{target_role}' role ko notification bhejna: {message[:60]}")

    @tool
    def create_event(name: str, date: str, venue: str = "") -> str:
        """Propose creating a school event. date format 'YYYY-MM-DD HH:MM'. Requires confirmation."""
        return _propose("create_event", {"name": name, "date": date, "venue": venue},
                         f"Event '{name}' banana on {date}")

    @tool
    def update_inventory(item_name: str, new_quantity: int, room: str = None) -> str:
        """Propose updating inventory quantity for an item by name. If the same
        item exists in multiple rooms, also pass room to disambiguate. Requires confirmation."""
        return _propose("update_inventory", {"item_name": item_name, "new_quantity": new_quantity, "room": room},
                         f"{item_name} ki quantity {new_quantity} karna" + (f" ({room})" if room else ""))

    @tool
    def create_class_section(class_name: str, section: str, default_room: str = None) -> str:
        """Propose creating a new class-section. Requires confirmation."""
        return _propose("create_class_section",
                         {"class_name": class_name, "section": section, "default_room": default_room},
                         f"Class {class_name}-{section} banana")

    @tool
    def create_subject(subject_name: str, class_section: str, teacher_name: str = None) -> str:
        """Propose creating a subject for a class-section. Requires confirmation."""
        return _propose("create_subject",
                         {"subject_name": subject_name, "class_section": class_section, "teacher_name": teacher_name},
                         f"{subject_name} subject banana {class_section} ke liye")

    @tool
    def create_timetable_entry(class_section: str, subject_name: str, teacher_name: str, day: str,
                                start_time: str, end_time: str, room_name: str = None) -> str:
        """Propose a timetable slot. day: Mon/Tue/etc, times as 'HH:MM'. Requires confirmation."""
        return _propose("create_timetable_entry", {
            "class_section": class_section, "subject_name": subject_name, "teacher_name": teacher_name,
            "day": day, "start_time": start_time, "end_time": end_time, "room_name": room_name,
        }, f"{subject_name} slot banana {class_section} ke liye {day} {start_time}-{end_time}")

    @tool
    def update_student_profile(student_name: str, class_section: str = None, guardian_name: str = None,
                                guardian_phone: str = None, scholarship_percentage: int = None) -> str:
        """Propose updating a student's profile. Requires confirmation."""
        student, error = _resolve_student(student_name)
        if error:
            return error
        class_section_id = None
        if class_section:
            from academics.services import parse_class_section
            try:
                class_section_id = parse_class_section(class_section).id
            except Exception:
                return f"Class '{class_section}' nahi mili."
        return _propose("update_student_profile",
                         {"student_id": student.id, "class_section_id": class_section_id,
                          "guardian_name": guardian_name, "guardian_phone": guardian_phone,
                          "scholarship_percentage": scholarship_percentage},
                         f"{student.user.full_name} ka profile update karna")

    @tool
    def delete_student_profile(student_name: str) -> str:
        """Propose deleting a student profile (and user account). Requires confirmation."""
        student, error = _resolve_student(student_name)
        if error:
            return error
        return _propose("delete_student_profile", {"student_id": student.id},
                         f"{student.user.full_name} ka student profile delete karna")

    @tool
    def delete_teacher_profile(teacher_name: str) -> str:
        """Propose deleting a teacher profile (and user account). Requires confirmation."""
        from accounts.models import TeacherProfile
        teacher = TeacherProfile.objects.filter(user__full_name__icontains=teacher_name).select_related("user").first()
        if not teacher:
            return f"'{teacher_name}' naam ka koi teacher nahi mila."
        return _propose("delete_teacher_profile", {"teacher_id": teacher.id},
                         f"{teacher.user.full_name} ka teacher profile delete karna")

    @tool
    def delete_parent_profile(parent_name: str) -> str:
        """Propose deleting a parent profile (and user account). Requires confirmation."""
        from accounts.models import ParentProfile
        parent = ParentProfile.objects.filter(user__full_name__icontains=parent_name).select_related("user").first()
        if not parent:
            return f"'{parent_name}' naam ka koi parent nahi mila."
        return _propose("delete_parent_profile", {"parent_id": parent.id},
                         f"{parent.user.full_name} ka parent profile delete karna")

    @tool
    def draft_social_caption(event_name: str, tone: str = "exciting") -> str:
        """Draft a social-media caption for an event. Read-only generation, no confirmation needed."""
        return f"[DRAFT] {event_name} — join us for an unforgettable experience! #SchoolLife"

    return {
        "read": [
            get_pending_users, get_fee_summary, get_attendance_stats, get_exam_results,
            get_assignment_compliance, get_inventory_status, get_events, get_open_tickets,
            get_scholarship_distribution, get_certificate_requests, get_notification_history,
            get_student_profile, get_teacher_profile, get_parent_profile,
        ],
        "write": [
            approve_user, reject_user, resolve_ticket, assign_scholarship,
            approve_certificate_request, send_notification, create_event, update_inventory,
            create_class_section, create_subject, create_timetable_entry,
            update_student_profile, delete_student_profile, delete_teacher_profile, delete_parent_profile,
            draft_social_caption,
        ],
    }
