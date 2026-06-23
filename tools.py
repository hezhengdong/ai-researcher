"""Tools for Searcher agent: web search, page extraction, PDF download and parse."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import urlretrieve

from tavily import TavilyClient

DOWNLOAD_DIR = Path("/tmp/searcher_papers")


def tavily_search(query: str, max_results: int = 5) -> str:
    """Search the web for a reading list of classic papers on a topic."""
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = client.search(query, max_results=max_results, search_depth="advanced")
    results = response.get("results", [])
    if not results:
        print(f"      [Tavily] 无结果: {query}", flush=True)
        return "No results found."
    print(f"      [Tavily] {query}", flush=True)
    for r in results:
        print(f"        → {r['title'][:80]}  {r['url'][:60]}", flush=True)
    return "\n\n".join(
        f"Title: {r['title']}\nURL: {r['url']}\nContent: {r.get('content', '')}"
        for r in results
    )


def tavily_extract(url: str) -> str:
    """Extract the full content of a web page given its URL. Use this to read reading list pages."""
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = client.extract(urls=url)
    results = response.get("results", [])
    if results:
        content = results[0].get("raw_content", "")
        print(f"      [Tavily Extract] {url[:60]} → {len(content)} 字符", flush=True)
        return content
    failed = response.get("failed_results", [])
    error = failed[0].get("error", "unknown") if failed else "no results"
    print(f"      [Tavily Extract] 失败: {url[:60]} ({error})", flush=True)
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

    # 阶段一：并行下载
    print(f"  [批量下载] 并行下载 {len(pdf_urls)} 篇 PDF...", flush=True)
    downloaded = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_download_single, url, i): i for i, url in enumerate(pdf_urls) if url}
        for f in as_completed(futures):
            idx, path = f.result()
            if path:
                downloaded[idx] = path
                print(f"    [{idx+1}/{len(pdf_urls)}] 下载成功: {pdf_urls[idx][:60]}", flush=True)
            else:
                print(f"    [{idx+1}/{len(pdf_urls)}] 下载失败: {pdf_urls[idx][:60]}", flush=True)

    if not downloaded:
        return results

    # 阶段二：Docling v2 convert_all 批量解析
    # CS 论文都是数字原生 PDF，不需要 OCR
    # RapidOCR 只支持 CPU，开 OCR 会白白消耗大量时间
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

        for idx, result in zip(sorted_indices, conv_results):
            if result.status.name == "SUCCESS":
                md = result.document.export_to_markdown()
                results[idx] = {"markdown": md, "source_type": "pdf"}
                print(f"    [{idx+1}/{len(pdf_urls)}] 解析完成: {len(md)} 字符", flush=True)
            else:
                print(f"    [{idx+1}/{len(pdf_urls)}] 解析失败: {result.status}", flush=True)
    except Exception as e:
        print(f"  [批量解析] convert_all 失败: {e}", flush=True)

    return results
