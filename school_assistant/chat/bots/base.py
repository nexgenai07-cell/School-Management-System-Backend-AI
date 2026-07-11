"""
Base Bot Class — All Admin Bots inherit from this.
Defines the contract for system_prompt() and build_context(), and wires
together the shared plumbing every bot needs: a deterministic (typo-
tolerant) scope check, recent conversation history, and the LLM call.
"""
import logging
from abc import ABC, abstractmethod
from django.db import close_old_connections
from chat.services.llm import call_llm
from chat.bots.scope import BOT_SCOPE, bot_keyword_hit, find_other_matching_bot

logger = logging.getLogger(__name__)


class BaseBot(ABC):
    """
    Abstract base class for all chatbot handlers.
    Each Admin bot (FeeBot, AttendanceBot, etc.) must implement:
        - system_prompt(): Return the bot's role/personality.
        - build_context(): Fetch and return relevant database data as a string.

    `user`, `session`, and `message` are provided by the bot registry.
    `self.bot_type` (set from session.bot_type, e.g. "fee", "attendance")
    is checked against chat.bots.scope.BOT_SCOPE to catch clearly
    out-of-scope questions BEFORE any DB query or LLM call is made.
    """

    HISTORY_LIMIT = 6  # last N messages included so follow-ups ("and last month?") work

    def __init__(self, user, session, message):
        self.user = user
        self.session = session
        self.bot_type = session.bot_type or "general"
        self.message = message

    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt defining the bot's role."""
        pass

    @abstractmethod
    def build_context(self) -> str:
        """Fetch database data relevant to self.message and return as a formatted string."""
        pass

    # ── Scope check ──────────────────────────────────────────────────────

    def out_of_scope_response(self, better_bot_label: str) -> str:
        my_label = BOT_SCOPE.get(self.bot_type, {}).get("label", "this bot")
        return (
            f"Yeh sawal **{my_label}** ke scope mein nahi aata, isliye main iska sahi "
            f"jawab nahi de sakta.\n\nAdmin Bot Hub mein ja kar **{better_bot_label}** "
            "select karein — yeh is tarah ke sawalon ke liye scoped hai."
        )

    # ── History + response generation ───────────────────────────────────

    def recent_history(self) -> str:
        """Returns the last few turns of this session as plain text, oldest first."""
        from chat.models import ChatMessage

        messages = list(
            ChatMessage.objects.filter(session=self.session)
            .order_by("-created_at")[: self.HISTORY_LIMIT]
        )
        if not messages:
            return ""
        messages.reverse()
        lines = [f"{m.role}: {m.content}" for m in messages]
        return "Recent conversation (for context on follow-up questions):\n" + "\n".join(lines)

    def get_response(self) -> str:
        close_old_connections()
        # Deterministic, typo-tolerant scope check -- runs before any DB
        # query or LLM call. Only rejects when this bot's OWN keywords
        # are absent AND another bot's keywords are clearly present --
        # so genuine follow-ups ("and last month?") or small talk (no
        # keywords at all) still go through normally instead of being
        # falsely blocked.
        if self.bot_type in BOT_SCOPE:
            text_l = self.message.lower()
            own_match = bot_keyword_hit(self.bot_type, text_l)
            if not own_match:
                better_bot_label = find_other_matching_bot(self.bot_type, text_l)
                if better_bot_label:
                    return self.out_of_scope_response(better_bot_label)

        try:
            data_context = self.build_context()
        except Exception:
            logger.exception("Bot %s failed while building context", self.__class__.__name__)
            data_context = (
                "(Live data could not be retrieved due to an internal error. "
                "Let the Admin know this specific data isn't available right now, "
                "don't guess numbers.)"
            )

        history = self.recent_history()
        full_context = f"{history}\n\n{data_context}".strip() if history else data_context
        return call_llm(self.system_prompt(), self.message, full_context)