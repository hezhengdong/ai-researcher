"""Full pipeline test with mock papers (skips Searcher)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from agents.outliner import outliner
from agents.writer import writer
from agents.synthesizer import synthesizer
from agents.critic import critic

# Mock paper data - simulating what Searcher would produce
mock_papers = [
    {
        "id": "gfs",
        "title": "The Google File System",
        "markdown": """We have designed and implemented the Google File System, a scalable
distributed file system for large distributed data-intensive applications. It provides fault
tolerance while running on inexpensive commodity hardware, and it delivers high aggregate
performance to a large number of clients. GFS uses a single master to manage metadata while
chunkservers store data blocks. The system is optimized for Google's workloads: large files,
mostly appends, and high throughput. Unlike traditional file systems, GFS relaxes consistency
to achieve better performance.""",
        "source_type": "pdf",
    },
    {
        "id": "mapreduce",
        "title": "MapReduce: Simplified Data Processing on Large Clusters",
        "markdown": """MapReduce is a programming model and an associated implementation for
processing and generating large data sets. Users specify a map function that processes a
key/value pair to generate a set of intermediate key/value pairs, and a reduce function
that merges all intermediate values associated with the same intermediate key. The runtime
system automatically parallelizes execution across a cluster of machines, handles machine
failures, and schedules inter-machine communication. Programs written in this functional
style are automatically parallelized and executed on a large cluster of commodity machines.""",
        "source_type": "pdf",
    },
    {
        "id": "bigtable",
        "title": "Bigtable: A Distributed Storage System for Structured Data",
        "markdown": """Bigtable is a distributed storage system for managing structured data
that is designed to scale to a very large size: petabytes of data across thousands of
commodity servers. Bigtable provides a simple data model: a sparse, distributed, persistent
multi-dimensional sorted map. The map is indexed by a row key, column key, and a timestamp.
Bigtable is built on several other pieces of Google infrastructure: GFS for storing log
and data files, a cluster management system for scheduling, and Chubby for distributed
consensus and lock service.""",
        "source_type": "pdf",
    },
    {
        "id": "spanner",
        "title": "Spanner: Google's Globally-Distributed Database",
        "markdown": """Spanner is Google's scalable, multi-version, globally-distributed, and
synchronously-replicated database. It is the first system to distribute data at global
scale and support externally-consistent distributed transactions. Spanner uses TrueTime API,
which leverages atomic clocks and GPS to provide a globally consistent notion of time.
Spanner is built on top of Colossus (the successor to GFS) for storage, and uses Paxos
for consensus across replicas. The paper describes how Spanner evolves from Bigtable's
data model while adding SQL semantics and cross-data-center transactions.""",
        "source_type": "pdf",
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

# Step 1: Outliner
result = outliner(state)
state.update(result)

print()

# Step 2: Writer × K (simulate sequential for testing)
for i in range(len(state["outline"])):
    state["current_section_index"] = i
    result = writer(state)
    state["chapters"].extend(result["chapters"])

# Step 3: Synthesizer
result = synthesizer(state)
state.update(result)

# Step 4: Critic
result = critic(state)
state.update(result)

print(f"\n完成。章节: {len(state['outline'])}, 草稿: {len(state['draft'])} 字符, 问题: {len(state['issues'])}")
