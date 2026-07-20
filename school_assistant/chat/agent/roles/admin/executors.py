"""
Admin's WRITE-tool executors -- run only after the user replies "yes" to
a CONFIRM message. Moved out of consumers.py so Admin changes never
require touching the shared consumer file.
"""
from accounts.services import (
    approve_user_service, reject_user_service, assign_scholarship_service,
    update_student_profile_service, delete_student_profile_service,
    delete_teacher_profile_service, delete_parent_profile_service,
)
from administration.services import (
    resolve_ticket_service, create_event_service, update_inventory_service,
    approve_certificate_request_service,
)
from academics.services import (
    create_class_section_service, create_subject_service, create_timetable_entry_service,
)


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
    approve_certificate_request_service(request_id)
    return f"Certificate request #{request_id} approve ho gaya."

def _execute_send_notification(target_role, message):
    from communication.services import send_notification_service
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


TOOL_REGISTRY = {
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
}
