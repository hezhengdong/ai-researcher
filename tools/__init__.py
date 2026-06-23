"""Tools for Searcher agent: web search, page extraction, PDF download and parse."""

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


from tools.pdf import batch_download_and_parse  # noqa: E402
from tools.search import tavily_extract, tavily_search  # noqa: E402
