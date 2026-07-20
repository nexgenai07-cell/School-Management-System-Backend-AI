"""
Thin aggregator -- each role's actual prompt now lives in
chat/agent/roles/<role>/prompt.py so changing one role's prompt never
touches this file (or any other role's file). This file just collects
them into the ROLE_PROMPTS dict that agent_factory.py already imports,
so agent_factory.py needed zero changes.
"""
from chat.agent.roles.admin.prompt import PROMPT as ADMIN_PROMPT
from chat.agent.roles.teacher.prompt import PROMPT as TEACHER_PROMPT
from chat.agent.roles.student.prompt import PROMPT as STUDENT_PROMPT
from chat.agent.roles.parent.prompt import PROMPT as PARENT_PROMPT

ROLE_PROMPTS = {
    "admin": ADMIN_PROMPT,
    "teacher": TEACHER_PROMPT,
    "student": STUDENT_PROMPT,
    "parent": PARENT_PROMPT,
}
