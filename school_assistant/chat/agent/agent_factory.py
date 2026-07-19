"""
Builds a role-specific agent: LLM (with fallback chain) + tools + system prompt.
"""
from datetime import date
from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware

from chat.services.llm_router import primary, fallback_1, fallback_2
from chat.agent.prompts import ROLE_PROMPTS


def build_agent(user, tools, role):
    print(f"🟢 Agent building for role: {role}")
    today = date.today().isoformat()
    system_prompt = (
        f"{ROLE_PROMPTS[role]}\n\n"
        f"Aaj ki date: {today}. Jab bhi 'is mahine', 'pichle mahine' jaisi "
        f"relative dates poochi jayen, isi date ko base maan kar calculate karo "
        f"-- kabhi khud se koi purani/random date guess mat karo."
    )
    return create_agent(
        model=primary,
        tools=tools,
        system_prompt=system_prompt,
        middleware=[ModelFallbackMiddleware(fallback_1, fallback_2)],
    )


def get_text(message):
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)