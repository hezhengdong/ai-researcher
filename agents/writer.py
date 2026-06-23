"""Writer agent: writes one chapter based on assigned papers. Runs in parallel via Send."""

import os
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from state import State

WRITER_PROMPT = """\
你是一个学术文献的章节撰写专家。你将收到：
- 一个章节标题和主题描述
- 该章关联的论文的标题和 Markdown 正文

撰写要求：
1. 按演进逻辑组织内容，而非逐篇罗列。格式应当类似：
   "A 提出了 X 方法，但受限于 Y。B 通过 Z 改进了这一问题。C 则走了不同路线，采用 W 方案。"
2. 引用论文时使用 [paper_id] 标注
3. 控制篇幅在 800-1500 字
4. 不要写子标题，以连贯散文形式输出
5. 在开头用一句话承接本章在领域中的位置
6. 在结尾用一句话总结本章的核心贡献

输出该章的完整正文，不要输出其他内容。"""

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "chapters"


def _make_llm():
    return ChatOpenAI(
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}},
    )


def writer(state: State) -> dict:
    llm = _make_llm()

    section = state["outline"][state["current_section_index"]]
    section_title = section["title"]
    section_theme = section["theme"]
    paper_ids = section["paper_ids"]

    chapter_num = state["current_section_index"] + 1
    total = len(state["outline"])

    # 收集分配的论文
    paper_map = {p["id"]: p for p in state["papers"]}
    assigned_papers = [paper_map[pid] for pid in paper_ids if pid in paper_map]

    print(f"  [Writer {chapter_num}/{total}] {section_title} ({len(assigned_papers)} 篇)", flush=True)

    # 构建论文上下文
    paper_texts = []
    for p in assigned_papers:
        md = p.get("markdown", "") or ""
        text = f"## [{p['id']}] {p['title']}\n\n{md[:6000]}"
        paper_texts.append(text)

    papers_context = "\n\n---\n\n".join(paper_texts)

    user_content = f"""\
章节 {chapter_num}/{total}: {section_title}
主题: {section_theme}

以下是与本章相关的论文：

{papers_context}"""

    messages = [
        SystemMessage(content=WRITER_PROMPT),
        HumanMessage(content=user_content),
    ]

    # 流式收集 LLM 输出，写入文件。并行时不乱码。
    chapter_content = ""
    for chunk in llm.stream(messages):
        if chunk.content:
            chapter_content += chunk.content

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / f"chapter_{chapter_num:02d}.md"
    filepath.write_text(chapter_content, encoding="utf-8")

    print(f"  [Writer {chapter_num}/{total}] {section_title} → {len(chapter_content)} 字 → {filepath}", flush=True)

    return {"chapters": [chapter_content]}
