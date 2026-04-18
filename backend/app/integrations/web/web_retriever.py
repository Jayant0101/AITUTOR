from __future__ import annotations

import logging
from typing import Any

from app.integrations.web.tavily_client import TavilyClient
from app.integrations.web.search_client import ZenserpSearchClient

logger = logging.getLogger(__name__)


def search_web(query: str, max_results: int = 8) -> list[dict[str, Any]]:
    """
    Search the web for the query.

    Priority order:
    1. Tavily API (if TAVILY_API_KEY is set)
    2. Zenserp API (if ZENSERP_API_KEY is set)
    3. Empty list (silent fail — caller handles no_data)

    Returns a list of dicts with keys: title, snippet, url.
    """
    # 1. Try Tavily
    tavily = TavilyClient()
    if tavily.api_key:
        results = tavily.search(query, max_results=max_results)
        if results:
            logger.info("[web_retriever] Tavily returned %d results.", len(results))
            return results
        logger.info("[web_retriever] Tavily returned 0 results — trying Zenserp.")

    # 2. Fall back to Zenserp
    try:
        client = ZenserpSearchClient()
        results = client.search(query, max_results=max_results)
        formatted = [
            {"title": r.title, "snippet": r.snippet, "url": r.url}
            for r in results
            if r.url
        ]
        if formatted:
            logger.info("[web_retriever] Zenserp returned %d results.", len(formatted))
        return formatted
    except Exception as exc:
        logger.warning("[web_retriever] Zenserp failed: %s", exc)
        raise RuntimeError("External search failed") from exc
