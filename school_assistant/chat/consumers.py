"""
WebSocket Consumer — Handles real-time chat messages.
"""
import json
import asyncio
import logging
from django.db import connection, close_old_connections
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser

from chat.models import ChatSession, ChatMessage, PendingAction
from chat.agent.agent_factory import build_agent, get_text
from chat.agent.tool_registry import get_tools_for_role

logger = logging.getLogger(__name__)

# ---- Admin services ----
from accounts.services import (
    approve_user_service, reject_user_service, assign_scholarship_service,
    update_student_profile_service, delete_student_profile_service,
    delete_teacher_profile_service, delete_parent_profile_service,
    update_teacher_profile_service, update_parent_profile_service,
)
from administration.services import (
    resolve_ticket_service, create_event_service, update_inventory_service,
    approve_certificate_request_service, file_complaint_service,
    request_certificate_service, cancel_certificate_request_service,
    create_inventory_service, delete_inventory_service,
    update_event_service, delete_event_service,
)
from academics.services import (
    create_class_section_service, create_subject_service, create_timetable_entry_service,
    upload_grades_service, create_assignment_service,
    update_class_section_service, delete_class_section_service,
    update_subject_service, delete_subject_service,
    create_room_service, update_room_service, delete_room_service,
    update_timetable_entry_service, delete_timetable_entry_service,
)
from finance.services import (
    create_fee_structure_service, update_fee_structure_service, delete_fee_structure_service,
    generate_monthly_challans_service, update_challan_service, delete_challan_service,
    record_payment_service,
)
from communication.services import send_notification_service
from attendance.services import mark_attendance_service


# ======================= Admin executors =======================

def _execute_approve_user(user_id, roll_number=None):
    u = approve_user_service(user_id, roll_number)
    return f"{u.full_name} approve ho gaya."

def _execute_reject_user(user_id):
    u = reject_user_service(user_id)
    return f"{u.full_name} reject kar diya gaya."

def _execute_resolve_ticket(ticket_id, remarks=None):
    resolve_ticket_service(ticket_id, remarks)
    return f"Ticket #{ticket_id} resolve ho gaya."

def _execute_assign_scholarship(student_id, percentage):
    p = assign_scholarship_service(student_id, percentage)
    return f"{p.user.full_name} ko {percentage}% scholarship mil gayi."

def _execute_approve_certificate_request(request_id):
    r = approve_certificate_request_service(request_id)
    return f"Certificate request #{request_id} approve ho gaya."

def _execute_send_notification(target_role, message):
    count = send_notification_service(sender=None, target_role=target_role, message=message)
    return f"{count} '{target_role}' users ko notification bhej di."

def _execute_create_event(name, date, venue=""):
    create_event_service(name, date, venue)
    return f"Event '{name}' ban gaya."

def _execute_update_inventory(item_name, new_quantity, room=None):
    update_inventory_service(item_name, new_quantity, room)
    return f"{item_name} ki quantity update ho gayi."

def _execute_create_class_section(class_name, section, default_room=None):
    create_class_section_service(class_name, section, default_room)
    return f"Class {class_name}-{section} ban gayi."

def _execute_create_subject(subject_name, class_section, teacher_name=None):
    create_subject_service(subject_name, class_section, teacher_name)
    return f"{subject_name} ban gaya."

def _execute_create_timetable_entry(**kwargs):
    create_timetable_entry_service(**kwargs)
    return "Timetable slot ban gaya."

def _execute_update_student_profile(student_id, class_section_id=None, guardian_name=None,
                                     guardian_phone=None, scholarship_percentage=None):
    update_student_profile_service(student_id, class_section_id, guardian_name,
                                    guardian_phone, scholarship_percentage)
    return "Student profile update ho gaya."

def _execute_delete_student_profile(student_id):
    delete_student_profile_service(student_id)
    return "Student profile delete ho gaya."

def _execute_delete_teacher_profile(teacher_id):
    delete_teacher_profile_service(teacher_id)
    return "Teacher profile delete ho gaya."

def _execute_delete_parent_profile(parent_id):
    delete_parent_profile_service(parent_id)
    return "Parent profile delete ho gaya."


# ---- Admin — NEW: class/subject/room/timetable updates-deletes ----

def _execute_update_class_section(class_section_str, new_class_name=None, new_section=None,
                                   default_room_name=None, teacher_incharge_name=None):
    update_class_section_service(class_section_str, new_class_name, new_section,
                                  default_room_name, teacher_incharge_name)
    return f"Class {class_section_str} update ho gayi."

