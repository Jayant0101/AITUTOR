from __future__ import annotations

import logging
import os
import re
from typing import Any

from app.verification.verification import verify_content
from app.integrations.web.content_extractor import extract_content
from app.integrations.web.web_retriever import search_web
from app.routing.decision_engine import local_context_signals, should_use_web

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]{3,}", text.lower()))


def _filter_web_sources(
    query: str, extracted_sources: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    min_chars = int(os.getenv("WEB_MIN_CHARS", "350"))
    min_query_overlap = float(os.getenv("WEB_MIN_QUERY_OVERLAP", "0.015"))
    query_tokens = _tokenize(query)

    if not query_tokens:
        return [
            s for s in extracted_sources if len(str(s.get("text") or "")) >= min_chars
        ]

    kept: list[dict[str, Any]] = []
    for src in extracted_sources:
        text = str(src.get("text") or "")
        if len(text) < min_chars:
            continue
        page_tokens = _tokenize(text[:8000])
        overlap = len(query_tokens.intersection(page_tokens)) / float(
            len(query_tokens)
        )
        if overlap < min_query_overlap:
            continue
        kept.append(src)
    return kept


def _dedupe_web_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_urls: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in results:
        url = str(r.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        out.append(r)
    return out


def _verified_items_to_retrieval_results(
    verified_items: list[dict[str, Any]], confidence: float
) -> list[dict[str, Any]]:
    if not verified_items:
        return []

    verified_items = verified_items[: int(os.getenv("WEB_MAX_VERIFIED_ITEMS", "4"))]
    anchor = verified_items[0]
    anchor_id = str(anchor.get("id") or "")

    pedagogical_context = []
    for item in verified_items[1:]:
        if not item.get("id"):
            continue
        pedagogical_context.append(item)

    return [
        {
            "anchor_node_id": anchor_id,
            "anchor_node": {
                "id": anchor_id,
                "heading": anchor.get("heading", ""),
                "content": anchor.get("content", ""),
                "source": anchor.get("source", "web_verified"),
                "source_type": "web",
                "keywords": anchor.get("keywords", []),
            },
            "score": 0.0,
            "confidence": float(confidence),
            "pedagogical_context": [
                {
                    "id": str(p.get("id") or ""),
                    "heading": p.get("heading", ""),
                    "content": p.get("content", ""),
                    "source": p.get("source", "web_verified"),
                    "source_type": "web",
                    "keywords": p.get("keywords", []),
                }
                for p in pedagogical_context
                if p.get("id")
            ],
        }
    ]


def build_verified_web_retrieval_results(query: str) -> list[dict[str, Any]]:
    """
    Retrieve -> Extract -> Filter -> Verify, then adapt to teaching-agent context format.
    """
    max_web_results = int(os.getenv("WEB_RETRIEVER_MAX_RESULTS", "8"))
    max_verified_items = int(os.getenv("WEB_MAX_VERIFIED_ITEMS", "4"))
    max_chars_per_url = int(os.getenv("WEB_EXTRACT_MAX_CHARS", "6000"))

    raw_results = _dedupe_web_results(search_web(query, max_results=max_web_results))
    if not raw_results:
        logger.info("[hybrid] web_search returned 0 results")
        return []

    extracted: list[dict[str, Any]] = []
    for r in raw_results[:max_web_results]:
        url = str(r.get("url") or "")
        title = str(r.get("title") or "")
        text = extract_content(url, max_chars=max_chars_per_url)
        if not text:
            continue
        extracted.append({"title": title, "url": url, "text": text})

    logger.info("[hybrid] extracted web pages=%d", len(extracted))
    filtered = _filter_web_sources(query, extracted)
    logger.info("[hybrid] filtered web pages=%d", len(filtered))
    if not filtered:
        return []

    verified = verify_content(filtered)
    verified_items = list(verified.get("verified_context_items") or [])
    confidence = float(verified.get("confidence") or 0.0)
    verified_items = verified_items[:max_verified_items]
    logger.info(
        "[hybrid] verified web facts=%d confidence=%.3f",
        len(verified_items),
        confidence,
    )

    return _verified_items_to_retrieval_results(verified_items, confidence=confidence)


def apply_hybrid_retrieval(
    query: str,
    local_retrieval_results: list[dict[str, Any]],
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    """
    Local graph first. If local context is weak, use verified web context.
    """

    if not local_retrieval_results:
        logger.info("[hybrid] local retrieval empty -> web-only")
        try:
            web_results = build_verified_web_retrieval_results(query)
        except Exception as exc:
            logger.error(f"[hybrid] external search failed: {exc}")
            return {"status": "error", "message": "External search failed. Try again later."}
        return web_results[:1] if top_k <= 1 else web_results

    if not should_use_web(local_retrieval_results):
        sig = local_context_signals(local_retrieval_results)
        logger.info(
            "[hybrid] local strong -> local-only (top_score=%.3f matched_nodes=%.0f coverage=%.2f)",
            sig.get("top_score", 0.0),
            sig.get("matched_nodes", 0.0),
            sig.get("coverage_ratio", 0.0),
        )
        return local_retrieval_results

    sig = local_context_signals(local_retrieval_results)
    logger.info(
        "[hybrid] local weak -> web considered (top_score=%.3f matched_nodes=%.0f coverage=%.2f)",
        sig.get("top_score", 0.0),
        sig.get("matched_nodes", 0.0),
        sig.get("coverage_ratio", 0.0),
    )
    
    try:
        web_results = build_verified_web_retrieval_results(query)
    except Exception as exc:
        logger.error(f"[hybrid] external search failed: {exc}")
        return {"status": "error", "message": "External search failed. Try again later."}
        
    if not web_results:
        logger.info("[hybrid] web unavailable/empty -> keep local")
        return local_retrieval_results

    # If local match is extremely weak, prefer web-only.
    top_score_threshold = float(os.getenv("WEB_DECISION_TOP_SCORE_THRESHOLD", "0.45"))
    min_coverage_ratio = float(os.getenv("WEB_DECISION_MIN_COVERAGE_RATIO", "0.34"))
    if sig["top_score"] < (top_score_threshold * 0.65) or sig["coverage_ratio"] < (
        min_coverage_ratio * 0.65
    ):
        logger.info("[hybrid] using web-only (local weak)")
        return web_results

    # Otherwise, merge: local first, then one web verified context bundle.
    merged = list(local_retrieval_results[: max(1, top_k)])
    for w in web_results:
        if len(merged) >= max(1, top_k):
            break
        merged.append(w)
    return merged[: max(1, top_k)]

