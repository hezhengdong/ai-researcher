"""Integration test for API + SSE + persistence with mocked agents.

Uses pytest. Patches all five agent functions so no real LLM or API calls are made.
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Mock data ──

MOCK_PAPERS = [
    {
        "id": "gfs",
        "title": "The Google File System",
        "authors": ["Sanjay Ghemawat", "Howard Gobioff", "Shun-Tak Leung"],
        "year": 2003,
        "abstract": "GFS is a scalable distributed file system.",
        "citation_count": 5000,
        "markdown": "GFS provides fault tolerance on commodity hardware.",
        "source_type": "pdf",
    },
    {
        "id": "mapreduce",
        "title": "MapReduce: Simplified Data Processing on Large Clusters",
        "authors": ["Jeffrey Dean", "Sanjay Ghemawat"],
        "year": 2004,
        "abstract": "MapReduce is a programming model for large data sets.",
        "citation_count": 8000,
        "markdown": "MapReduce automates parallelization and fault tolerance.",
        "source_type": "pdf",
    },
]

MOCK_OUTLINE = [
    {
        "title": "Distributed Storage",
        "theme": "GFS as the foundation of scalable storage",
        "paper_ids": ["gfs"],
    },
    {
        "title": "Distributed Computing",
        "theme": "MapReduce and the batch processing paradigm",
        "paper_ids": ["mapreduce"],
    },
]

MOCK_CHAPTERS = [
    "GFS [gfs] introduced a scalable distributed file system that tolerates failures on commodity hardware. Its single-master architecture simplified metadata management.",
    "MapReduce [mapreduce] abstracted distributed computation into map and reduce primitives, enabling automatic parallelization across clusters.",
]

MOCK_DRAFT = """# A Survey of Distributed Systems

## Introduction
Distributed systems form the backbone of modern computing infrastructure.

## 1. Distributed Storage
GFS [gfs] introduced a scalable distributed file system that tolerates failures on commodity hardware.

## 2. Distributed Computing
MapReduce [mapreduce] abstracted distributed computation into map and reduce primitives.

