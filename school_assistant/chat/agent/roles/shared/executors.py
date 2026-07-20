"""
Shared executor for the file_complaint WRITE tool -- Teacher, Student,
and Parent all register this same function against the "file_complaint"
key in their TOOL_REGISTRY.
"""
from administration.services import file_complaint_service


def _execute_file_complaint(reporter_id, complaint_type, description, against_user_name=None):
    file_complaint_service(reporter_id, complaint_type, description, against_user_name)
    return f"Complaint file ho gayi: {complaint_type}."
