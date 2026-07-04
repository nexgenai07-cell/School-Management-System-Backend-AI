"""
Bot Registry — Routes user requests to the appropriate Admin bot.
"""
import logging
from chat.bots.admin import (
    FeeBot,
    AttendanceBot,
    AssignmentBot,
    ExamBot,
    CertificateBot,
    ScholarshipBot,
    InventoryBot,
    EventBot,
    MaintenanceBot,
    MediaBot,
)

logger = logging.getLogger(__name__)

# Map bot_type (from ChatSession) to Bot Class
ADMIN_BOTS = {
    "fee": FeeBot,
    "attendance": AttendanceBot,
    "assignment": AssignmentBot,
    "exam": ExamBot,
    "certificate": CertificateBot,
    "scholarship": ScholarshipBot,
    "inventory": InventoryBot,
    "event": EventBot,
    "maintenance": MaintenanceBot,
    "media": MediaBot,
}


def get_bot_handler(user, session, message):
    """
    Route to the appropriate bot based on user role and session.bot_type.
    Returns the bot's AI response as a string.
    """
    role = user.role.role_name
    bot_type = session.bot_type

    # Admin with a valid bot_type
    if role == "Admin" and bot_type in ADMIN_BOTS:
        bot_class = ADMIN_BOTS[bot_type]
        bot = bot_class(user, session, message)
        return bot.get_response()

    # Admin without a bot_type selected
    if role == "Admin":
        return (
            "Please select a specialized bot from the Admin Bot Hub. "
            "Available bots: Fee, Attendance, Assignment, Exam, Certificate, "
            "Scholarship, Inventory, Event, Maintenance, Media."
        )

    # Non-Admin users (Teacher/Student/Parent)
    return (
        "I'm your general assistant. For specialized queries, "
        "please use the Admin Bot Hub if you have Admin access."
    )