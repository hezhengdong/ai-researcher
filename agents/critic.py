"""Critic agent: reviews the draft and produces a list of issues."""

import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from state import State

CRITIC_PROMPT = """\
你是一个学术文献综述的审稿人，强制使用中文输出所有内容。你将收到一篇完整的综述草稿以及所有被引用论文的列表（每篇带 [N] 编号）。

审查项目：

硬检查：
- 综述中所有 [N] 引用标记的 N 是否在 1 到论文总数的范围内
- 论文列表中是否有完全未被引用的论文（遗漏）

软检查：
- 各章间逻辑是否连贯，是否存在前后矛盾
- 是否在真正做跨论文的比较分析，而非简单罗列
- Introduction 是否准确概括了各章的核心内容
- References 节是否完整列出了正文中实际引用过的所有论文

输出格式：
- 如果发现问题，每个问题一行，格式为 "- [类别] 问题描述（例如：「- [硬检查] 引用 [5] 超出论文列表范围」）
- 如果没有问题，输出 "OK"

注意：只指出问题，不要给出修改建议。"""


def _make_llm():
    return ChatOpenAI(
        model=os.environ.get("LLM_MODEL", "deepseek-v4-flash"),
        base_url=os.environ.get("LLM_BASE_URL", "https://api.deepseek.com"),
        api_key=os.environ["LLM_API_KEY"],
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
    )


def critic(state: State) -> dict:
    print(f"\n{'='*50}")
    print(f"  Critic 开始审稿 (第 {state.get('retry_count', 0)+1} 轮)")
    print(f"{'='*50}", flush=True)

    llm = _make_llm()

    papers_summary = "\n".join(
        f"- [{i+1}] {p['title']}" for i, p in enumerate(state["papers"])
    )

    user_content = f"""\
论文列表:
{papers_summary}

综述草稿:
{state['draft']}"""

    messages = [
        SystemMessage(content=CRITIC_PROMPT),
        HumanMessage(content=user_content),
    ]

    print("  ", end="", flush=True)
    content = ""
    for chunk in llm.stream(messages):
        if chunk.content:
            print(chunk.content, end="", flush=True)
            content += chunk.content
    print()

    issues = _parse_issues(content)
    if issues:
        for issue in issues:
            print(f"  ✗ {issue}", flush=True)
    else:
        print(f"  ✓ 通过", flush=True)
    new_retry = state.get("retry_count", 0) + 1
    return {"issues": issues, "retry_count": new_retry}


def _parse_issues(content: str) -> list[str]:
    content = content.strip()
    if content.upper() == "OK" or content == "":
        return []

    issues = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("-"):
            issues.append(stripped.lstrip("- "))

    return issues
