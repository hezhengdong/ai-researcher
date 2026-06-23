"""Quick test for Writer agent with mock data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from agents.writer import writer

load_dotenv()

mock_papers = [
    {
        "id": "gfs",
        "title": "The Google File System",
        "authors": ["Sanjay Ghemawat", "Howard Gobioff", "Shun-Tak Leung"],
        "year": 2003,
        "abstract": "GFS is a scalable distributed file system for large distributed data-intensive applications.",
        "citation_count": 5000,
        "markdown": "GFS provides fault tolerance while running on inexpensive commodity hardware. Unlike traditional file systems, GFS is optimized for Google's workloads: large files, mostly appends, and high throughput. A single master manages metadata while chunkservers store data blocks.",
        "source_type": "none",
    },
    {
        "id": "mapreduce",
        "title": "MapReduce: Simplified Data Processing on Large Clusters",
        "authors": ["Jeffrey Dean", "Sanjay Ghemawat"],
        "year": 2004,
        "abstract": "MapReduce is a programming model for processing large data sets.",
        "citation_count": 8000,
        "markdown": "Users specify a map function and a reduce function. The system automatically parallelizes execution across a cluster. MapReduce handles fault tolerance by re-executing failed tasks.",
        "source_type": "none",
    },
    {
        "id": "bigtable",
        "title": "Bigtable: A Distributed Storage System for Structured Data",
        "authors": ["Fay Chang", "Jeffrey Dean", "et al."],
        "year": 2006,
        "abstract": "Bigtable is a distributed storage system for structured data at petabyte scale.",
        "citation_count": 4500,
        "markdown": "Bigtable provides a sparse, distributed, persistent multi-dimensional sorted map. It is used by many Google projects. Data is organized by row, column, and timestamp. Built on GFS for storage and Chubby for coordination.",
        "source_type": "none",
    },
    {
        "id": "paxos",
        "title": "Paxos Made Simple",
        "authors": ["Leslie Lamport"],
        "year": 2001,
        "abstract": "The Paxos algorithm explained in plain English.",
        "citation_count": 3000,
        "markdown": "Paxos is a consensus algorithm for asynchronous systems. It consists of three roles: proposers, acceptors, and learners. A value is chosen when a majority of acceptors accept it. Despite its theoretical clarity, Paxos is known to be difficult to implement correctly in practice.",
        "source_type": "none",
    },
    {
        "id": "raft",
        "title": "In Search of an Understandable Consensus Algorithm",
        "authors": ["Diego Ongaro", "John Ousterhout"],
        "year": 2014,
        "abstract": "Raft is a consensus algorithm designed to be easy to understand.",
        "citation_count": 3500,
        "markdown": "Raft decomposes consensus into leader election, log replication, and safety. It uses a strong leader model where all log entries flow from leader to followers. Raft is equivalent to Paxos in fault-tolerance but designed for understandability, making it easier to implement correctly.",
        "source_type": "none",
    },
    {
        "id": "spanner",
        "title": "Spanner: Google's Globally-Distributed Database",
        "authors": ["James C. Corbett", "Jeffrey Dean", "et al."],
        "year": 2012,
        "abstract": "Spanner is Google's globally-distributed, synchronously-replicated database.",
        "citation_count": 2800,
        "markdown": "Spanner uses TrueTime API with atomic clocks and GPS to provide external consistency. It supports distributed transactions across data centers. Spanner is built on top of Colossus (GFS successor), Bigtable, and a Paxos-based consensus layer.",
        "source_type": "none",
    },
]

# Use the outline produced by Outliner in the previous test
mock_outline = [
    {
        "title": "分布式共识算法",
        "theme": "从理论奠基到工程可理解性：Paxos 和 Raft",
        "paper_ids": ["paxos", "raft"],
    },
    {
        "title": "分布式文件系统",
        "theme": "GFS 作为大规模分布式文件系统的奠基之作",
        "paper_ids": ["gfs"],
    },
    {
        "title": "分布式计算与存储",
        "theme": "MapReduce 计算模型和 Bigtable 存储系统的演进",
        "paper_ids": ["mapreduce", "bigtable"],
    },
    {
        "title": "全局分布式数据库",
        "theme": "Spanner 如何实现全球分布和外部一致性",
        "paper_ids": ["spanner"],
    },
]

state = {
    "topic": "分布式系统",
    "papers": mock_papers,
    "outline": mock_outline,
    "current_section_index": 0,  # Test first section: consensus algorithms
    "chapters": [],
    "draft": "",
    "issues": [],
    "retry_count": 0,
}

print("Testing Writer for chapter 1: 分布式共识算法...\n")
result = writer(state)

chapter = result["chapters"][0]
print(chapter[:500])
if len(chapter) > 500:
    print(f"\n... (共 {len(chapter)} 字符)")
