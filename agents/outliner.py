"""Outliner agent: reads papers' titles and first N chars of markdown to produce an outline."""

import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from state import State

OUTLINER_PROMPT = """\
你是一个学术文献综述的大纲撰写专家。你将收到一批论文的标题和正文前 1500 字，需要为这些论文组织一个综述大纲。

工作流程：
1. 通读所有论文的标题和正文前 1500 字
2. 从以下三个维度分析论文之间的关联：
   - 时间线：哪些是奠基论文，哪些是后续发展
   - 问题线：哪些论文在解决同一类问题
   - 传承线：谁基于谁做了改进
3. 将论文自由划分为若干章节（最多 6 章），每章包含一个明确的主题
4. 每篇论文只能归属一个章节，选择最合适的那一章
5. 输出 JSON 格式：

{{
  "sections": [
    {{
      "title": "章节标题",
      "theme": "本章主题的一句话描述",
      "paper_ids": ["paper_id_1", "paper_id_2"]
    }}
  ]
}}

只输出 JSON，不要其他内容。"""


def _make_llm():
    return ChatOpenAI(
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
    )


def outliner(state: State) -> dict:
    print(f"\n{'='*50}")
    print(f"  Outliner 开始，共 {len(state['papers'])} 篇论文")
    print(f"{'='*50}", flush=True)

    llm = _make_llm()

    paper_summaries = []
    for i, p in enumerate(state["papers"]):
        preview = (p.get("markdown", "") or "")[:1500]
        paper_summaries.append(
            f"[{i}] ID: {p['id']}\n"
            f"    标题: {p['title']}\n"
            f"    内容: {preview}"
        )
    papers_text = "\n\n---\n\n".join(paper_summaries)

    messages = [
        SystemMessage(content=OUTLINER_PROMPT),
        HumanMessage(content=papers_text),
    ]

    print("  ", end="", flush=True)
    content = ""
    for chunk in llm.stream(messages):
        if chunk.content:
            print(chunk.content, end="", flush=True)
            content += chunk.content
    print()
    print(f"  ({len(content)} 字符)", flush=True)

    outline = _parse_outline(content)
    for i, sec in enumerate(outline):
        print(f"    第{i+1}章: {sec['title']} ({len(sec['paper_ids'])} 篇)", flush=True)
    return {"outline": outline}


def _parse_outline(content: str) -> list[dict]:
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "sections" in data:
            return data["sections"]
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            return data.get("sections", [])
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return data.get("sections", [])
        except json.JSONDecodeError:
            pass

    return []