def _execute_delete_class_section(class_section_str):
    delete_class_section_service(class_section_str)
    return f"Class {class_section_str} delete ho gayi."

def _execute_update_subject(subject_name, class_section, new_subject_name=None, teacher_name=None):
    update_subject_service(subject_name, class_section, new_subject_name, teacher_name)
    return f"{subject_name} update ho gaya."

def _execute_delete_subject(subject_name, class_section):
    delete_subject_service(subject_name, class_section)
    return f"{subject_name} delete ho gaya."

def _execute_create_room(name, location=None, capacity=None):
    create_room_service(name, location, capacity)
    return f"Room '{name}' ban gaya."

def _execute_update_room(room_name, new_name=None, location=None, capacity=None):
    update_room_service(room_name, new_name, location, capacity)
    return f"Room '{room_name}' update ho gaya."

def _execute_delete_room(room_name):
    delete_room_service(room_name)
    return f"Room '{room_name}' delete ho gaya."

def _execute_update_timetable_entry(class_section, subject_name, day, start_time,
                                     new_start_time=None, new_end_time=None,
                                     new_teacher_name=None, new_room_name=None):
    update_timetable_entry_service(class_section, subject_name, day, start_time,
                                    new_start_time, new_end_time, new_teacher_name, new_room_name)
    return "Timetable slot update ho gaya."

def _execute_delete_timetable_entry(class_section, subject_name, day, start_time):
    delete_timetable_entry_service(class_section, subject_name, day, start_time)
    return "Timetable slot delete ho gaya."


# ---- Admin — NEW: profiles ----

def _execute_update_teacher_profile(teacher_id, qualification=None, specialization=None):
    update_teacher_profile_service(teacher_id, qualification, specialization)
    return "Teacher profile update ho gaya."

def _execute_update_parent_profile(user_id):
    update_parent_profile_service(user_id)
    return "Parent profile update ho gaya."


# ---- Admin — NEW: finance ----

def _execute_create_fee_structure(class_section, monthly_fee):
    create_fee_structure_service(class_section, monthly_fee)
    return f"{class_section} ke liye fee structure ban gaya."

def _execute_update_fee_structure(class_section, monthly_fee):
    update_fee_structure_service(class_section, monthly_fee)
    return f"{class_section} ki fee update ho gayi."

def _execute_delete_fee_structure(class_section):
    delete_fee_structure_service(class_section)
    return f"{class_section} ka fee structure delete ho gaya."

def _execute_generate_monthly_challans(month):
    generate_monthly_challans_service(month)
    return f"{month} ke challans generate ho gaye."

def _execute_update_challan(challan_id, amount=None, status=None):
    update_challan_service(challan_id, amount, status)
    return f"Challan #{challan_id} update ho gaya."

def _execute_delete_challan(challan_id):
    delete_challan_service(challan_id)
    return f"Challan #{challan_id} delete ho gaya."

def _execute_record_payment(challan_id, amount_paid, payment_method, payment_date):
    record_payment_service(challan_id, amount_paid, payment_method, payment_date)
    return f"Challan #{challan_id} par payment record ho gayi."


# ---- Admin — NEW: inventory / events ----

def _execute_create_inventory(item_name, category, total_quantity, assigned_to_room=None):
    create_inventory_service(item_name, category, total_quantity, assigned_to_room)
    return f"{item_name} inventory mein add ho gaya."

def _execute_delete_inventory(item_name, room=None):
    delete_inventory_service(item_name, room)
    return f"{item_name} inventory se delete ho gaya."

def _execute_update_event(event_name, new_name=None, date=None, venue=None):
    update_event_service(event_name, new_name, date, venue)
    return f"Event '{event_name}' update ho gaya."

def _execute_delete_event(event_name):
    delete_event_service(event_name)
    return f"Event '{event_name}' delete ho gaya."


# ======================= Teacher executors =======================

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


# ======================= Shared executor (Teacher/Student/Parent) =======================

def _execute_file_complaint(reporter_id, complaint_type, description, against_user_name=None):
    file_complaint_service(reporter_id, complaint_type, description, against_user_name)
    return f"Complaint file ho gayi: {complaint_type}."


# ======================= Student executors =======================

def _execute_request_certificate(student_id, cert_type):
    request_certificate_service(student_id, cert_type)
    return f"{cert_type} certificate ki request bhej di gayi hai."

