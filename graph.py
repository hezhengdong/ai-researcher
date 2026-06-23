"""LangGraph graph construction for the survey generation pipeline."""

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agents.critic import critic
from agents.outliner import outliner
from agents.searcher import searcher
from agents.synthesizer import synthesizer
from agents.writer import writer
from state import State

MAX_RETRIES = 3


def _fanout_writers(state: State) -> list[Send]:
    """After outlining, create one Send per section for parallel writer execution."""
    return [
        Send("writer", {
            "current_section_index": i,
            "outline": state["outline"],
            "papers": state["papers"],
        })
        for i in range(len(state["outline"]))
    ]


def _after_critic(state: State) -> str:
    """Decide whether to retry synthesis or finish."""
    if state.get("issues") and state.get("retry_count", 0) < MAX_RETRIES:
        return "synthesizer"
    return "end"


def build_graph() -> StateGraph:
    builder = StateGraph(State)

    builder.add_node("searcher", searcher)
    builder.add_node("outliner", outliner)
    builder.add_node("writer", writer)
    builder.add_node("synthesizer", synthesizer)
    builder.add_node("critic", critic)

    builder.add_edge(START, "searcher")
    builder.add_edge("searcher", "outliner")
    builder.add_conditional_edges("outliner", _fanout_writers)
    builder.add_edge("writer", "synthesizer")
    builder.add_edge("synthesizer", "critic")
    builder.add_conditional_edges("critic", _after_critic, {
        "synthesizer": "synthesizer",
        "end": END,
    })

    return builder.compile()


graph = build_graph()
