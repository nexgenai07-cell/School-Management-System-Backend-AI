'''
SHARED FILE -- edited by both, on different days.
PERSON 1, Day 1: check(), is_own_child()
PERSON 1, Day 4: check_teacher_owns_class()
PERSON 2, Day 4: get_self_context()
'''
"""
Casbin enforcer + ownership-check helpers.
Used by every tool in chat/agent/tools/*.py to verify permission before
running.
"""
import os
import casbin
from django.conf import settings

_MODEL_PATH = os.path.join(settings.BASE_DIR, "conf", "model.conf")
_POLICY_PATH = os.path.join(settings.BASE_DIR, "conf", "policy.csv")

enforcer = casbin.Enforcer(_MODEL_PATH, _POLICY_PATH)


def check(user, resource, action):
    return enforcer.enforce(user.role.role_name.lower(), resource, action)

def is_own_child(parent_user, student_id, session):
    """Parent can only access their currently-active child's data,
    never any arbitrary student_id."""
    from accounts.models import ParentStudentLink  # adjust import path if different
    return (
        session.active_child_id == student_id
        and ParentStudentLink.objects.filter(parent=parent_user, student_id=student_id).exists()
    )