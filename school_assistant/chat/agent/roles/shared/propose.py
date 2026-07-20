"""
Shared propose() builder for the WRITE-tool confirm flow.

BUG HISTORY: every role's tools.py used to define its own local _propose()
helper, copy-pasted 4 times. All 4 copies wrote
{"action_name": ..., "params": ..., "summary": ...} to PendingAction --
but the model's real fields are (tool_name, params, status) (see
migrations/0004_sync_pendingaction_schema.py). That mismatch crashed
every single WRITE tool, in every role, with a TypeError.

Centralizing this in ONE file means that kind of bug can only exist in
one place now, and fixing it once fixes it for all 4 roles.
"""
from chat.models import PendingAction


def make_propose(session):
    """Returns a _propose(tool_name, params, summary) function bound to
    this chat session. Call once per role's make_X_tools(user, session)
    and use the returned function for every WRITE tool."""

    def _propose(tool_name, params, summary):
        PendingAction.objects.update_or_create(
            session=session,
            defaults={
                "tool_name": tool_name,
                # the human-readable summary rides inside params["_summary"] --
                # consumers.py's handle_pending_action() reads it from there.
                "params": {**params, "_summary": summary},
                "status": "pending",
            },
        )
        return f"CONFIRM: {summary} (yes/no)"

    return _propose
