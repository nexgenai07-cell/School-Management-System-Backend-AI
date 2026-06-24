from rest_framework import viewsets
from accounts.permissions import IsStudent
from chat.models import ChatSession, ChatMessage
from chat.serializers.student import StudentChatSessionSerializer, StudentChatMessageSerializer

class StudentChatSessionViewSet(viewsets.ModelViewSet):
    """Students can create and view their own chat sessions."""
    serializer_class = StudentChatSessionSerializer
    permission_classes = [IsStudent]

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, bot_type="general")


class StudentChatMessageViewSet(viewsets.ModelViewSet):
    """Students can send and view messages in their sessions."""
    serializer_class = StudentChatMessageSerializer
    permission_classes = [IsStudent]

    def get_queryset(self):
        return ChatMessage.objects.filter(session__user=self.request.user).order_by("created_at")

    def perform_create(self, serializer):
        serializer.save(session_id=self.request.data.get("session"), role="user")
