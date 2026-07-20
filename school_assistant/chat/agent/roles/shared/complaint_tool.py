"""
Shared file_complaint tool -- Teacher, Student, and Parent all reuse this
exact same tool (this was the plan's original intent -- "write once,
import everywhere" -- but the previous code had it copy-pasted 3 times
with identical logic. Centralized here now.)
"""
from langchain_core.tools import tool


def build_file_complaint_tool(user, propose):
    """propose: the role's _propose() function (from shared/propose.py),
    already bound to that role's session."""

    @tool
    def file_complaint(complaint_type: str, description: str, against_user_name: str = None) -> str:
        """File a complaint. complaint_type: infrastructure, behavioral, other.
        against_user_name: optional name of the person you're complaining about."""
        return propose(
            "file_complaint",
            {"reporter_id": user.id, "complaint_type": complaint_type,
             "description": description, "against_user_name": against_user_name},
            f"Complaint file karna: {complaint_type}",
        )

    return file_complaint
