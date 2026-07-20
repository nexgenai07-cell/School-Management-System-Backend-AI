"""
WebSocket Consumer — Handles real-time chat messages.
"""
import json
import asyncio
import logging
from django.db import connection, close_old_connections
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser

from chat.models import ChatSession, ChatMessage, PendingAction
from chat.agent.agent_factory import build_agent, get_text
from chat.agent.tool_registry import get_tools_for_role

logger = logging.getLogger(__name__)

# Each role's WRITE-tool executors now live next to that role's tools
# (chat/agent/roles/<role>/executors.py) instead of all being defined
# inline in this file. Changing what happens when e.g. a Student WRITE
# action is confirmed only ever touches roles/student/executors.py --
# this file (and every other role) is untouched.
from chat.agent.roles.admin.executors import TOOL_REGISTRY as ADMIN_REGISTRY
from chat.agent.roles.teacher.executors import TOOL_REGISTRY as TEACHER_REGISTRY
from chat.agent.roles.student.executors import TOOL_REGISTRY as STUDENT_REGISTRY
from chat.agent.roles.parent.executors import TOOL_REGISTRY as PARENT_REGISTRY

# Merged lookup used by handle_pending_action() below. Since "file_complaint"
# is intentionally the same shared executor in all 3 non-admin registries,
# merging is safe -- there's no real key collision, just the same function
# registered multiple times under the same name.
TOOL_REGISTRY = {**ADMIN_REGISTRY, **TEACHER_REGISTRY, **STUDENT_REGISTRY, **PARENT_REGISTRY}

WELCOME_MESSAGES = {
    "admin": "Assalam-o-Alaikum! Main aapka Admin AI assistant hoon. Fees, attendance, complaints, events, ya kisi bhi school-data ke baare mein pooch sakte hain.",
    "teacher": "Assalam-o-Alaikum! Main aapka Teacher assistant hoon. Apni class, attendance, ya assignments ke baare mein pooch sakte hain.",
    "student": "Assalam-o-Alaikum! Main aapka assistant hoon. Apni attendance, grades, ya fee-status pooch sakte hain.",
    "parent": "Assalam-o-Alaikum! Main aapka assistant hoon. Apne bachay ka data dekhne ke liye bata dein kis bachay ki baat karni hai.",
}


