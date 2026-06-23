"""FastAPI server with SSE streaming for the survey generation pipeline."""

import asyncio
import json
import os
import queue
import threading

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from db import create_survey, get_survey, list_surveys, update_survey_done
from graph import graph
from latex import generate_pdf
from state import State
from tools import set_progress_reporter

load_dotenv()

app = FastAPI()

AGENT_NAMES = {"searcher", "outliner", "writer", "synthesizer", "critic"}


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/surveys/stream")
async def generate_survey(topic: str = Query(..., description="Research topic to survey")):
    """Generate a literature survey via SSE streaming. Synchronous (one request = one pipeline run)."""

    async def event_stream():
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

        accumulated: dict = {
            "papers": [],
            "outline": [],
            "chapters": [],
            "draft": "",
            "issues": [],
            "retry_count": 0,
        }

        survey_id = create_survey(topic)

        writer_node_runs: dict[str, int] = {}
        chat_to_writer: dict[str, str] = {}
        paper_map: dict[str, dict] = {}

        # 线程安全队列，tools 通过 set_progress_reporter 回调写入
        progress_q: queue.Queue = queue.Queue()
        set_progress_reporter(lambda evt: progress_q.put(evt))

        def drain_progress():
            """非阻塞地取出队列中所有进度事件。"""
            items = []
            while True:
                try:
                    items.append(progress_q.get_nowait())
                except queue.Empty:
                    break
            return items

        async def send_progress():
            """将队列中的进度事件转为 SSE。"""
            for evt in drain_progress():
                yield _sse(evt)

        try:
            # 统一事件总线：两股流（graph events + progress events）并发写入同一 Queue
            event_q: asyncio.Queue = asyncio.Queue()

            async def graph_producer():
                async for event in graph.astream_events(initial_state, version="v2"):
                    await event_q.put(("graph", event))
                await event_q.put(("graph_eof", None))

            async def progress_producer():
                while True:
                    try:
                        while True:
                            evt = progress_q.get_nowait()
                            await event_q.put(("progress", evt))
                    except queue.Empty:
                        pass
                    await asyncio.sleep(0.3)

            graph_task = asyncio.create_task(graph_producer())
            prog_task = asyncio.create_task(progress_producer())

            graph_done = False
            while not graph_done:
                # 检查 graph_producer 是否异常退出
                if graph_task.done():
                    exc = graph_task.exception()
                    if exc:
                        raise exc

                try:
                    source, data = await asyncio.wait_for(event_q.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                if source == "graph_eof":
                    graph_done = True
                    continue

                if source == "progress":
                    evt = data
                    yield _sse(evt)
                    continue

                # source == "graph": process graph event
                event = data
                evt_type = event["event"]
                name = event.get("name", "")
                meta = event.get("metadata", {})
                node = meta.get("langgraph_node", "")
                run_id = event["run_id"]
                parent_run_id = event.get("parent_run_id", "")

                # --- Agent start ---
                if evt_type == "on_chain_start" and name in AGENT_NAMES:
                    if name == "writer":
                        inp = event["data"].get("input", {})
                        idx = inp.get("current_section_index", 0)
                        writer_node_runs[run_id] = idx
                        section = (inp.get("outline", []) or [])[idx] if idx < len(inp.get("outline", [])) else {}
                        assigned = [
                            paper_map.get(pid, {}).get("title", pid)
                            for pid in section.get("paper_ids", [])
                        ]
                        yield _sse({
                            "type": "agent_start", "agent": "writer", "writer_index": idx,
                            "chapter_title": section.get("title", ""),
                            "theme": section.get("theme", ""),
                            "assigned_papers": assigned,
                        })
                    elif name == "outliner":
                        inp_data = event["data"].get("input", {})
                        papers_in = inp_data.get("papers", accumulated["papers"])
                        titles = [p.get("title", "") for p in papers_in]
                        yield _sse({
                            "type": "agent_start", "agent": "outliner",
                            "paper_count": len(papers_in), "paper_titles": titles,
                        })
                    elif name == "synthesizer":
                        ch_count = len(accumulated.get("chapters", []))
                        outline = accumulated.get("outline", [])
                        ch_titles = [s.get("title", "") for s in outline]
                        is_retry = bool(accumulated.get("issues"))
                        yield _sse({
                            "type": "agent_start", "agent": "synthesizer",
                            "chapter_count": ch_count, "chapter_titles": ch_titles,
                            "is_retry": is_retry,
                        })
                    else:
                        yield _sse({"type": "agent_start", "agent": name})

                # --- LLM token ---
                elif evt_type == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    content = chunk.content if hasattr(chunk, "content") else ""
                    reasoning = ""
                    if hasattr(chunk, "additional_kwargs") and chunk.additional_kwargs:
                        reasoning = chunk.additional_kwargs.get("reasoning_content", "") or ""

                    if reasoning:
                        p = {"type": "thinking", "content": reasoning}
                        if node == "writer":
                            p["agent"] = "writer"
                            p["writer_index"] = writer_node_runs.get(chat_to_writer.get(parent_run_id, ""))
                        else:
                            p["agent"] = node
                        yield _sse(p)

                    if content:
                        p = {"type": "token", "content": content}
                        if node == "writer":
                            p["agent"] = "writer"
                            p["writer_index"] = writer_node_runs.get(chat_to_writer.get(parent_run_id, ""))
                        else:
                            p["agent"] = node
                        yield _sse(p)

                # --- Chat model start ---
                elif evt_type == "on_chat_model_start":
                    if parent_run_id in writer_node_runs:
                        chat_to_writer[run_id] = parent_run_id

                # --- Agent done ---
                elif evt_type == "on_chain_end" and name in AGENT_NAMES:
                    output = event["data"].get("output", {})
                    if name == "searcher":
                        accumulated["papers"] = output.get("papers", [])
                        paper_map = {p["id"]: p for p in accumulated["papers"]}
                        ps = [{"id": p["id"], "title": p["title"], "source_type": p.get("source_type", "none"), "chars": len(p.get("markdown", "") or "")} for p in accumulated["papers"]]
                        yield _sse({"type": "agent_done", "agent": "searcher", "paper_count": len(accumulated["papers"]), "papers": ps})
                    elif name == "outliner":
                        accumulated["outline"] = output.get("outline", [])
                        secs = [{"title": s["title"], "theme": s.get("theme", ""), "paper_ids": s.get("paper_ids", [])} for s in accumulated["outline"]]
                        yield _sse({"type": "outline", "sections": secs})
                        yield _sse({"type": "agent_done", "agent": "outliner"})
                    elif name == "writer":
                        chapters = output.get("chapters", [])
                        accumulated["chapters"].extend(chapters)
                        w_idx = writer_node_runs.get(run_id, 0)
                        yield _sse({"type": "agent_done", "agent": "writer", "writer_index": w_idx})
                    elif name == "synthesizer":
                        accumulated["draft"] = output.get("draft", "")
                        yield _sse({"type": "agent_done", "agent": "synthesizer"})
                    elif name == "critic":
                        accumulated["issues"] = output.get("issues", [])
                        accumulated["retry_count"] = output.get("retry_count", 0)
                        yield _sse({"type": "agent_done", "agent": "critic", "issues": accumulated["issues"]})

            # 排空 graph 完成后残留的 progress 事件
            while not event_q.empty():
                source, data = event_q.get_nowait()
                if source == "progress":
                    yield _sse(data)

            prog_task.cancel()
            try:
                await prog_task
            except asyncio.CancelledError:
                pass

            update_survey_done(survey_id, accumulated)

            # LaTeX PDF（非关键，失败不阻塞）
            pdf_path = None
            try:
                pdf_path = await asyncio.to_thread(
                    generate_pdf, survey_id, accumulated["draft"], topic
                )
            except Exception:
                pass

            yield _sse({"type": "done", "survey_id": survey_id, "has_pdf": bool(pdf_path)})

        except Exception as e:
            yield _sse({"type": "error", "message": str(e)})
        finally:
            set_progress_reporter(None)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/surveys")
async def get_surveys():
    """List all past surveys."""
    return list_surveys()


@app.get("/api/surveys/{survey_id}")
async def get_survey_detail(survey_id: int):
    """Get a single survey with all papers, sections, and chapters."""
    result = get_survey(survey_id)
    if result is None:
        return {"error": "not found"}
    return result


@app.get("/api/surveys/{survey_id}/pdf")
async def get_survey_pdf(survey_id: int):
    """Download the LaTeX-generated PDF for a survey."""
    import os
    pdf_path = os.path.join(os.path.dirname(__file__), "output", f"survey_{survey_id}.pdf")
    if not os.path.isfile(pdf_path):
        raise HTTPException(404, "PDF not available")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"survey_{survey_id}.pdf")


# Serve static frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
