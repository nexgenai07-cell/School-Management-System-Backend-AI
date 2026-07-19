"""
Admin's complete tools (59 tools). Built fresh per-request via
make_admin_tools(user, session).

TOOL COUNT: 59 total -- READ: 22, WRITE: 37
Categories: Academics(17), Users(12), Finance(10), Administration(20)

PATTERN: WRITE tools resolve records by human-readable name (class
"10-A", subject name, room name, person's name) rather than raw IDs,
except financial challans/payments where a numeric id is the only
practical identifier (shown explicitly in get_challans/get_payments).

PendingAction schema note: _propose() stores the real DB fields
(tool_name, params, status) -- the human summary is smuggled inside
params["_summary"] since there's no separate summary column.
"""
from langchain_core.tools import tool
from chat.models import PendingAction

from accounts.services import (
    get_pending_users_service, approve_user_service, reject_user_service,
    get_scholarship_distribution_service, assign_scholarship_service,
    get_student_profile_service, update_student_profile_service,
    get_teacher_profile_service, update_teacher_profile_service,
    get_parent_profile_service, update_parent_profile_service,
    delete_student_profile_service, delete_teacher_profile_service,
    delete_parent_profile_service, list_users_service, get_user_details_service,
)
from finance.services import (
    get_fee_summary_service, get_challans_service,
)
from attendance.services import get_attendance_stats_service
from academics.services import (
    get_exam_results_service, get_assignment_compliance_service,
    parse_class_section, list_classes_service, get_class_details_service,
    list_subjects_service, list_rooms_service, list_timetable_service,
)
from administration.services import (
    get_inventory_status_service, get_events_service, get_open_tickets_service,
    get_certificate_requests_service,
)
from communication.services import get_notification_history_service


