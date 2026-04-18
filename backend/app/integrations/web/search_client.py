from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    snippet: str
    url: str


class ZenserpSearchClient:
    """
    Minimal Zenserp SERP client.

    Config:
    - ZENSERP_API_KEY (required for live calls)
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("ZENSERP_API_KEY", "").strip()
        self.endpoint = "https://app.zenserp.com/api/v2/search"

    def search(
        self, query: str, *, max_results: int = 10, engine: str = "google"
    ) -> list[WebSearchResult]:
        if not self.api_key:
            return []

        params: dict[str, Any] = {
            "q": query,
            "engine": engine,
        }

        headers = {"apikey": self.api_key}
        try:
            resp = requests.get(
                self.endpoint,
                headers=headers,
                params=params,
                timeout=20,
            )
            if resp.status_code != 200:
                return []
            payload = resp.json()
        except Exception:
            return []

        organic = payload.get("organic") or []
        out: list[WebSearchResult] = []
        for item in organic:
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or item.get("destination") or "").strip()
            snippet = str(item.get("description") or item.get("snippet") or "").strip()
            if not title or not url:
                continue
            out.append(WebSearchResult(title=title, snippet=snippet, url=url))
            if len(out) >= max_results:
                break
        return out

