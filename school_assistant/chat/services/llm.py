# """
# LLM Service — Handles AI API calls (OpenRouter / OpenAI).
# Supports OpenRouter with GPT-4/3.5 and falls back gracefully.
# """
# import json
# import logging
# import requests
# from django.conf import settings

# logger = logging.getLogger(__name__)

# # --- Configuration ---
# OPENROUTER_API_KEY = getattr(settings, "OPENROUTER_API_KEY", "")
# OPENROUTER_BASE_URL = getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
# OPENROUTER_MODEL = getattr(settings, "OPENROUTER_MODEL", "openai/gpt-4o-mini")

# # Fallback to OpenAI if OpenRouter is not configured
# OPENAI_API_KEY = getattr(settings, "OPENAI_API_KEY", "")


# def call_llm(system_prompt: str, user_message: str, context: str = "") -> str:
#     """
#     Send a prompt to the LLM and return the response.
#     Uses OpenRouter as primary, falls back to OpenAI if needed.
#     """
#     prompt = f"""{system_prompt}

# --- Context Data ---
# {context}

# --- User Question ---
# {user_message}

# Provide a helpful, accurate response using the context data above.
# Never invent numbers or facts not present in the context.
# """

#     # Try OpenRouter first
#     if OPENROUTER_API_KEY:
#         return _call_openrouter(prompt)
    
#     # Fallback to OpenAI
#     if OPENAI_API_KEY:
#         return _call_openai(prompt)
    
#     return "AI service is not configured. Please set OPENROUTER_API_KEY or OPENAI_API_KEY."


# def _call_openrouter(prompt: str) -> str:
#     """Call OpenRouter API."""
#     url = f"{OPENROUTER_BASE_URL}/chat/completions"
#     headers = {
#         "Authorization": f"Bearer {OPENROUTER_API_KEY}",
#         "Content-Type": "application/json",
#     }
#     payload = {
#         "model": OPENROUTER_MODEL,
#         "messages": [{"role": "user", "content": prompt}],
#         "temperature": 0.3,
#         "max_tokens": 500,
#     }

#     try:
#         response = requests.post(url, headers=headers, json=payload, timeout=30)
#         response.raise_for_status()
#         data = response.json()
#         return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
#     except requests.exceptions.RequestException as e:
#         logger.error(f"OpenRouter request failed: {e}")
#         return f"I encountered an error connecting to the AI service. Please try again later."


# def _call_openai(prompt: str) -> str:
#     """Fallback: Call OpenAI API directly."""
#     import openai
#     openai.api_key = OPENAI_API_KEY
    
#     try:
#         response = openai.ChatCompletion.create(
#             model="gpt-4o-mini",
#             messages=[{"role": "user", "content": prompt}],
#             temperature=0.3,
#             max_tokens=500,
#         )
#         return response.choices[0].message.content.strip()
#     except Exception as e:
#         logger.error(f"OpenAI request failed: {e}")
#         return f"I encountered an error. Please try again later."