from rest_framework import viewsets
from accounts.permissions import IsParent
from chat.models import ChatSession, ChatMessage
from chat.serializers.parent import ParentChatSessionSerializer, ParentChatMessageSerializer

class ParentChatSessionViewSet(viewsets.ModelViewSet):
    """Parents can create and view their own chat sessions, scoped to a child."""
    serializer_class = ParentChatSessionSerializer
    permission_classes = [IsParent]

    def get_queryset(self):
        return ChatSession.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, bot_type="general")


class ParentChatMessageViewSet(viewsets.ModelViewSet):
    """Parents can send and view messages in their sessions."""
    serializer_class = ParentChatMessageSerializer
    permission_classes = [IsParent]

    def get_queryset(self):
        return ChatMessage.objects.filter(session__user=self.request.user).order_by("created_at")

    def perform_create(self, serializer):
        serializer.save(session_id=self.request.data.get("session"), role="user")
