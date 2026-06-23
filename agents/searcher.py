"""Searcher agent: ReAct-style, uses tools to find papers, batch downloads PDFs after."""

import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from state import State
from tools import batch_download_and_parse, tavily_extract, tavily_search

SEARCHER_PROMPT = """\
你是一个学术文献搜索专家，任务是找到某个 CS 领域的经典必读论文。强制使用中文输出所有内容。

注意：最多找 3 篇论文即可。

你有两个工具：
- tavily_search: 搜索网页，返回结果摘要和 URL
- tavily_extract: 提取某个 URL 页面的全文内容

工作分为两个阶段：

**阶段一：发现经典论文**
1. 用 tavily_search 搜 "{topic} classic papers reading list"
2. 对搜索结果中看起来像论文列表页面的 URL，用 tavily_extract 提取全文
3. 从页面全文中识别出所有经典论文的标题，列出来

**阶段二：找 PDF 链接**
1. 对每篇论文标题，用 tavily_search 搜 "{论文标题} PDF"
2. 优先选择 .edu 域名或作者主页的 PDF 链接
3. 记录每篇论文的 PDF 链接

全部完成后，输出一个 JSON 数组：

[
  {
    "id": "简短英文id",
    "title": "论文正式标题",
    "pdf_url": "https://..."
  }
]

- 如果某篇找不到 PDF，pdf_url 为空字符串
- 只输出 JSON 数组，不要其他内容"""


def _make_llm():
    return ChatOpenAI(
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        streaming=True,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
    )


def _log(msg: str):
    print(f"  {msg}", flush=True)


def searcher(state: State) -> dict:
    llm = _make_llm()
    # LLM 只负责搜索和提取，下载解析由代码批量完成
    tools = [tavily_search, tavily_extract]
    llm_with_tools = llm.bind_tools(tools)
    tool_map = {"tavily_search": tavily_search, "tavily_extract": tavily_extract}

    messages = [
        SystemMessage(content=SEARCHER_PROMPT),
        HumanMessage(content=state["topic"]),
    ]

    print(f"\n{'='*50}")
    print(f"  Searcher，话题: {state['topic']}")
    print(f"{'='*50}")

    # === 阶段一：LLM 搜索发现论文和 PDF 链接 ===
    max_turns = 30
    for turn in range(max_turns):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for tc in response.tool_calls:
            tool_name = tc["name"]
            _log(f"[第 {turn+1} 轮] {tool_name}")

            fn = tool_map.get(tool_name)
            try:
                result = str(fn(**tc["args"]))
            except Exception as e:
                result = f"Error: {e}"

            if len(result) > 8000:
                result = result[:8000] + f"\n... (截断，原 {len(result)} 字符)"

            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
    else:
        print(f"\n  ✗ 错误：超过 {max_turns} 轮")
        return {"papers": []}

    content = response.content or ""
    papers = _parse_papers(content)
    print(f"\n  ✓ 搜索完成: {len(papers)} 篇论文")

    # === 阶段二：代码批量下载并解析 PDF ===
    pdf_urls = [p.get("pdf_url", "") for p in papers]
    parsed = batch_download_and_parse(pdf_urls)

    for i, p in enumerate(papers):
        p["markdown"] = parsed[i]["markdown"]
        p["source_type"] = parsed[i]["source_type"]
        p.pop("pdf_url", None)

    print(f"  ✓ Searcher 完成: {len(papers)} 篇")
    return {"papers": papers}


def _parse_papers(content: str) -> list[dict]:
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\[.*\]", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    print(f"  ⚠ 无法解析: {content[:500]}")
    return []
