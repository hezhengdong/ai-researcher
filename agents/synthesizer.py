"""Synthesizer agent: merges chapters into a complete survey draft."""

import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from state import State

SYNTHESIZER_PROMPT = """\
你是一个学术文献综述的汇总编辑。你将收到多篇独立的章节正文，需要将其整合为一篇完整的综述。

工作流程：
1. 撰写 Introduction：概述该领域的重要性、主要演进脉络、本综述的组织逻辑
2. 将各章节按顺序组织，添加适当的过渡
3. 检测跨章节的重复内容：同一篇论文若在多处被提及，保留一处详细讨论，其余简化为简短提及或删除
4. 统一文风：确保各章的语气、用词、句式风格一致
5. 撰写 Conclusion：总结关键发现和思想演进
6. 输出完整的综述全文

输出完整的综述全文，不要输出其他内容。"""

RETRY_PROMPT = """\
你是一个学术文献综述的汇总编辑。你将收到一份已完成的综述草稿以及审稿人提出的问题。

请根据审稿人的问题修改草稿：
1. 只修改被指出的问题，不要重写整个综述
2. 保持原有的结构和文风
3. 修改后输出完整的综述全文

审稿人的问题：
{issues}

以下是当前草稿：

{draft}"""


def _make_llm():
    return ChatOpenAI(
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
    )


def synthesizer(state: State) -> dict:
    stage = "修订" if state.get("issues") else "初稿"
    print(f"\n{'='*50}")
    print(f"  Synthesizer ({stage}) 开始, {len(state.get('chapters', []))} 个章节")
    print(f"{'='*50}", flush=True)

    llm = _make_llm()

    chapters_text = _format_chapters(state)
    outline_text = _format_outline(state)

    if state.get("issues"):
        print(f"  审稿意见: {state['issues']}", flush=True)
        user_content = RETRY_PROMPT.format(
            issues="\n".join(f"- {i}" for i in state["issues"]),
            draft=state["draft"],
        )
    else:
        # First pass: build from chapters
        user_content = f"""\
话题: {state['topic']}

大纲:
{outline_text}

各章节内容:

{chapters_text}"""

    messages = [
        SystemMessage(content=SYNTHESIZER_PROMPT),
        HumanMessage(content=user_content),
    ]

    print("  ", end="", flush=True)
    draft = ""
    for chunk in llm.stream(messages):
        if chunk.content:
            print(chunk.content, end="", flush=True)
            draft += chunk.content
    print()
    print(f"  Synthesizer 完成: {len(draft)} 字符", flush=True)
    return {"draft": draft}


def _format_chapters(state: State) -> str:
    parts = []
    for i, (ch, sec) in enumerate(
        zip(state.get("chapters", []), state.get("outline", []))
    ):
        title = sec.get("title", f"Chapter {i+1}") if i < len(state["outline"]) else f"Chapter {i+1}"
        parts.append(f"## {title}\n\n{ch}")
    return "\n\n".join(parts)


def _format_outline(state: State) -> str:
    parts = []
    for i, sec in enumerate(state.get("outline", [])):
        parts.append(f"{i+1}. {sec['title']} — {sec['theme']}")
    return "\n".join(parts)
