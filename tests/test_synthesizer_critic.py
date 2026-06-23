"""Quick test for Synthesizer + Critic with mock chapter data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from agents.critic import critic
from agents.synthesizer import synthesizer

load_dotenv()

mock_papers = [
    {
        "id": "gfs",
        "title": "The Google File System",
        "authors": ["Sanjay Ghemawat", "Howard Gobioff", "Shun-Tak Leung"],
        "year": 2003,
        "abstract": "GFS is a scalable distributed file system.",
    },
    {
        "id": "mapreduce",
        "title": "MapReduce: Simplified Data Processing on Large Clusters",
        "authors": ["Jeffrey Dean", "Sanjay Ghemawat"],
        "year": 2004,
        "abstract": "MapReduce is a programming model for large data sets.",
    },
    {
        "id": "bigtable",
        "title": "Bigtable: A Distributed Storage System for Structured Data",
        "authors": ["Fay Chang", "Jeffrey Dean", "et al."],
        "year": 2006,
        "abstract": "Bigtable is a distributed storage system.",
    },
    {
        "id": "paxos",
        "title": "Paxos Made Simple",
        "authors": ["Leslie Lamport"],
        "year": 2001,
        "abstract": "The Paxos algorithm explained in plain English.",
    },
    {
        "id": "raft",
        "title": "In Search of an Understandable Consensus Algorithm",
        "authors": ["Diego Ongaro", "John Ousterhout"],
        "year": 2014,
        "abstract": "Raft is a consensus algorithm designed for understandability.",
    },
    {
        "id": "spanner",
        "title": "Spanner: Google's Globally-Distributed Database",
        "authors": ["James C. Corbett", "Jeffrey Dean", "et al."],
        "year": 2012,
        "abstract": "Spanner is a globally-distributed database.",
    },
]

mock_outline = [
    {
        "title": "分布式共识算法",
        "theme": "从理论奠基到工程可理解性：Paxos 和 Raft",
        "paper_ids": ["paxos", "raft"],
    },
    {
        "title": "分布式存储基础设施",
        "theme": "GFS 文件系统、Bigtable 结构化存储与 Spanner 全局数据库",
        "paper_ids": ["gfs", "bigtable", "spanner"],
    },
    {
        "title": "分布式计算模型",
        "theme": "MapReduce 开创的批处理模型及其影响",
        "paper_ids": ["mapreduce"],
    },
]

# Simulated writer outputs (abbreviated)
mock_chapters = [
    (
        "在分布式系统中，共识算法是构建高可用服务的基础。Leslie Lamport 提出的 Paxos 算法 "
        "[paxos] 通过两阶段提交确保了安全性，但其复杂性催生了 Raft [raft] 的设计。Raft "
        "将共识分解为领导者选举、日志复制和安全保证三个独立部分，在提供与 Paxos 等价 "
        "容错性的同时大幅提升了可理解性。从 Paxos 到 Raft 的演进，反映了分布式系统社区 "
        "从追求理论严谨到重视工程实践的价值转向。"
    ),
    (
        "现代分布式存储经历了从文件系统到结构化存储再到全局数据库的演进。GFS [gfs] "
        "作为奠基之作，通过单主控 + 多 chunkserver 的架构在廉价硬件上实现了容错和吞吐。"
        "在此基础上，Bigtable [bigtable] 提供了多维排序的结构化存储抽象，而 Spanner "
        "[spanner] 更进一步，利用 TrueTime API 和 Paxos 共识实现了跨数据中心的 "
        "外部一致性分布式事务。这三者的演进清晰地展示了 Google 基础设施的迭代路径："
        "从非结构化到结构化，从单数据中心到全球分布。"
    ),
    (
        "MapReduce [mapreduce] 提出了一种简洁而强大的批处理范式。通过将计算抽象为 "
        "Map 和 Reduce 两个阶段，开发者无需关心并行化、容错和负载均衡等底层细节。"
        "尽管其后涌现了 Spark、FlumeJava 等更高效的框架，MapReduce 的核心思想 "
        "——将分布式计算简化为函数式编程原语——至今仍是分布式计算教育的基础。"
    ),
]

state = {
    "topic": "分布式系统",
    "papers": mock_papers,
    "outline": mock_outline,
    "current_section_index": -1,
    "chapters": mock_chapters,
    "draft": "",
    "issues": [],
    "retry_count": 0,
}

# Step 1: Synthesizer
print("=== Synthesizer (first pass) ===")
result = synthesizer(state)
draft = result["draft"]
print(draft[:600])
if len(draft) > 600:
    print(f"\n... (共 {len(draft)} 字符)")
print()

# Step 2: Critic
print("=== Critic ===")
state["draft"] = draft
state["issues"] = []
result = critic(state)
issues = result["issues"]
if issues:
    for issue in issues:
        print(f"  - {issue}")
else:
    print("  通过，没有问题")
print()

# Step 3: Synthesizer retry (if issues)
if issues and result["retry_count"] < 3:
    print("=== Synthesizer (retry with issues) ===")
    state["issues"] = issues
    state["retry_count"] = result["retry_count"]
    result = synthesizer(state)
    revised = result["draft"]
    print(revised[:400])
    if len(revised) > 400:
        print(f"\n... (共 {len(revised)} 字符)")
