import os

from langchain_openai import ChatOpenAI


def make_llm(streaming: bool = False):
    return ChatOpenAI(
        model=os.environ.get("LLM_MODEL", "deepseek-v4-flash"),
        base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"),
        api_key=os.environ["LLM_API_KEY"],
        reasoning_effort="high",
        streaming=streaming,
        extra_body={"thinking": {"type": "enabled"}},
    )
