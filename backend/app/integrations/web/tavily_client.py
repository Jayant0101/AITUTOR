"""
Tavily Search Client
====================
Primary web-search fallback using the Tavily API (free tier: tavily.com).

Set ``TAVILY_API_KEY`` in your .env file.
If the key is missing or the request fails, an empty list is returned so the
system can fall back silently to Zenserp or return no_data.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"


class TavilyClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key or os.getenv("TAVILY_API_KEY", "")).strip()

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",  # "basic" or "advanced"
    ) -> list[dict[str, Any]]:
        """
        Search using Tavily API.
        Returns list of dicts with keys: title, url, snippet.
        """
        if not self.api_key:
            logger.debug("[tavily] No TAVILY_API_KEY set — skipping.")
            return []

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": False,
            "include_raw_content": False,
        }
        
        # Phase 5: Performance Safety - Retry once + 10s timeout
        max_retries = 1
        last_exc = None
        
        for attempt in range(max_retries + 1):
            try:
                resp = requests.post(_TAVILY_URL, json=payload, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                
                results = []
                for item in data.get("results", [])[:max_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("content", ""),
                        "url": item.get("url", ""),
                    })
                return results
            except Exception as exc:
                last_exc = exc
                logger.warning(f"[tavily] Search attempt {attempt + 1} failed: {exc}")
                if attempt < max_retries:
                    import time
                    time.sleep(1) # short backoff
                    continue
        
        raise RuntimeError(f"Tavily search failed after {max_retries + 1} attempts: {last_exc}")
