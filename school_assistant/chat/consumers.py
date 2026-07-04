"""
WebSocket Consumer — Handles real-time chat messages.
Authenticates users, saves messages, and calls the bot registry.
"""
import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from chat.models import ChatSession, ChatMessage
from chat.services.bot_registry import get_bot_handler

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for AI chatbot conversations."""

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.room_group_name = f"chat_{self.session_id}"

        # Authenticate user
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser):
            await self.close()
            return

        # Check if the session belongs to this user
        session = await self.get_session(self.session_id)
        if not session or session.user.id != user.id:
            await self.close()
            return

        # Join the room
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        logger.info(f"WebSocket connected: User {user.id}, Session {self.session_id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        logger.info(f"WebSocket disconnected: {self.room_group_name}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            user_message = data.get("message", "").strip()
            if not user_message:
                return

            # Save user message
            await self.save_message("user", user_message)

            # Get session and user
            session = await self.get_session(self.session_id)
            user = self.scope["user"]

            # Send "typing..." indicator
            await self.send(json.dumps({"type": "typing", "status": True}))

            # Get AI response (runs in thread to avoid blocking)
            ai_response = await asyncio.to_thread(
                get_bot_handler, user, session, user_message
            )

            # Save AI response
            ai_msg = await self.save_message("assistant", ai_response)

            # Send AI response to client
            await self.send(json.dumps({
                "type": "message",
                "role": "assistant",
                "content": ai_response,
                "message_id": ai_msg.id,
                "created_at": str(ai_msg.created_at),
            }))

        except json.JSONDecodeError:
            await self.send(json.dumps({"type": "error", "error": "Invalid JSON format."}))
        except Exception as e:
            logger.error(f"Error in receive: {e}")
            await self.send(json.dumps({"type": "error", "error": str(e)}))

    @database_sync_to_async
    def get_session(self, session_id):
        try:
            return ChatSession.objects.get(id=session_id)
        except ChatSession.DoesNotExist:
            return None

    @database_sync_to_async
    def save_message(self, role, content):
        return ChatMessage.objects.create(
            session_id=self.session_id,
            role=role,
            content=content,
        )