class ChatConsumer(AsyncWebsocketConsumer):
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
        self.session = await self.get_session(self.session_id)

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        logger.info("WebSocket connected: User %s, Session %s", user.id, self.session_id)

        self.keep_alive_task = asyncio.create_task(self.send_keep_alive())

        await self.send_welcome_if_new()

    async def disconnect(self, close_code):
        if hasattr(self, "keep_alive_task"):
            self.keep_alive_task.cancel()
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def send_welcome_if_new(self):
        has_messages = await self.session_has_messages(self.session_id)
        if has_messages:
            return
        role = self.user.role.role_name.lower()
        text = WELCOME_MESSAGES.get(role, "Assalam-o-Alaikum! Kaise madad kar sakta hoon?")
        msg = await self.save_message(self.session, "assistant", text)
        await self.safe_send({
            "type": "message", "role": "assistant", "content": text,
            "message_id": msg.id, "created_at": str(msg.created_at),
        })

    async def send_keep_alive(self):
        while True:
            try:
                await asyncio.sleep(30)
                await self.safe_send({"type": "ping"})
            except asyncio.CancelledError:
                break
            except Exception:
                break

    async def safe_send(self, data):
        try:
            await self.send(json.dumps(data))
        except RuntimeError:
            logger.warning("Tried to send after connection was already closed (client disconnected).")

    async def receive(self, text_data):
        await database_sync_to_async(close_old_connections)()
        try:
            data = json.loads(text_data)
            if data.get("type") == "ping":
                return

            user_message = data.get("message", "").strip()
            if not user_message:
                return

            session = await self.get_session(self.session_id)
            await self.save_message(session, "user", user_message)
            await self.safe_send({"type": "typing", "status": True})

            pending = await self.get_pending_action(session)
            if pending:
                reply = await self.handle_pending_action(pending, user_message)
                ai_msg = await self.save_message(session, "assistant", reply)
                await self.safe_send({
                    "type": "message", "role": "assistant", "content": reply,
                    "message_id": ai_msg.id, "created_at": str(ai_msg.created_at),
                })
                return

            role = self.user.role.role_name.lower()
            history = await self.get_chat_history(session)
            tools = get_tools_for_role(role, self.user, session)

            ai_reply = await self.run_agent(self.user, tools, role, history, user_message)

            ai_msg = await self.save_message(session, "assistant", ai_reply)
            await self.safe_send({
                "type": "message", "role": "assistant", "content": ai_reply,
                "message_id": ai_msg.id, "created_at": str(ai_msg.created_at),
            })

        except json.JSONDecodeError:
            await self.safe_send({"type": "error", "error": "Invalid JSON format."})
        except Exception as e:
            # FIX: this used to send f"Something went wrong: {str(e)}" straight
            # to the user -- if every model in the fallback chain was out of
            # quota, that raw provider error (e.g. "402 Payment Required",
            # rate-limit JSON, etc.) leaked directly into the chat. The full
            # exception is still logged server-side for debugging; the user
            # just gets a friendly, actionable message.
            logger.exception("Error in ChatConsumer.receive")
            await self.safe_send({
                "type": "error",
                "error": "Abhi AI assistant thodi der ke liye busy hai (saare available models "
                         "busy/limit pe hain). Thodi der baad dobara try karein.",
            })

    @sync_to_async
    def run_agent(self, user, tools, role, history, user_message):
        agent = build_agent(user, tools, role)
        messages = history + [{"role": "user", "content": user_message}]
        result = agent.invoke({"messages": messages})
        reply = get_text(result["messages"][-1])
        print(f"\n🤖 [DEBUG] Agent reply: {reply}\n")
        return reply

    @database_sync_to_async
    def handle_pending_action(self, pending, user_message):
        """
        FIXED: the real DB schema for PendingAction is (tool_name, params,
        status) -- there is no action_name or summary column. The
        human-readable summary is instead stashed inside params["_summary"]
        by each tool's _propose() helper, and stripped back out here before
        calling the executor.
        """
        text = user_message.lower()
        if text in ("yes", "haan", "han"):
            tool_name = pending.tool_name
            executor = TOOL_REGISTRY.get(tool_name)
            params = {k: v for k, v in pending.params.items() if k != "_summary"}
            # IMPORTANT: delete BEFORE executing -- if the executor raises
            # (duplicate/ambiguous record, bad data, etc), the session must
            # not get permanently stuck re-asking to confirm the same
            # broken action on every subsequent message.
            pending.delete()
            if not executor:
                return f"'{tool_name}' action ka executor register nahi hai (TOOL_REGISTRY check karo)."
            try:
                return executor(**params)
            except Exception as e:
                logger.exception("Error executing pending action %s", tool_name)
                return f"Action complete nahi ho saka: {str(e)}"
        elif text in ("no", "nahi", "nhi"):
            pending.delete()
            return "Cancel kar diya."
        else:
            summary = pending.params.get("_summary", pending.tool_name)
            return f"Pehle confirm karein: '{summary}' -- (yes/no)"

    @database_sync_to_async
    def get_session_owner_id(self, session_id):
        return ChatSession.objects.filter(id=session_id).values_list("user_id", flat=True).first()

    @database_sync_to_async
    def get_session(self, session_id):
        return ChatSession.objects.select_related("user", "active_child").get(id=session_id)

    @database_sync_to_async
    def session_has_messages(self, session_id):
        return ChatMessage.objects.filter(session_id=session_id).exists()

    @database_sync_to_async
    def get_pending_action(self, session):
        return PendingAction.objects.filter(session=session).first()

    @database_sync_to_async
    def get_chat_history(self, session, limit=6):
        msgs = ChatMessage.objects.filter(session=session).order_by("-created_at")[:limit]
        return [{"role": m.role, "content": m.content} for m in reversed(list(msgs))]

    @database_sync_to_async
    def save_message(self, session, role, content):
        return ChatMessage.objects.create(session=session, role=role, content=content)