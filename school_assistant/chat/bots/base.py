"""
Base Bot Class — All Admin Bots inherit from this.
Defines the contract for system_prompt() and build_context().
"""
from abc import ABC, abstractmethod
from chat.services.llm import call_llm


class BaseBot(ABC):
    """
    Abstract base class for all chatbot handlers.
    Each Admin bot (FeeBot, AttendanceBot, etc.) must implement:
        - system_prompt(): Return the bot's role/personality.
        - build_context(): Fetch and return relevant database data as a string.
    """

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
        """Fetch database data and return as a formatted string."""
        pass

    def get_response(self) -> str:
        """Generate AI response using the context and system prompt."""
        context = self.build_context()
        return call_llm(self.system_prompt(), self.message, context)