from __future__ import annotations

import html
import os
import re

import requests


def _clean_html_to_text(raw_html: str) -> str:
    # Strip scripts/styles first.
    cleaned = re.sub(
        r"<(script|style)[^>]*>.*?</\1>",
        " ",
        raw_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Remove the remaining tags.
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)

    # Normalize whitespace.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_content(url: str, *, max_chars: int | None = None) -> str:
    """
    Fetch a webpage and extract a plain-text approximation of its main content.

    This intentionally avoids heavy dependencies (e.g., readability-lxml) to keep
    the integration lightweight and research-friendly.
    """
    max_chars = max_chars or int(os.getenv("WEB_EXTRACT_MAX_CHARS", "6000"))
    timeout_s = float(os.getenv("WEB_EXTRACT_TIMEOUT_S", "15"))

    if not url:
        return ""

    try:
        resp = requests.get(
            url,
            timeout=timeout_s,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SocratiqBot/1.0)"},
        )
        if resp.status_code != 200:
            return ""
        text = _clean_html_to_text(resp.text)
    except Exception:
        return ""

    if not text:
        return ""

    # Heuristic: keep the densest part of the page to reduce boilerplate.
    # We approximate this by taking the longest segments (by char length).
    segments = [seg.strip() for seg in re.split(r"\.\s*|\n+", text) if seg.strip()]
    segments = [s for s in segments if len(s) >= 80]
    if segments:
        # Sort by length descending, take top N, preserve order by original position.
        # Since we lost positions, just join from top segments.
        segments_sorted = sorted(segments, key=len, reverse=True)[:6]
        text = " ".join(segments_sorted)

    return text[:max_chars]

