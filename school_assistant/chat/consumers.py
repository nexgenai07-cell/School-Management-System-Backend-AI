"""
WebSocket Consumer — Handles real-time chat messages.
Authenticates users (via JWTAuthMiddleware, see chat/middleware.py),
checks the session belongs to them, saves messages, and delegates the
actual reply to the bot registry.
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
from chat.services.bot_registry import get_bot_handler

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for AI chatbot conversations."""

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.room_group_name = f"chat_{self.session_id}"

        # STEP 1: Authenticate user
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser):
            await self.close(code=4001)
            return

        # STEP 2: PERMANENT FIX — Wake up Neon DB before the session check
        await database_sync_to_async(connection.ensure_connection)()

        # STEP 3: Session ownership check
        owner_id = await self.get_session_owner_id(self.session_id)
        if owner_id is None or owner_id != user.id:
            await self.close(code=4003)
            return

        self.user = user

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        
        # ✅ NEW: Start keep-alive ping task to prevent idle timeouts
        self.keep_alive_task = asyncio.create_task(self.send_keep_alive())
        
        logger.info("WebSocket connected: User %s, Session %s", user.id, self.session_id)

    async def disconnect(self, close_code):
        # ✅ NEW: Cancel keep-alive task when connection closes
        if hasattr(self, 'keep_alive_task'):
            self.keep_alive_task.cancel()
            
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        logger.info("WebSocket disconnected: %s", self.room_group_name)

    # ✅ NEW: Background task to send ping every 30 seconds
    async def send_keep_alive(self):
        """Send a ping message every 30 seconds to keep the connection alive."""
        while True:
            try:
                await asyncio.sleep(30)
                await self.send(text_data=json.dumps({"type": "ping"}))
            except Exception:
                # Connection closed or error, exit the loop
                break

    async def receive(self, text_data):
        await database_sync_to_async(close_old_connections)()
        """Handle incoming WebSocket messages."""
        print(" RECEIVED CALLED ")   # checking in the terminal
        print("TEXT DATA:", text_data) #checking in the terminal
        
        try:
            data = json.loads(text_data)
            
            # ✅ NEW: Ignore client pings (if frontend sends them)
            if data.get("type") == "ping":
                return

            user_message = data.get("message", "").strip()
            if not user_message:
                return

            # Save user message
            await self.save_message("user", user_message)

            session = await self.get_session(self.session_id)

            # "typing..." indicator while the bot/LLM does its work
            await self.send(json.dumps({"type": "typing", "status": True}))

            # Runs in a real OS thread (not an asyncio task) so the
            # synchronous Django ORM + requests call inside the bot are safe.
            ai_response = await asyncio.to_thread(
                get_bot_handler, self.user, session, user_message
            )

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