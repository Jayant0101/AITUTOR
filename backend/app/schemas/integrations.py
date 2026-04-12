from __future__ import annotations

from pydantic import BaseModel


class YouTubeSearchRequest(BaseModel):
    query: str


class YouTubeSearchResponse(BaseModel):
    title: str
    url: str
    channel: str
    snippet: str
