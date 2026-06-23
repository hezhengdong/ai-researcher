"""Test for Searcher agent with real API calls."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from agents.searcher import searcher

load_dotenv()

state = {
    "topic": "system design",
    "papers": [],
    "outline": [],
    "current_section_index": -1,
    "chapters": [],
    "draft": "",
    "issues": [],
    "retry_count": 0,
}

print("Testing Searcher for topic: system design...\n")
result = searcher(state)

papers = result["papers"]
print(f"Found {len(papers)} papers:\n")
for i, p in enumerate(papers):
    print(f"  {i+1}. [{p['id']}] {p['title']}")
    print(f"     Year: {p.get('year')}, Citations: {p.get('citation_count')}")
    print(f"     Authors: {', '.join(p.get('authors', []))}")
    print(f"     Source: {p.get('source_type', 'none')}")
    has_md = bool(p.get("markdown"))
    print(f"     Has fulltext: {has_md} ({len(p.get('markdown', ''))} chars)")
    print()

    # 持久化每篇论文为独立 Markdown 文件
    output_dir = Path(__file__).parent.parent / "output" / "papers"
    output_dir.mkdir(parents=True, exist_ok=True)
    for p in papers:
        filename = f"{p['id']}.md"
        filepath = output_dir / filename
        content = f"# {p['title']}\n\n"
        content += f"**作者**: {', '.join(p.get('authors', []))}\n\n"
        content += f"**年份**: {p.get('year', 'N/A')}  |  **引用数**: {p.get('citation_count', 'N/A')}\n\n"
        content += f"## 摘要\n\n{p.get('abstract', 'N/A')}\n\n"
        content += f"## 全文\n\n{p.get('markdown', '（未获取到全文）')}\n"
        filepath.write_text(content, encoding="utf-8")

    # 同时保存论文列表 JSON
    index_path = output_dir / "_paper_list.json"
    papers_for_json = [
        {
            "id": p["id"],
            "title": p["title"],
            "authors": p.get("authors", []),
            "year": p.get("year"),
            "citation_count": p.get("citation_count"),
            "source_type": p.get("source_type", "none"),
            "has_fulltext": bool(p.get("markdown")),
        }
        for p in papers
    ]
    index_path.write_text(json.dumps(papers_for_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已保存 {len(papers)} 篇论文到 {output_dir}")
