from chat.agent.roles.admin.tools import make_admin_tools
from chat.agent.roles.teacher.tools import make_teacher_tools
from chat.agent.roles.student.tools import make_student_tools
from chat.agent.roles.parent.tools import make_parent_tools


def get_tools_for_role(role, user, session):
    role = role.lower()

    if role == "admin":
        tools = make_admin_tools(user, session)
        return tools["read"] + tools["write"]

    elif role == "teacher":
        tools = make_teacher_tools(user, session)
        return tools["read"] + tools["write"]

    elif role == "student":
        tools = make_student_tools(user, session)
        return tools["read"] + tools["write"]

    elif role == "parent":
        tools = make_parent_tools(user, session)
        return tools["read"] + tools["write"]

    return []
