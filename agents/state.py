"""Shared state schema for the LangGraph survey generation pipeline."""

import operator
from typing import Annotated, TypedDict


class OutlineSection(TypedDict):
    title: str
    theme: str
    paper_ids: list[str]


class State(TypedDict):
    topic: str
    papers: list[dict]
    outline: list[OutlineSection]
    current_section_index: int  # set by Send when fanning out to writers
    chapters: Annotated[list[str], operator.add]
    draft: str
    issues: list[str]
    retry_count: int