def _execute_cancel_certificate_request(student_id, cert_type):
    cancel_certificate_request_service(student_id, cert_type)
    return f"{cert_type} certificate request cancel kar di gayi."


TOOL_REGISTRY = {
    # Admin
    "approve_user": _execute_approve_user,
    "reject_user": _execute_reject_user,
    "resolve_ticket": _execute_resolve_ticket,
    "assign_scholarship": _execute_assign_scholarship,
    "approve_certificate_request": _execute_approve_certificate_request,
    "send_notification": _execute_send_notification,
    "create_event": _execute_create_event,
    "update_inventory": _execute_update_inventory,
    "create_class_section": _execute_create_class_section,
    "create_subject": _execute_create_subject,
    "create_timetable_entry": _execute_create_timetable_entry,
    "update_student_profile": _execute_update_student_profile,
    "delete_student_profile": _execute_delete_student_profile,
    "delete_teacher_profile": _execute_delete_teacher_profile,
    "delete_parent_profile": _execute_delete_parent_profile,
    # Admin — NEW (22)
    "update_class_section": _execute_update_class_section,
    "delete_class_section": _execute_delete_class_section,
    "update_subject": _execute_update_subject,
    "delete_subject": _execute_delete_subject,
    "create_room": _execute_create_room,
    "update_room": _execute_update_room,
    "delete_room": _execute_delete_room,
    "update_timetable_entry": _execute_update_timetable_entry,
    "delete_timetable_entry": _execute_delete_timetable_entry,
    "update_teacher_profile": _execute_update_teacher_profile,
    "update_parent_profile": _execute_update_parent_profile,
    "create_fee_structure": _execute_create_fee_structure,
    "update_fee_structure": _execute_update_fee_structure,
    "delete_fee_structure": _execute_delete_fee_structure,
    "generate_monthly_challans": _execute_generate_monthly_challans,
    "update_challan": _execute_update_challan,
    "delete_challan": _execute_delete_challan,
    "record_payment": _execute_record_payment,
    "create_inventory": _execute_create_inventory,
    "delete_inventory": _execute_delete_inventory,
    "update_event": _execute_update_event,
    "delete_event": _execute_delete_event,
    # Teacher
    "mark_attendance": _execute_mark_attendance,
    "upload_grades": _execute_upload_grades,
    "create_assignment": _execute_create_assignment,
    # Shared (Teacher/Student/Parent)
    "file_complaint": _execute_file_complaint,
    # Student
    "request_certificate": _execute_request_certificate,
    "cancel_certificate_request": _execute_cancel_certificate_request,
}

