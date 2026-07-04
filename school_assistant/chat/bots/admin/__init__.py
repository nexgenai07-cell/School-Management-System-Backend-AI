"""
Admin Bots — 10 specialized bots for the Admin Bot Hub.
Each bot handles a specific domain (Fee, Attendance, Assignment, etc.).
"""
# These imports will work once the bot files are created.
from .fee_bot import FeeBot
from .attendance_bot import AttendanceBot
from .assignment_bot import AssignmentBot
from .exam_bot import ExamBot
from .certificate_bot import CertificateBot
from .scholarship_bot import ScholarshipBot
from .inventory_bot import InventoryBot
from .event_bot import EventBot
from .maintenance_bot import MaintenanceBot
from .media_bot import MediaBot

__all__ = [
    "FeeBot",
    "AttendanceBot",
    "AssignmentBot",
    "ExamBot",
    "CertificateBot",
    "ScholarshipBot",
    "InventoryBot",
    "EventBot",
    "MaintenanceBot",
    "MediaBot",
]