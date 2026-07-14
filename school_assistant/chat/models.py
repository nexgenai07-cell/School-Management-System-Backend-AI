"""
CHAT APP
========
AI chatbot conversation storage. Real-time message delivery is handled
separately by a Channels WebSocket consumer (to be added later in
chat/consumers.py and chat/routing.py) -- this file only defines the
persistence layer.

Cross-app references used in this file:
- ChatSession.user -> accounts.User
- ChatSession.active_child -> accounts.StudentProfile
"""

from django.db import models


class ChatSession(models.Model):
    """One conversation thread."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="chat_sessions")
    title = models.CharField(max_length=200, blank=True)  # auto-filled from the first user message

    # Only meaningful when user.role == Parent -- tracks which child the
    # conversation is currently scoped to, matching the child-toggle on
    # the Parent Dashboard (Page 31).
    active_child = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"{self.user.email} ({self.created_at})"


class ChatMessage(models.Model):
    ROLE_CHOICES = (("user", "user"), ("assistant", "assistant"))

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.session.user.email} - {self.role} ({self.created_at})"

    class Meta:
        ordering = ["created_at"]
class PendingAction(models.Model):
    bot_type = models.CharField(max_length=20)
    action_name = models.CharField(max_length=50)
    params = models.JSONField(default=dict)
    summary = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    session = models.OneToOneField(
        ChatSession, on_delete=models.CASCADE, related_name="pending_action"
    )