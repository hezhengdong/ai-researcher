"""Tavily web search and page extraction tools."""

import os

from tavily import TavilyClient

from tools import _report


def tavily_search(query: str, max_results: int = 5) -> str:
    """Search the web for a reading list of classic papers on a topic."""
    _report("tool_start", tool="tavily_search", query=query)
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = client.search(query, max_results=max_results, search_depth="advanced")
    results = response.get("results", [])
    if not results:
        print(f"      [Tavily] 无结果: {query}", flush=True)
        _report("tool_result", tool="tavily_search", summary="无结果")
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
    """Extract the full content of a web page given its URL."""
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
