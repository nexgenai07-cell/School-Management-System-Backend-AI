"""
LLM Service — Handles AI API calls for every Admin bot.
Uses OpenRouter (https://openrouter.ai) as a single gateway so the
model can be swapped later (GPT-4o-mini, Claude, Llama, etc.) purely
via the OPENROUTER_MODEL env var, with no code changes.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = getattr(settings, "OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = getattr(settings, "OPENROUTER_MODEL", "openai/gpt-4o-mini")

REQUEST_TIMEOUT = 30  # seconds -- fail fast rather than hang the WebSocket

# Anything longer than this gets trimmed before it's sent to the model.
# Bots should already be sending summaries, not raw table dumps, but this
# is a hard safety net against a bug pulling in too many rows.
MAX_CONTEXT_CHARS = 12000


def call_llm(system_prompt: str, user_message: str, context: str = "") -> str:
    """
    Send a prompt to the LLM and return its reply as plain text.
    `context` is the live database data the calling bot fetched for
    this specific question; the model is instructed to only use that
    data and never invent numbers.
    """
    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY not set — chatbot cannot reach the LLM.")
        return (
            "AI chatbot is not configured yet. Ask your developer to set "
            "OPENROUTER_API_KEY in the .env file."
        )

    if context and len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n...(data truncated)"

    full_system_prompt = f"""{system_prompt}

--- Live Database Context ---
{context or "(no relevant data found for this question)"}

Rules:
- Only use facts present in the "Live Database Context" above.
- If the context doesn't contain the answer, say so plainly instead of guessing.
- Never invent names, numbers, dates, or amounts.
- Keep replies concise and well formatted (short paragraphs or bullet points).
- Amounts are in PKR unless stated otherwise.
- If the Admin's question has nothing to do with school administration at
  all (general chit-chat, unrelated trivia, personal questions, etc.),
  politely say you're scoped to school administration tasks only and
  can't help with that -- don't try to force an answer using the context.
"""

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "max_tokens": 600,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": getattr(settings, "FRONTEND_URL", "http://localhost:5173"),
        "X-Title": "School ERP Admin Assistant",
    }

    try:
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return content or "I couldn't generate a response for that. Please rephrase your question."
    except requests.exceptions.Timeout:
        logger.error("OpenRouter request timed out.")
        return "The AI service took too long to respond. Please try again."
    except requests.exceptions.RequestException as e:
        logger.error("OpenRouter request failed: %s", e)
        return "I encountered an error connecting to the AI service. Please try again later."
    except (KeyError, IndexError, ValueError) as e:
        logger.error("Unexpected OpenRouter response shape: %s", e)
        return "I received an unexpected response from the AI service. Please try again."