WELCOME_MESSAGES = {
    "admin": "Assalam-o-Alaikum! Main aapka Admin AI assistant hoon. Fees, attendance, complaints, events, ya kisi bhi school-data ke baare mein pooch sakte hain.",
    "teacher": "Assalam-o-Alaikum! Main aapka Teacher assistant hoon. Apni class, attendance, ya assignments ke baare mein pooch sakte hain.",
    "student": "Assalam-o-Alaikum! Main aapka assistant hoon. Apni attendance, grades, ya fee-status pooch sakte hain.",
    "parent": "Assalam-o-Alaikum! Main aapka assistant hoon. Apne bachay ka data dekhne ke liye bata dein kis bachay ki baat karni hai.",
}


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.room_group_name = f"chat_{self.session_id}"

        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser):
            await self.close(code=4001)
            return

        await database_sync_to_async(connection.ensure_connection)()
        owner_id = await self.get_session_owner_id(self.session_id)
        if owner_id is None or owner_id != user.id:
            await self.close(code=4003)
            return

        self.user = user
        self.session = await self.get_session(self.session_id)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        logger.info("WebSocket connected: User %s, Session %s", user.id, self.session_id)

        self.keep_alive_task = asyncio.create_task(self.send_keep_alive())

        await self.send_welcome_if_new()

    async def disconnect(self, close_code):
        if hasattr(self, "keep_alive_task"):
            self.keep_alive_task.cancel()
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def send_welcome_if_new(self):
        has_messages = await self.session_has_messages(self.session_id)
        if has_messages:
            return
        role = self.user.role.role_name.lower()
        text = WELCOME_MESSAGES.get(role, "Assalam-o-Alaikum! Kaise madad kar sakta hoon?")
        msg = await self.save_message(self.session, "assistant", text)
        await self.safe_send({
            "type": "message", "role": "assistant", "content": text,
            "message_id": msg.id, "created_at": str(msg.created_at),
        })

    async def send_keep_alive(self):
        while True:
            try:
                await asyncio.sleep(30)
                await self.safe_send({"type": "ping"})
            except asyncio.CancelledError:
                break
            except Exception:
                break

    async def safe_send(self, data):
        try:
            await self.send(json.dumps(data))
        except RuntimeError:
            logger.warning("Tried to send after connection was already closed (client disconnected).")

    async def receive(self, text_data):
        await database_sync_to_async(close_old_connections)()
        try:
            data = json.loads(text_data)
            if data.get("type") == "ping":
                return

            user_message = data.get("message", "").strip()
            if not user_message:
                return

            session = await self.get_session(self.session_id)
            await self.save_message(session, "user", user_message)
            await self.safe_send({"type": "typing", "status": True})

            pending = await self.get_pending_action(session)
            if pending:
                reply = await self.handle_pending_action(pending, user_message)
                ai_msg = await self.save_message(session, "assistant", reply)
                await self.safe_send({
                    "type": "message", "role": "assistant", "content": reply,
                    "message_id": ai_msg.id, "created_at": str(ai_msg.created_at),
                })
                return

            role = self.user.role.role_name.lower()
            history = await self.get_chat_history(session)
            tools = get_tools_for_role(role, self.user, session)

            ai_reply = await self.run_agent(self.user, tools, role, history, user_message)

            ai_msg = await self.save_message(session, "assistant", ai_reply)
            await self.safe_send({
                "type": "message", "role": "assistant", "content": ai_reply,
                "message_id": ai_msg.id, "created_at": str(ai_msg.created_at),
            })

        except json.JSONDecodeError:
            await self.safe_send({"type": "error", "error": "Invalid JSON format."})
        except Exception as e:
            logger.exception("Error in ChatConsumer.receive")
            await self.safe_send({"type": "error", "error": f"Something went wrong: {str(e)}"})

    @sync_to_async
    def run_agent(self, user, tools, role, history, user_message):
        agent = build_agent(user, tools, role)
        messages = history + [{"role": "user", "content": user_message}]
        result = agent.invoke({"messages": messages})
        reply = get_text(result["messages"][-1])
        print(f"\n🤖 [DEBUG] Agent reply: {reply}\n")
        return reply

    @database_sync_to_async
    def handle_pending_action(self, pending, user_message):
        """
        FIXED: the real DB schema for PendingAction is (tool_name, params,
        status) -- there is no action_name or summary column. The
        human-readable summary is instead stashed inside params["_summary"]
        by each tool's _propose() helper, and stripped back out here before
        calling the executor.
        """
        text = user_message.lower()
        if text in ("yes", "haan", "han"):
            tool_name = pending.tool_name
            executor = TOOL_REGISTRY.get(tool_name)
            params = {k: v for k, v in pending.params.items() if k != "_summary"}
            # IMPORTANT: delete BEFORE executing -- if the executor raises
            # (duplicate/ambiguous record, bad data, etc), the session must
            # not get permanently stuck re-asking to confirm the same
            # broken action on every subsequent message.
            pending.delete()
            if not executor:
                return f"'{tool_name}' action ka executor register nahi hai (TOOL_REGISTRY check karo)."
            try:
                return executor(**params)
            except Exception as e:
                logger.exception("Error executing pending action %s", tool_name)
                return f"Action complete nahi ho saka: {str(e)}"
        elif text in ("no", "nahi", "nhi"):
            pending.delete()
            return "Cancel kar diya."
        else:
            summary = pending.params.get("_summary", pending.tool_name)
            return f"Pehle confirm karein: '{summary}' -- (yes/no)"

    @database_sync_to_async
    def get_session_owner_id(self, session_id):
        return ChatSession.objects.filter(id=session_id).values_list("user_id", flat=True).first()

    @database_sync_to_async
    def get_session(self, session_id):
        return ChatSession.objects.select_related("user", "active_child").get(id=session_id)

    @database_sync_to_async
    def session_has_messages(self, session_id):
        return ChatMessage.objects.filter(session_id=session_id).exists()

    @database_sync_to_async
    def get_pending_action(self, session):
        return PendingAction.objects.filter(session=session).first()

    @database_sync_to_async
    def get_chat_history(self, session, limit=6):
        msgs = ChatMessage.objects.filter(session=session).order_by("-created_at")[:limit]
        return [{"role": m.role, "content": m.content} for m in reversed(list(msgs))]

    @database_sync_to_async
    def save_message(self, session, role, content):
        return ChatMessage.objects.create(session=session, role=role, content=content)