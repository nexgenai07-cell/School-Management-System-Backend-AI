"""
Parent's WRITE-tool executors -- currently just the shared file_complaint.
Add more here as more Parent WRITE tools are built.
"""
from chat.agent.roles.shared.executors import _execute_file_complaint

TOOL_REGISTRY = {
    "file_complaint": _execute_file_complaint,  # shared
}
