"""Quick test for Outliner agent with mock paper data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from agents.outliner import outliner

load_dotenv()

mock_papers = [
    {
        "id": "gfs",
        "title": "The Google File System",
        "authors": ["Sanjay Ghemawat", "Howard Gobioff", "Shun-Tak Leung"],
        "year": 2003,
        "abstract": "We have designed and implemented the Google File System, a scalable distributed file system for large distributed data-intensive applications. It provides fault tolerance while running on inexpensive commodity hardware, and it delivers high aggregate performance to a large number of clients.",
        "citation_count": 5000,
        "markdown": "",
        "source_type": "none",
    },
    {
        "id": "mapreduce",
        "title": "MapReduce: Simplified Data Processing on Large Clusters",
        "authors": ["Jeffrey Dean", "Sanjay Ghemawat"],
        "year": 2004,
        "abstract": "MapReduce is a programming model and an associated implementation for processing and generating large data sets. Users specify a map function that processes a key/value pair to generate a set of intermediate key/value pairs, and a reduce function that merges all intermediate values associated with the same intermediate key.",
        "citation_count": 8000,
        "markdown": "",
        "source_type": "none",
    },
    {
        "id": "bigtable",
        "title": "Bigtable: A Distributed Storage System for Structured Data",
        "authors": ["Fay Chang", "Jeffrey Dean", "Sanjay Ghemawat", "et al."],
        "year": 2006,
        "abstract": "Bigtable is a distributed storage system for managing structured data that is designed to scale to a very large size: petabytes of data across thousands of commodity servers. Bigtable is used by many Google projects including Google Earth and Google Finance.",
        "citation_count": 4500,
        "markdown": "",
        "source_type": "none",
    },
    {
        "id": "paxos",
        "title": "Paxos Made Simple",
        "authors": ["Leslie Lamport"],
        "year": 2001,
        "abstract": "The Paxos algorithm, when presented in plain English, is very simple. This paper explains the algorithm clearly.",
        "citation_count": 3000,
        "markdown": "",
        "source_type": "none",
    },
    {
        "id": "raft",
        "title": "In Search of an Understandable Consensus Algorithm",
        "authors": ["Diego Ongaro", "John Ousterhout"],
        "year": 2014,
        "abstract": "Raft is a consensus algorithm that is designed to be easy to understand. It's equivalent to Paxos in fault-tolerance and performance. Raft separates the key elements of consensus, such as leader election, log replication, and safety.",
        "citation_count": 3500,
        "markdown": "",
        "source_type": "none",
    },
    {
        "id": "spanner",
        "title": "Spanner: Google's Globally-Distributed Database",
        "authors": ["James C. Corbett", "Jeffrey Dean", "et al."],
        "year": 2012,
        "abstract": "Spanner is Google's scalable, multi-version, globally-distributed, and synchronously-replicated database. It is the first system to distribute data at global scale and support externally-consistent distributed transactions.",
        "citation_count": 2800,
        "markdown": "",
        "source_type": "none",
    },
]

state = {
    "topic": "分布式系统",
    "papers": mock_papers,
    "outline": [],
    "current_section_index": -1,
    "chapters": [],
    "draft": "",
    "issues": [],
    "retry_count": 0,
}

print("Testing Outliner with 6 distributed systems papers...\n")
result = outliner(state)

print("Outline sections:")
for i, sec in enumerate(result["outline"]):
    print(f"  {i+1}. {sec['title']}")
    print(f"     Theme: {sec['theme']}")
    print(f"     Papers: {sec['paper_ids']}")
    print()