def make_admin_tools(user, session):
    def _propose(action_name, params, summary):
        PendingAction.objects.update_or_create(
            session=session, defaults={
                "tool_name": action_name,
                "params": {**params, "_summary": summary},
                "status": "pending",
            }
        )
        return f"CONFIRM: {summary} (yes/no)"

    def _resolve_pending_user(user_name, role=None):
        users = get_pending_users_service(role)
        matches = [u for u in users if user_name.lower() in u["full_name"].lower()]
        if not matches:
            return None, f"'{user_name}' naam ka koi pending user nahi mila."
        if len(matches) > 1:
            names = ", ".join(f"{m['full_name']} ({m['role__role_name']})" for m in matches)
            return None, f"Multiple pending users '{user_name}' se match karte hain: {names}."
        return matches[0], None

    def _resolve_student(student_name):
        from accounts.models import StudentProfile
        matches = StudentProfile.objects.filter(user__full_name__icontains=student_name).select_related("user")
        count = matches.count()
        if count == 0:
            return None, f"'{student_name}' naam ka koi student nahi mila."
        if count > 1:
            names = ", ".join(f"{m.user.full_name} (roll {m.roll_number})" for m in matches)
            return None, f"Multiple students mile '{student_name}' se: {names}."
        return matches.first(), None

    def _resolve_teacher(teacher_name):
        from accounts.models import TeacherProfile
        matches = TeacherProfile.objects.filter(user__full_name__icontains=teacher_name).select_related("user")
        count = matches.count()
        if count == 0:
            return None, f"'{teacher_name}' naam ka koi teacher nahi mila."
        if count > 1:
            names = ", ".join(m.user.full_name for m in matches)
            return None, f"Multiple teachers mile '{teacher_name}' se: {names}."
        return matches.first(), None

    def _resolve_parent(parent_name):
        from accounts.models import ParentProfile
        matches = ParentProfile.objects.filter(user__full_name__icontains=parent_name).select_related("user")
        count = matches.count()
        if count == 0:
            return None, f"'{parent_name}' naam ka koi parent nahi mila."
        if count > 1:
            names = ", ".join(m.user.full_name for m in matches)
            return None, f"Multiple parents mile '{parent_name}' se: {names}."
        return matches.first(), None

    # ================= ACADEMICS (17: 5 READ + 12 WRITE) =================

    @tool
    def list_classes() -> str:
        """List all classes with their default room and teacher-in-charge."""
        r = list_classes_service()
        if not r:
            return "Koi class nahi hai."
        return "; ".join(f"{c['class_name']}-{c['section']} (room: {c['default_room'] or 'none'}, in-charge: {c['teacher_incharge'] or 'none'})" for c in r)

    @tool
    def get_class_details(class_section: str) -> str:
        """Get details of a class like '10-A' -- room, in-charge, student/subject counts."""
        try:
            r = get_class_details_service(class_section)
        except Exception:
            return f"Class '{class_section}' nahi mili."
        return (f"{r['class_name']}-{r['section']} | Room: {r['default_room']} | "
                f"In-charge: {r['teacher_incharge']} | {r['student_count']} students, {r['subject_count']} subjects")

    @tool
    def create_class_section(class_name: str, section: str, default_room: str = None) -> str:
        """Propose creating a new class-section. Requires confirmation."""
        return _propose("create_class_section",
                         {"class_name": class_name, "section": section, "default_room": default_room},
                         f"Class {class_name}-{section} banana")

    @tool
    def update_class_section(class_section: str, new_class_name: str = None, new_section: str = None,
                              default_room_name: str = None, teacher_incharge_name: str = None) -> str:
        """Propose updating a class-section's name/section/room/in-charge. Requires confirmation."""
        return _propose("update_class_section", {
            "class_section_str": class_section, "new_class_name": new_class_name, "new_section": new_section,
            "default_room_name": default_room_name, "teacher_incharge_name": teacher_incharge_name,
        }, f"Class {class_section} update karna")

    @tool
    def delete_class_section(class_section: str) -> str:
        """Propose deleting a class-section. Requires confirmation."""
        return _propose("delete_class_section", {"class_section_str": class_section}, f"Class {class_section} delete karna")

    @tool
    def list_subjects(class_section: str = None) -> str:
        """List subjects, optionally filtered by class_section like '10-A'."""
        r = list_subjects_service(class_section)
        if not r:
            return "Koi subject nahi mila."
        return "; ".join(f"{s['subject_name']} ({s['class_section']}, teacher: {s['assigned_teacher'] or 'unassigned'})" for s in r)

    @tool
    def create_subject(subject_name: str, class_section: str, teacher_name: str = None) -> str:
        """Propose creating a subject for a class-section. Requires confirmation."""
        return _propose("create_subject",
                         {"subject_name": subject_name, "class_section": class_section, "teacher_name": teacher_name},
                         f"{subject_name} subject banana {class_section} ke liye")

    @tool
    def update_subject(subject_name: str, class_section: str, new_subject_name: str = None, new_teacher_name: str = None) -> str:
        """Propose updating a subject's name/teacher. Requires confirmation."""
        return _propose("update_subject", {
            "subject_name": subject_name, "class_section": class_section,
            "new_subject_name": new_subject_name, "teacher_name": new_teacher_name,
        }, f"{subject_name} ({class_section}) update karna")

    @tool
    def delete_subject(subject_name: str, class_section: str) -> str:
        """Propose deleting a subject from a class-section. Requires confirmation."""
        return _propose("delete_subject", {"subject_name": subject_name, "class_section": class_section},
                         f"{subject_name} ({class_section}) delete karna")

    @tool
    def list_rooms() -> str:
        """List all rooms with location and capacity."""
        r = list_rooms_service()
        if not r:
            return "Koi room nahi hai."
        return "; ".join(f"{rm['name']} ({rm['location'] or 'no location'}, capacity: {rm['capacity'] or 'n/a'})" for rm in r)

    @tool
    def create_room(name: str, location: str = None, capacity: int = None) -> str:
        """Propose creating a new room. Requires confirmation."""
        return _propose("create_room", {"name": name, "location": location, "capacity": capacity}, f"Room '{name}' banana")

    @tool
    def update_room(room_name: str, new_name: str = None, location: str = None, capacity: int = None) -> str:
        """Propose updating a room's details. Requires confirmation."""
        return _propose("update_room",
                         {"room_name": room_name, "new_name": new_name, "location": location, "capacity": capacity},
                         f"Room '{room_name}' update karna")

    @tool
    def delete_room(room_name: str) -> str:
        """Propose deleting a room. Requires confirmation."""
        return _propose("delete_room", {"room_name": room_name}, f"Room '{room_name}' delete karna")

    @tool
    def list_timetable(class_section: str = None, day: str = None) -> str:
        """List timetable slots, optionally filtered by class_section and/or day."""
        r = list_timetable_service(class_section, day)
        if not r:
            return "Koi timetable slot nahi mila."
        return "; ".join(f"{t['class_section']} {t['day']} {t['start_time']}-{t['end_time']}: {t['subject']} ({t['teacher']}, room: {t['room'] or 'n/a'})" for t in r)

    @tool
    def create_timetable_entry(class_section: str, subject_name: str, teacher_name: str, day: str,
                                start_time: str, end_time: str, room_name: str = None) -> str:
        """Propose a new timetable slot. day: Mon/Tue/etc, times 'HH:MM'. Requires confirmation."""
        return _propose("create_timetable_entry", {
            "class_section": class_section, "subject_name": subject_name, "teacher_name": teacher_name,
            "day": day, "start_time": start_time, "end_time": end_time, "room_name": room_name,
        }, f"{subject_name} slot banana {class_section} ke liye {day} {start_time}-{end_time}")

    @tool
    def update_timetable_entry(class_section: str, subject_name: str, day: str, start_time: str,
                                new_start_time: str = None, new_end_time: str = None,
                                new_teacher_name: str = None, new_room_name: str = None) -> str:
        """Propose updating an existing timetable slot (identified by class/subject/day/start_time). Requires confirmation."""
        return _propose("update_timetable_entry", {
            "class_section": class_section, "subject_name": subject_name, "day": day, "start_time": start_time,
            "new_start_time": new_start_time, "new_end_time": new_end_time,
            "new_teacher_name": new_teacher_name, "new_room_name": new_room_name,
        }, f"{subject_name} slot ({class_section}, {day} {start_time}) update karna")

    @tool
    def delete_timetable_entry(class_section: str, subject_name: str, day: str, start_time: str) -> str:
        """Propose deleting a timetable slot (identified by class/subject/day/start_time). Requires confirmation."""
        return _propose("delete_timetable_entry",
                         {"class_section": class_section, "subject_name": subject_name, "day": day, "start_time": start_time},
                         f"{subject_name} slot ({class_section}, {day} {start_time}) delete karna")

    # ================= USERS (12: 3 READ + 9 WRITE) =================

    @tool
    def list_users(role: str = None, status: str = None) -> str:
        """List users, optionally filtered by role (Admin/Teacher/Student/Parent) and/or status (Pending/Active/Rejected)."""
        r = list_users_service(role, status)
        if not r:
            return "Koi user nahi mila."
        return f"{len(r)} users: " + "; ".join(f"{u['full_name']} ({u['role__role_name']}, {u['status']})" for u in r)

    @tool
    def get_user_details(user_name: str) -> str:
        """Get details of any user by name."""
        u, error = get_user_details_service(user_name)
        if error:
            return error
        return f"{u.full_name} | Role: {u.role.role_name} | Status: {u.status} | Email: {u.email}"

    @tool
    def get_student_profile(student_name: str) -> str:
        """Get full profile of a student by name."""
        student, error = _resolve_student(student_name)
        if error:
            return error
        r = get_student_profile_service(student.id)
        return (f"{r['full_name']} | Roll: {r['roll_number']} | Reg: {r['registration_number']} | "
                f"Class: {r['class_section']} | Guardian: {r['guardian_name']} | "
                f"Phone: {r['guardian_phone']} | Scholarship: {r['scholarship_percentage']}%")

    @tool
    def approve_user(user_name: str, roll_number: str = None) -> str:
        """Propose approving a pending user by name. Requires confirmation."""
        target, error = _resolve_pending_user(user_name)
        if error:
            return error
        return _propose("approve_user", {"user_id": target["id"], "roll_number": roll_number},
                         f"{target['full_name']} ko approve karna")

    @tool
    def reject_user(user_name: str) -> str:
        """Propose rejecting a pending user by name. Requires confirmation."""
        target, error = _resolve_pending_user(user_name)
        if error:
            return error
        return _propose("reject_user", {"user_id": target["id"]}, f"{target['full_name']} ko reject karna")

    @tool
    def update_student_profile(student_name: str, class_section: str = None, guardian_name: str = None,
                                guardian_phone: str = None, scholarship_percentage: int = None) -> str:
        """Propose updating a student's profile. Requires confirmation."""
        student, error = _resolve_student(student_name)
        if error:
            return error
        return _propose("update_student_profile", {
            "student_id": student.id, "class_section": class_section, "guardian_name": guardian_name,
            "guardian_phone": guardian_phone, "scholarship_percentage": scholarship_percentage,
        }, f"{student.user.full_name} ka profile update karna")

    @tool
    def update_teacher_profile(teacher_name: str, qualification: str = None, specialization: str = None) -> str:
        """Propose updating a teacher's profile. Requires confirmation."""
        teacher, error = _resolve_teacher(teacher_name)
        if error:
            return error
        return _propose("update_teacher_profile",
                         {"teacher_id": teacher.id, "qualification": qualification, "specialization": specialization},
                         f"{teacher.user.full_name} ka profile update karna")

    @tool
    def update_parent_profile(parent_name: str) -> str:
        """Propose updating a parent's profile. Requires confirmation.
        NOTE: currently a no-op at the service level (no editable fields defined yet)."""
        parent, error = _resolve_parent(parent_name)
        if error:
            return error
        return _propose("update_parent_profile", {"user_id": parent.user_id},
                         f"{parent.user.full_name} ka parent profile update karna")

    @tool
    def delete_student_profile(student_name: str) -> str:
        """Propose deleting a student profile (and user account). Requires confirmation. IRREVERSIBLE."""
        student, error = _resolve_student(student_name)
        if error:
            return error
        return _propose("delete_student_profile", {"student_id": student.id},
                         f"{student.user.full_name} ka student profile delete karna")

    @tool
    def delete_teacher_profile(teacher_name: str) -> str:
        """Propose deleting a teacher profile (and user account). Requires confirmation. IRREVERSIBLE."""
        teacher, error = _resolve_teacher(teacher_name)
        if error:
            return error
        return _propose("delete_teacher_profile", {"teacher_id": teacher.id},
                         f"{teacher.user.full_name} ka teacher profile delete karna")

    @tool
    def delete_parent_profile(parent_name: str) -> str:
        """Propose deleting a parent profile (and user account). Requires confirmation. IRREVERSIBLE."""
        parent, error = _resolve_parent(parent_name)
        if error:
            return error
        return _propose("delete_parent_profile", {"parent_id": parent.id},
                         f"{parent.user.full_name} ka parent profile delete karna")

    @tool
    def assign_scholarship(student_name: str, percentage: int) -> str:
        """Propose assigning scholarship % (0/50/100) to a student by name. Requires confirmation."""
        student, error = _resolve_student(student_name)
        if error:
            return error
        return _propose("assign_scholarship", {"student_id": student.id, "percentage": percentage},
                         f"{student.user.full_name} ko {percentage}% scholarship dena")

    # ================= FINANCE (10: 3 READ + 7 WRITE) =================

    @tool
    def get_fee_summary(month: str = None, class_section: str = None) -> str:
        """Get fee collection summary. month format 'YYYY-MM', class_section like '10-A'.
        Both OPTIONAL -- call with no filters for overall summary, don't ask for clarification first."""
        r = get_fee_summary_service(month, class_section)
        return (f"{r['month'] or 'Overall'}: Rs.{r['total_collected']} collected of Rs.{r['total_due']} due, "
                f"{r['pending_count']} pending challans.")

    @tool
    def get_challans(month: str = None, student_name: str = None, status: str = None) -> str:
        """List fee challans, optionally filtered by month ('YYYY-MM'), student name, or status.
        Each challan's numeric id is shown -- quote it exactly for update_challan/delete_challan/record_payment."""
        r = get_challans_service(month, student_name, status)
        if not r:
            return "Koi challan nahi mila."
        return "; ".join(f"#{c['id']} {c['student__user__full_name']} {c['month']}: Rs.{c['amount']} (paid: Rs.{c['amount_paid']}, {c['status']})" for c in r)

    @tool
    def get_payments(student_name: str = None, date_from: str = None, date_to: str = None) -> str:
        """List payment transactions, optionally filtered by student name or date range (YYYY-MM-DD)."""
        from finance.services import get_payments_service
        r = get_payments_service(student_name, date_from, date_to)
        if not r:
            return "Koi payment nahi mila."
        return "; ".join(f"{p['fee__student__user__full_name']}: Rs.{p['amount_paid']} via {p['payment_method']} on {p['payment_date']}" for p in r)

    @tool
    def create_fee_structure(class_section: str, monthly_fee: float) -> str:
        """Propose creating a fee structure for a class. Requires confirmation."""
        return _propose("create_fee_structure", {"class_section": class_section, "monthly_fee": monthly_fee},
                         f"{class_section} ke liye Rs.{monthly_fee}/month fee structure banana")

    @tool
    def update_fee_structure(class_section: str, monthly_fee: float) -> str:
        """Propose updating a class's monthly fee. Requires confirmation."""
        return _propose("update_fee_structure", {"class_section": class_section, "monthly_fee": monthly_fee},
                         f"{class_section} ki fee Rs.{monthly_fee}/month karna")

    @tool
    def delete_fee_structure(class_section: str) -> str:
        """Propose deleting a class's fee structure. Requires confirmation. Fails if challans already exist for it."""
        return _propose("delete_fee_structure", {"class_section": class_section},
                         f"{class_section} ka fee structure delete karna")

    @tool
    def generate_monthly_challans(month: str) -> str:
        """Propose generating fee challans for all students for a given month ('YYYY-MM'). Requires confirmation."""
        return _propose("generate_monthly_challans", {"month": month}, f"{month} ke liye sab students ke challans generate karna")

    @tool
    def update_challan(challan_id: int, amount: float = None, status: str = None) -> str:
        """Propose updating a challan's amount/status. challan_id from get_challans. Requires confirmation."""
        return _propose("update_challan", {"challan_id": challan_id, "amount": amount, "status": status},
                         f"Challan #{challan_id} update karna")

    @tool
    def delete_challan(challan_id: int) -> str:
        """Propose deleting a challan. challan_id from get_challans. Requires confirmation."""
        return _propose("delete_challan", {"challan_id": challan_id}, f"Challan #{challan_id} delete karna")

    @tool
    def record_payment(challan_id: int, amount_paid: float, payment_method: str, payment_date: str) -> str:
        """Propose recording a payment against a challan. challan_id from get_challans.
        payment_method: Cash/Card/Bank Transfer/Online. payment_date: 'YYYY-MM-DD'. Requires confirmation."""
        return _propose("record_payment", {
            "challan_id": challan_id, "amount_paid": amount_paid,
            "payment_method": payment_method, "payment_date": payment_date,
        }, f"Challan #{challan_id} par Rs.{amount_paid} payment record karna")

    # ================= ADMINISTRATION (20: 11 READ + 9 WRITE) =================

    @tool
    def get_inventory_status(item: str = None, room: str = None) -> str:
        """Full inventory status. item/room OPTIONAL -- call with no filters to list everything."""
        r = get_inventory_status_service(item, room)
        if not r:
            return "Koi inventory item nahi mila."
        return "; ".join(f"{i['item_name']}: {i['total_quantity']} ({i['assigned_to_room'] or 'unassigned'})" for i in r)

    @tool
    def create_inventory(item_name: str, category: str, total_quantity: int, assigned_to_room: str = None) -> str:
        """Propose adding a new inventory item. Requires confirmation."""
        return _propose("create_inventory", {
            "item_name": item_name, "category": category,
            "total_quantity": total_quantity, "assigned_to_room": assigned_to_room,
        }, f"{item_name} ({total_quantity}) inventory mein add karna")

    @tool
    def update_inventory(item_name: str, new_quantity: int, room: str = None) -> str:
        """Propose updating inventory quantity by item name. If same item exists in
          multiple rooms, also pass room to disambiguate. Requires confirmation."""
        from administration.models import Inventory
        qs = Inventory.objects.filter(item_name__iexact=item_name)
        if room:
            qs = qs.filter(assigned_to_room__iexact=room)
        count = qs.count()
        if count == 0:
            return f"'{item_name}' inventory mein nahi mila."
        if count > 1:
            rooms = ", ".join(i.assigned_to_room or "unassigned" for i in qs)
            return f"'{item_name}' {count} rooms mein hai ({rooms}). Konsa room?"
        target_room = room or (qs.first().assigned_to_room or "unassigned")
        return _propose("update_inventory", {"item_name": item_name, "new_quantity": new_quantity, "room": room},
                         f"{item_name} ({target_room}) ki quantity {new_quantity} karna")

    @tool
    def delete_inventory(item_name: str, room: str = None) -> str:
        """Propose deleting an inventory item by name. If same item exists in
        multiple rooms, also pass room to disambiguate. Requires confirmation."""
        return _propose("delete_inventory", {"item_name": item_name, "room": room},
                         f"{item_name}" + (f" ({room})" if room else "") + " ko inventory se delete karna")

    @tool
    def get_events(upcoming: bool = True) -> str:
        """List upcoming or past school events."""
        r = get_events_service(upcoming)
        if not r:
            return "Koi events nahi mile."
        return "; ".join(f"{e['event_name']} on {e['event_date']}" for e in r)

    @tool
    def create_event(name: str, date: str, venue: str = "") -> str:
        """Propose creating a school event. date format 'YYYY-MM-DD HH:MM'. Requires confirmation."""
        return _propose("create_event", {"name": name, "date": date, "venue": venue},
                         f"Event '{name}' banana on {date}")

    @tool
    def update_event(event_name: str, new_name: str = None, date: str = None, venue: str = None) -> str:
        """Propose updating an event by its current name. Requires confirmation."""
        return _propose("update_event", {"event_name": event_name, "new_name": new_name, "date": date, "venue": venue},
                         f"Event '{event_name}' update karna")

    @tool
    def delete_event(event_name: str) -> str:
        """Propose deleting an event by name. Requires confirmation."""
        return _propose("delete_event", {"event_name": event_name}, f"Event '{event_name}' delete karna")

    @tool
    def get_open_tickets(keyword: str = None) -> str:
        """List open/in-progress complaints, optionally filtered by keyword."""
        r = get_open_tickets_service(keyword)
        if not r:
            return "Koi open complaint nahi hai."
        return "; ".join(f"{c['complaint_type']} by {c['reporter__full_name']} ({c['status']})" for c in r)

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
            return f"{reporter_name} ki {len(matches)} open complaints hain ({types}). Konsa type?"
        ticket = matches[0]
        return _propose("resolve_ticket", {"ticket_id": ticket["id"], "remarks": remarks},
                         f"{ticket['reporter__full_name']} ki {ticket['complaint_type']} complaint resolve karna")

    @tool
    def get_certificate_requests(status: str = None) -> str:
        """List certificate requests, optionally filtered by status (Pending/Approved)."""
        r = get_certificate_requests_service(status)
        if not r:
            return "Koi certificate requests nahi hain."
        return "; ".join(f"{c['cert_type']} for {c['student__user__full_name']} ({c['status']})" for c in r)

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
            return f"{student_name} ki {len(matches)} pending requests hain ({types}). Konsa cert_type?"
        req = matches[0]
        return _propose("approve_certificate_request", {"request_id": req["id"]},
                         f"{req['student__user__full_name']} ki {req['cert_type']} certificate request approve karna")

    @tool
    def send_notification(target_role: str, message: str) -> str:
        """Propose sending a notification to all users of a role. Requires confirmation."""
        return _propose("send_notification", {"target_role": target_role, "message": message},
                         f"'{target_role}' role ko notification bhejna: {message[:60]}")

    @tool
    def draft_social_caption(event_name: str, tone: str = "exciting") -> str:
        """Draft a social-media caption for an event. Read-only generation, no confirmation needed."""
        return f"[DRAFT] 🎉 {event_name} — join us for an unforgettable experience! #SchoolLife"

    @tool
    def get_notification_history(receiver_role: str = None) -> str:
        """Recent notification history, optionally filtered by receiver role."""
        r = get_notification_history_service(receiver_role)
        if not r:
            return "Koi notifications nahi mili."
        return f"{len(r)} recent notifications, sabse nayi: {r[0]['message'][:80]}"

    @tool
    def get_pending_users(role: str = None) -> str:
        """List users awaiting admin approval, optionally filtered by role (Teacher/Student/Parent)."""
        users = get_pending_users_service(role)
        if not users:
            return "Koi pending user nahi hai."
        lines = "; ".join(f"{u['full_name']} ({u['role__role_name']})" for u in users)
        return f"{len(users)} pending users hain: {lines}"

    @tool
    def get_scholarship_distribution(class_section: str = None) -> str:
        """Scholarship distribution (0%/50%/100%) across students."""
        r = get_scholarship_distribution_service(class_section)
        return f"0%: {r[0]} students, 50%: {r[50]} students, 100%: {r[100]} students."

    @tool
    def get_attendance_stats(class_section: str = None, date_from: str = None, date_to: str = None) -> str:
        """Overall school attendance stats. All filters OPTIONAL -- call with none for school-wide totals."""
        r = get_attendance_stats_service(class_section, date_from, date_to)
        return f"{r['attendance_pct']}% attendance ({r['present']} present, {r['absent']} absent, {r['leave']} leave out of {r['total']})."

    @tool
    def get_exam_results(class_section: str = None, exam_type: str = None, subject: str = None) -> str:
        """Overall exam results. All filters OPTIONAL -- call with none for school-wide results."""
        r = get_exam_results_service(class_section, exam_type, subject)
        if not r["count"]:
            return "Koi results nahi mile."
        return f"{r['count']} results, average {r['average']}, top scorer: {r['top_scorer']} ({r['top_score']})."

    @tool
    def get_assignment_compliance(class_section: str = None) -> str:
        """Overall assignment compliance. class_section OPTIONAL -- call with none for school-wide view."""
        r = get_assignment_compliance_service(class_section)
        if not r:
            return "Koi assignments nahi mile."
        return "; ".join(f"{a['title']}: {a['submitted']}/{a['total_students']} submitted" for a in r)

    return {
        "read": [
            list_classes, get_class_details, list_subjects, list_rooms, list_timetable,
            list_users, get_user_details, get_student_profile,
            get_fee_summary, get_challans, get_payments,
            get_inventory_status, get_events, get_open_tickets, get_certificate_requests,
            get_notification_history, get_pending_users, get_scholarship_distribution,
            get_attendance_stats, get_exam_results, get_assignment_compliance, draft_social_caption,
        ],
        "write": [
            create_class_section, update_class_section, delete_class_section,
            create_subject, update_subject, delete_subject,
            create_room, update_room, delete_room,
            create_timetable_entry, update_timetable_entry, delete_timetable_entry,
            approve_user, reject_user, update_student_profile, update_teacher_profile,
            update_parent_profile, delete_student_profile, delete_teacher_profile,
            delete_parent_profile, assign_scholarship,
            create_fee_structure, update_fee_structure, delete_fee_structure,
            generate_monthly_challans, update_challan, delete_challan, record_payment,
            create_inventory, update_inventory, delete_inventory,
            create_event, update_event, delete_event,
            resolve_ticket, approve_certificate_request, send_notification,
        ],
    }