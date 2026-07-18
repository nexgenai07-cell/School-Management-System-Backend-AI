"""
Model chain for the Agent: OpenRouter (2 models) primary, Gemini as final
fallback -- since Gemini's free tier has a very low daily quota (20
requests/day), OpenRouter now carries the main load.
"""
from decouple import config
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

_OPENROUTER_KEY = config("OPENROUTER_API_KEY")
_OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Primary -- fast, capable, cheap
primary = ChatOpenAI(
    model="openai/gpt-4o-mini",
    base_url=_OPENROUTER_BASE,
    api_key=_OPENROUTER_KEY,
    max_retries=0,
)

# Fallback #1 -- different OpenRouter model (if gpt-4o-mini is down/rate-limited)
fallback_1 = ChatOpenAI(
    model="meta-llama/llama-3.1-8b-instruct",
    base_url=_OPENROUTER_BASE,
    api_key=_OPENROUTER_KEY,
    max_retries=0,
)

# Fallback #2 -- Gemini, last resort (low daily quota)
fallback_2 = ChatGoogleGenerativeAI(
    model=config("GEMINI_MODEL", default="gemini-2.5-flash"),
    google_api_key=config("GEMINI_API_KEY"),
    max_retries=0,
)