from __future__ import annotations

import requests
from typing import Any


class YouTubeSearchClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def search(self, query: str, max_results: int = 1) -> list[dict[str, Any]]:
        if not self.api_key:
            return []

        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "key": self.api_key,
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            return []

        results: list[dict[str, Any]] = []
        for item in payload.get("items", []):
            video_id = item.get("id", {}).get("videoId", "")
            snippet = item.get("snippet", {})
            if not video_id:
                continue
            results.append(
                {
                    "title": snippet.get("title", ""),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "channel": snippet.get("channelTitle", ""),
                    "snippet": snippet.get("description", ""),
                    "query": query,
                }
            )
        return results
