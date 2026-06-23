"""PDF download and Docling parse."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import urlretrieve

from tools import _report

DOWNLOAD_DIR = Path("/tmp/searcher_papers")


def _download_single(url: str, idx: int) -> tuple[int, str | None]:
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
