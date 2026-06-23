"""Tools for Searcher agent: web search, page extraction, PDF download and parse."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import urlretrieve

from tavily import TavilyClient

DOWNLOAD_DIR = Path("/tmp/searcher_papers")

# 全局进度回调，供 SSE 流式推送使用
_progress_reporter = None


def set_progress_reporter(fn):
    global _progress_reporter
    _progress_reporter = fn


def _report(event_type: str, **kwargs):
    if _progress_reporter:
        try:
            _progress_reporter({"type": event_type, **kwargs})
        except Exception:
            pass


def tavily_search(query: str, max_results: int = 5) -> str:
    """Search the web for a reading list of classic papers on a topic."""
    _report("tool_start", tool="tavily_search", query=query)
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = client.search(query, max_results=max_results, search_depth="advanced")
    results = response.get("results", [])
    if not results:
        print(f"      [Tavily] 无结果: {query}", flush=True)
        _report("tool_result", tool="tavily_search", summary=f"无结果")
        return "No results found."
    print(f"      [Tavily] {query}", flush=True)
    summaries = []
    for r in results:
        line = f"{r['title'][:80]}  {r['url'][:60]}"
        print(f"        → {line}", flush=True)
        summaries.append(line)
    _report("tool_result", tool="tavily_search", summary=f"{len(results)} 条结果", items=summaries)
    return "\n\n".join(
        f"Title: {r['title']}\nURL: {r['url']}\nContent: {r.get('content', '')}"
        for r in results
    )


def tavily_extract(url: str) -> str:
    """Extract the full content of a web page given its URL. Use this to read reading list pages."""
    _report("tool_start", tool="tavily_extract", url=url[:80])
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = client.extract(urls=url)
    results = response.get("results", [])
    if results:
        content = results[0].get("raw_content", "")
        print(f"      [Tavily Extract] {url[:60]} → {len(content)} 字符", flush=True)
        _report("tool_result", tool="tavily_extract", summary=f"{len(content)} 字符")
        return content
    failed = response.get("failed_results", [])
    error = failed[0].get("error", "unknown") if failed else "no results"
    print(f"      [Tavily Extract] 失败: {url[:60]} ({error})", flush=True)
    _report("tool_result", tool="tavily_extract", summary=f"失败: {error}")
    return f"Failed to extract {url}: {error}"


def _download_single(url: str, idx: int) -> tuple[int, str | None]:
    """下载单个 PDF 到本地，返回 (idx, path_or_None)。"""
    import socket
    try:
        path = DOWNLOAD_DIR / f"paper_{idx:02d}.pdf"
        socket.setdefaulttimeout(30)
        urlretrieve(url, str(path))
        with open(path, "rb") as f:
            if f.read(4) != b"%PDF":
                path.unlink(missing_ok=True)
                return idx, None
        return idx, str(path)
    except Exception as e:
        print(f"    [{idx+1}] 下载异常: {e}", flush=True)
        return idx, None


def batch_download_and_parse(pdf_urls: list[str]) -> list[dict]:
    """并行下载 PDF，批量解析。返回 [{markdown, source_type}]，与输入顺序一致。"""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    results = [{"markdown": "", "source_type": "none"} for _ in pdf_urls]
    total = len(pdf_urls)
    _report("pdf_start", total=total)

    # 阶段一：并行下载
    print(f"  [批量下载] 并行下载 {total} 篇 PDF...", flush=True)
    downloaded = {}
    done_dl = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_download_single, url, i): i for i, url in enumerate(pdf_urls) if url}
        for f in as_completed(futures):
            idx, path = f.result()
            done_dl += 1
            if path:
                downloaded[idx] = path
                print(f"    [{idx+1}/{total}] 下载成功: {pdf_urls[idx][:60]}", flush=True)
            else:
                print(f"    [{idx+1}/{total}] 下载失败: {pdf_urls[idx][:60]}", flush=True)
            _report("pdf_download_progress", done=done_dl, total=total)

    if not downloaded:
        _report("pdf_done", results=[])
        return results

    # 阶段二：Docling v2 convert_all 批量解析
    print(f"  [批量解析] 使用 Docling convert_all 解析 {len(downloaded)} 篇...", flush=True)
    try:
        sorted_indices = sorted(downloaded.keys())
        paths = [str(downloaded[i]) for i in sorted_indices]

        import torch
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice

        accelerator = AcceleratorOptions(device=AcceleratorDevice.MPS, num_threads=1)
        pipeline = PdfPipelineOptions(
            accelerator_options=accelerator,
            do_ocr=False,
        )
        converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline)}
        )
        conv_results = converter.convert_all(paths, raises_on_error=False)

        for parse_done, (idx, conv_result) in enumerate(zip(sorted_indices, conv_results), 1):
            if conv_result.status.name == "SUCCESS":
                md = conv_result.document.export_to_markdown()
                results[idx] = {"markdown": md, "source_type": "pdf"}
                print(f"    [{idx+1}/{total}] 解析完成: {len(md)} 字符", flush=True)
            else:
                print(f"    [{idx+1}/{total}] 解析失败: {conv_result.status}", flush=True)
            _report("pdf_parse_progress", done=parse_done, total=total)
    except Exception as e:
        print(f"  [批量解析] convert_all 失败: {e}", flush=True)

    _report("pdf_done", results=[
        {"title": f"paper_{i:02d}", "success": r["source_type"] == "pdf",
         "chars": len(r["markdown"]) if r["markdown"] else 0}
        for i, r in enumerate(results)
    ])
    return results
