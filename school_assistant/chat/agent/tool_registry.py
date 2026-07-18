from chat.agent.tools.admin_tools import make_admin_tools
from chat.agent.tools.teacher_tools import make_teacher_tools
from chat.agent.tools.student_tools import make_student_tools
from chat.agent.tools.parent_tools import make_parent_tools


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