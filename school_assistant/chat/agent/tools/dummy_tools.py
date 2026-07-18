from langchain_core.tools import tool


def make_dummy_tools(user, session):
    """Factory -- builds fresh tool objects per request, with user/session
    captured via closure (never exposed to the LLM as a parameter)."""

    @tool
    def get_dummy_pending_users() -> str:
        """Returns the list of users currently pending admin approval."""
        return "Dummy: 3 pending users hain: Ali (Teacher), Sara (Student), Zain (Parent)."

    @tool
    def get_dummy_my_class() -> str:
        """Returns the teacher's assigned class list."""
        return "Dummy: Class 8-A, 30 students."

    @tool
    def get_dummy_my_attendance() -> str:
        """Returns the logged-in student's own attendance percentage."""
        return "Dummy: 92% attendance."

    @tool
    def get_dummy_child_attendance() -> str:
        """Returns the parent's currently-selected child's attendance."""
        return "Dummy: 88% attendance."

    return {
        "admin": [get_dummy_pending_users],
        "teacher": [get_dummy_my_class],
        "student": [get_dummy_my_attendance],
        "parent": [get_dummy_child_attendance],
    }