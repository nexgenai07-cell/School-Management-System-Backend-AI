"""
WebSocket Consumer — Handles real-time chat messages.
Authenticates users (via JWTAuthMiddleware, see chat/middleware.py),
checks the session belongs to them, saves messages, and delegates the
actual reply to the AI agent.
"""
import json
import asyncio
import logging
from django.db import connection
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.db import close_old_connections
from chat.models import ChatSession, ChatMessage

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for AI chatbot conversations."""

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.room_group_name = f"chat_{self.session_id}"

        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser):
            await self.close(code=4001)
            return

        await database_sync_to_async(connection.ensure_connection)()

        owner_id = await self.get_session_owner_id(self.session_id)
        if owner_id is None or owner_id != user.id:
            await self.close(code=4003)
            return

        self.user = user

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        self.keep_alive_task = asyncio.create_task(self.send_keep_alive())
        logger.info("WebSocket connected: User %s, Session %s", user.id, self.session_id)

    async def disconnect(self, close_code):
        if hasattr(self, 'keep_alive_task'):
            self.keep_alive_task.cancel()
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        logger.info("WebSocket disconnected: %s", self.room_group_name)

    async def send_keep_alive(self):
        while True:
            try:
                await asyncio.sleep(30)
                await self.send(text_data=json.dumps({"type": "ping"}))
            except Exception:
                break

    async def receive(self, text_data):
        await database_sync_to_async(close_old_connections)()
        try:
            data = json.loads(text_data)
            if data.get("type") == "ping":
                return

            user_message = data.get("message", "").strip()
            if not user_message:
                return

            await self.save_message("user", user_message)
            session = await self.get_session(self.session_id)
            await self.send(json.dumps({"type": "typing", "status": True}))

            # TEMPORARY placeholder — naye 7-day plan mein yahan real
            # Agent-call aayega (role-based tools + LLM). Abhi ke liye
            # sirf ek static response taake system chalta rahe.
            ai_response = "AI system rebuild ho raha hai, thodi der mein wapas aayega."

            ai_msg = await self.save_message("assistant", ai_response)

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
            logger.exception("Error in ChatConsumer.receive")
            await self.send(json.dumps({"type": "error", "error": "Something went wrong. Please try again."}))

    @database_sync_to_async
    def get_session_owner_id(self, session_id):
        return ChatSession.objects.filter(id=session_id).values_list("user_id", flat=True).first()

    @database_sync_to_async
    def get_session(self, session_id):
        try:
            return ChatSession.objects.select_related("user", "active_child").get(id=session_id)
        except ChatSession.DoesNotExist:
            return None

    @database_sync_to_async
    def save_message(self, role, content):
        return ChatMessage.objects.create(
            session_id=self.session_id,
            role=role,
            content=content,
        )