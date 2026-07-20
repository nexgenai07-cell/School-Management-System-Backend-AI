"""
Model chain for the Agent, reordered (July 2026) around actual free-tier
quotas -- see reasoning below.

WHY THE ORDER CHANGED:
OpenRouter's free tier is only ~50 free-model requests/day per account
(20 RPM) until $10 of credit has ever been purchased -- that is a TINY
quota for a team actively testing a chatbot, and it was previously set
as PRIMARY, meaning it was the very first thing to run out every day.

Once it was out, everything fell to Groq, then Gemini (whose free
quota was also cut ~50-80% in late 2025) -- so the whole chain was
regularly getting exhausted by team testing traffic.

NEW ORDER (best free quota + quality + tool-calling reliability first):
  1. primary    = Groq llama-3.3-70b-versatile
                  Best overall pick for this app: strong tool-calling,
                  very fast (LPU hardware), solid free quota
                  (30 RPM / 1,000 RPD / 100K TPD on the 70B model).

  2. fallback_1 = Cerebras llama-3.3-70b
                  Independent billing from Groq. Cerebras' free tier is
                  the most generous of any provider by daily token
                  volume (~1M tokens/day) and is extremely fast
                  (wafer-scale hardware) -- a strong first fallback.

  3. fallback_2 = NVIDIA NIM (only added if NVIDIA_API_KEY is set)
                  Independent billing from both Groq and Cerebras.

  4. fallback_3 = OpenRouter free model
                  Kept as a LATE fallback (not primary) precisely
                  because its daily cap is so small -- it's most useful
                  as a rarely-touched reserve, not the first thing hit.

  5. fallback_4 = Gemini, last resort (lowest/most-cut-back free quota
                  of the 5, but still a real safety net if all 4 above
                  are exhausted).

5 independent-billing providers total means all of them running out on
the same day at once is very unlikely, even under heavy team testing.
"""

from decouple import config
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

_TIMEOUT = 20  # seconds -- fail fast instead of hanging on a slow provider

# ---- 1. Primary: Groq ----
_GROQ_KEY = config("GROQ_API_KEY")
_GROQ_BASE = "https://api.groq.com/openai/v1"

primary = ChatOpenAI(
    model=config("GROQ_MODEL", default="llama-3.3-70b-versatile"),
    base_url=_GROQ_BASE,
    api_key=_GROQ_KEY,
    max_retries=0,
    timeout=_TIMEOUT,
)

# ---- 2. Fallback #1: Cerebras ----
_CEREBRAS_KEY = config("CEREBRAS_API_KEY")
_CEREBRAS_BASE = "https://api.cerebras.ai/v1"

fallback_1 = None
if _CEREBRAS_KEY:
    fallback_1 = ChatOpenAI(
        model=config("CEREBRAS_MODEL", default="llama-3.3-70b"),
        base_url=_CEREBRAS_BASE,
        api_key=_CEREBRAS_KEY,
        max_retries=0,
        timeout=_TIMEOUT,
    )

# ---- 3. Fallback #2: NVIDIA NIM ----
_NVIDIA_KEY = config("NVIDIA_API_KEY", default=None)
_NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"

fallback_2 = None
if _NVIDIA_KEY:
    fallback_2 = ChatOpenAI(
        model=config("NVIDIA_MODEL", default="meta/llama-3.1-70b-instruct"),
        base_url=_NVIDIA_BASE,
        api_key=_NVIDIA_KEY,
        max_retries=0,
        timeout=_TIMEOUT,
    )

# ---- 4. Fallback #3: OpenRouter ----
_OPENROUTER_KEY = config("OPENROUTER_API_KEY")
_OPENROUTER_BASE = "https://openrouter.ai/api/v1"

fallback_3 = None
if _OPENROUTER_KEY:
    fallback_3 = ChatOpenAI(
        model=config("OPENROUTER_MODEL", default="meta-llama/llama-3.3-70b-instruct:free"),
        base_url=_OPENROUTER_BASE,
        api_key=_OPENROUTER_KEY,
        max_retries=0,
        timeout=_TIMEOUT,
    )

# ---- 5. Fallback #4: Gemini ----
_GEMINI_KEY = config("GEMINI_API_KEY")

fallback_4 = ChatGoogleGenerativeAI(
    model=config("GEMINI_MODEL", default="gemini-3.5-flash"),
    google_api_key=_GEMINI_KEY,
    max_retries=0,
    timeout=_TIMEOUT,
)

def get_fallback_chain():
    """Returns the ordered list of fallback models (after `primary`),
    skipping any provider whose key isn't configured in .env yet."""
    chain = []
    for model in (fallback_1, fallback_2, fallback_3):
        if model is not None:
            chain.append(model)
    chain.append(fallback_4)  # Gemini always last, always present
    return chain