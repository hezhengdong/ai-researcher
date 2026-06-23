"""Entry point for the AI Researcher survey generation system.

Usage:
    python main.py "分布式系统"
    python main.py "distributed systems"
"""

import sys

from dotenv import load_dotenv

from agents.graph import graph
from agents.state import State


def main():
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python main.py <topic>")
        sys.exit(1)

    topic = sys.argv[1]

    initial_state: State = {
        "topic": topic,
        "papers": [],
        "outline": [],
        "current_section_index": -1,
        "chapters": [],
        "draft": "",
        "issues": [],
        "retry_count": 0,
    }

    print(f"开始生成关于「{topic}」的文献综述...\n")

    result = graph.invoke(initial_state)

    print("=" * 60)
    print(result["draft"])
    print("=" * 60)

    if result.get("issues"):
        print(f"\n审查问题（共 {len(result['issues'])} 个）:")
        for issue in result["issues"]:
            print(f"  - {issue}")

    print(f"\n论文数: {len(result['papers'])}")
    print(f"章节数: {len(result['outline'])}")
    print(f"重试次数: {result.get('retry_count', 0)}")


if __name__ == "__main__":
    main()
