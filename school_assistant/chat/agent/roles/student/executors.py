"""
Student's WRITE-tool executors -- run only after the user replies "yes"
to a CONFIRM message.
"""
from accounts.services import update_student_profile_service
from administration.services import request_certificate_service, cancel_certificate_request_service
from academics.services import submit_assignment_service, delete_submission_service
from communication.services import mark_notification_read_service, mark_all_notifications_read_service
from chat.agent.roles.shared.executors import _execute_file_complaint


def _execute_request_certificate(student_id, cert_type):
    request_certificate_service(student_id, cert_type)
    return f"{cert_type} certificate ki request bhej di gayi hai."

def _execute_cancel_certificate_request(student_id, cert_type):
    cancel_certificate_request_service(student_id, cert_type)
    return f"{cert_type} certificate request cancel kar di gayi."

def _execute_update_my_profile_student(student_id, guardian_name=None, guardian_phone=None, date_of_birth=None):
    """Deliberately separate from admin's update_student_profile: only
    self-editable fields are accepted here (no class_section_id/scholarship)."""
    update_student_profile_service(student_id, guardian_name=guardian_name,
                                    guardian_phone=guardian_phone, date_of_birth=date_of_birth)
    return "Aapki profile update ho gayi."

def _execute_submit_assignment(assignment_id, student_id, file_url):
    submit_assignment_service(assignment_id, student_id, file_url)
    return "Assignment submit ho gaya."

def _execute_delete_submission(assignment_id, student_id):
    delete_submission_service(assignment_id, student_id)
    return "Submission delete ho gayi."

def _execute_mark_notification_read(user_id, notification_id):
    mark_notification_read_service(user_id, notification_id)
    return "Notification read mark ho gayi."

def _execute_mark_all_notifications_read(user_id):
    mark_all_notifications_read_service(user_id)
    return "Saari notifications read mark ho gayin."


TOOL_REGISTRY = {
    "request_certificate": _execute_request_certificate,
    "cancel_certificate_request": _execute_cancel_certificate_request,
    "update_my_profile_student": _execute_update_my_profile_student,
    "submit_assignment": _execute_submit_assignment,
    "delete_submission": _execute_delete_submission,
    "mark_notification_read": _execute_mark_notification_read,
    "mark_all_notifications_read": _execute_mark_all_notifications_read,
    "file_complaint": _execute_file_complaint,  # shared
}