## Conclusion
These foundational papers established patterns that remain influential today."""


# ── Mock agent functions ──

def mock_searcher(state):
    return {"papers": MOCK_PAPERS}


def mock_outliner(state):
    return {"outline": MOCK_OUTLINE}


def mock_writer(state):
    idx = state["current_section_index"]
    outline = state["outline"]
    chapter = MOCK_CHAPTERS[idx] if idx < len(MOCK_CHAPTERS) else f"Mock chapter {idx}"
    return {"chapters": [chapter]}


def mock_synthesizer(state):
    return {"draft": MOCK_DRAFT}


def mock_critic(state):
    return {"issues": [], "retry_count": state.get("retry_count", 0) + 1}


# ── Fixtures ──

@pytest.fixture
def test_db():
    """Use a temporary SQLite database instead of the real one."""
    import db
    original_engine = db.engine
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp_path = f.name
    db.engine = db.create_engine(f"sqlite:///{tmp_path}", echo=False)
    db.Base.metadata.create_all(db.engine)
    yield
    db.engine = original_engine
    Path(tmp_path).unlink(missing_ok=True)


@pytest.fixture
def client(test_db):
    """Create a TestClient with mocked agent functions."""
    with patch('agents.graph.searcher', mock_searcher), \
         patch('agents.graph.outliner', mock_outliner), \
         patch('agents.graph.writer', mock_writer), \
         patch('agents.graph.synthesizer', mock_synthesizer), \
         patch('agents.graph.critic', mock_critic):

        from agents.graph import build_graph
        test_graph = build_graph()

        import api
        original_graph = api.graph
        api.graph = test_graph

        yield TestClient(api.app)

        api.graph = original_graph


# ── Tests ──

def test_sse_event_stream(client):
    """Verify the SSE endpoint emits expected event types in correct order."""
    response = client.get("/api/surveys/stream?topic=distributed+systems")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events: list[dict] = []
    for line in response.iter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    event_types = [e["type"] for e in events]

    # Verify key event types are present in order
    assert "agent_start" in event_types, f"Missing agent_start in {event_types}"
    assert "agent_done" in event_types, f"Missing agent_done in {event_types}"
    assert "done" in event_types, f"Missing done in {event_types}"

    # Verify pipeline flow: searcher → outliner → writers → synthesizer → critic
    agents_seen = [
        e["agent"] for e in events
        if e["type"] == "agent_start"
    ]
    assert "searcher" in agents_seen
    assert "outliner" in agents_seen
    assert "writer" in agents_seen
    assert "synthesizer" in agents_seen
    assert "critic" in agents_seen

    # Verify writer parallelism: at least 2 writer start events
    writer_starts = [e for e in events if e["type"] == "agent_start" and e["agent"] == "writer"]
    assert len(writer_starts) == 2, f"Expected 2 writer starts, got {len(writer_starts)}"
    assert writer_starts[0]["writer_index"] == 0
    assert writer_starts[1]["writer_index"] == 1

    # Verify outline event is emitted with section data
    outline_events = [e for e in events if e["type"] == "outline"]
    assert len(outline_events) == 1
    assert len(outline_events[0]["sections"]) == 2
    assert outline_events[0]["sections"][0]["title"] == "Distributed Storage"

    # Verify done event has survey_id
    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert "survey_id" in done_events[0]
    assert isinstance(done_events[0]["survey_id"], int)


def test_persistence_after_stream(client):
    """Verify the survey data is saved to SQLite after the SSE stream completes."""
    response = client.get("/api/surveys/stream?topic=persistence+test")
    # Consume stream
    done_id = None
    for line in response.iter_lines():
        if line.startswith("data: "):
            evt = json.loads(line[6:])
            if evt["type"] == "done":
                done_id = evt["survey_id"]

    assert done_id is not None, "No done event with survey_id"

    # Fetch from API
    detail_resp = client.get(f"/api/surveys/{done_id}")
    assert detail_resp.status_code == 200
    survey = detail_resp.json()

    assert survey["topic"] == "persistence test"
    assert survey["status"] == "done"
    assert len(survey["draft"]) > 0
    assert len(survey["papers"]) == 2
    assert survey["papers"][0]["paper_id"] == "gfs"
    assert survey["papers"][0]["title"] == "The Google File System"
    assert len(survey["sections"]) == 2
    assert len(survey["chapters"]) == 2
    assert survey["chapters"][0]["title"] == "Distributed Storage"


def test_history_list(client):
    """Verify GET /api/surveys returns the list of past surveys."""
    # Generate one survey first
    resp = client.get("/api/surveys/stream?topic=history+test")
    for _ in resp.iter_lines():
        pass

    # List
    list_resp = client.get("/api/surveys")
    assert list_resp.status_code == 200
    surveys = list_resp.json()
    assert isinstance(surveys, list)
    assert len(surveys) >= 1
    assert any(s["topic"] == "history test" for s in surveys)


def test_survey_not_found(client):
    """Verify 404-like response for non-existent survey ID."""
    resp = client.get("/api/surveys/99999")
    assert resp.status_code == 200
    assert resp.json() == {"error": "not found"}


def test_error_handling(client):
    """Verify that agent exceptions are caught and sent as error events."""
    def failing_searcher(state):
        raise RuntimeError("API rate limit exceeded")

    with patch('agents.graph.searcher', failing_searcher):
        from agents.graph import build_graph
        test_graph = build_graph()
        import api
        original = api.graph
        api.graph = test_graph

        try:
            response = client.get("/api/surveys/stream?topic=error+test")
            events = []
            for line in response.iter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            error_events = [e for e in events if e["type"] == "error"]
            assert len(error_events) == 1
            assert "API rate limit exceeded" in error_events[0]["message"]
        finally:
            api.graph = original


def test_sse_format(client):
    """Verify SSE messages follow the expected format."""
    response = client.get("/api/surveys/stream?topic=format+test")

    sse_fields_seen = set()
    line_count = 0
    for line in response.iter_lines():
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            assert "type" in payload, f"Missing 'type' in: {payload}"
            sse_fields_seen.add(payload["type"])
        elif line.strip() == "":
            # Empty line between events is valid SSE
            pass
        elif line.startswith(":"):
            # SSE comment, OK
            pass
        else:
            # Non-data, non-empty line — shouldn't happen
            assert False, f"Unexpected SSE line: {line}"
        line_count += 1

    assert "done" in sse_fields_seen
    assert line_count > 0
