from __future__ import annotations

import os
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def local_context_signals(local_results: list[dict]) -> dict[str, float]:
    """
    Signals are intentionally simple and explainable so that routing behavior
    can be audited without peeking into model internals.
    """
    if not local_results:
        return {
            "top_score": 0.0,
            "matched_nodes": 0.0,
            "coverage_ratio": 0.0,
            "result_count": 0.0,
        }

    top_score = 0.0
    anchor_ids: set[str] = set()

    for item in local_results:
        anchor_id = item.get("anchor_node_id")
        if anchor_id:
            anchor_ids.add(str(anchor_id))

        conf = _safe_float(item.get("confidence"), None)  # type: ignore[arg-type]
        score = _safe_float(item.get("score"), None)  # type: ignore[arg-type]
        item_score = conf if conf is not None else score
        top_score = max(top_score, _safe_float(item_score, 0.0))

        # If user uploaded context exists, always prefer local.
        anchor_src = (item.get("anchor_node") or {}).get("source")
        if anchor_src == "upload":
            return {
                "top_score": 1.0,
                "matched_nodes": float(len(anchor_ids) or 1),
                "coverage_ratio": 1.0,
                "result_count": float(len(local_results)),
            }
        for node in item.get("pedagogical_context", []) or []:
            node_src = (node or {}).get("source")
            if node_src == "upload":
                return {
                    "top_score": 1.0,
                    "matched_nodes": float(len(anchor_ids) or 1),
                    "coverage_ratio": 1.0,
                    "result_count": float(len(local_results)),
                }

    result_count = max(1, len(local_results))
    matched_nodes = float(len(anchor_ids))
    coverage_ratio = matched_nodes / float(result_count)
    return {
        "top_score": top_score,
        "matched_nodes": matched_nodes,
        "coverage_ratio": coverage_ratio,
        "result_count": float(len(local_results)),
    }


def should_use_web(local_results: list[dict]) -> bool:
    """
    Decide whether web fallback is necessary.

    Returns True if:
    - no results, OR
    - top score < threshold, OR
    - low concept/coverage ratio.
    """
    sig = local_context_signals(local_results)
    if sig["result_count"] <= 0:
        return True

    top_score_threshold = float(os.getenv("WEB_DECISION_TOP_SCORE_THRESHOLD", "0.45"))
    min_coverage_ratio = float(os.getenv("WEB_DECISION_MIN_COVERAGE_RATIO", "0.34"))
    min_matched_nodes = float(os.getenv("WEB_DECISION_MIN_MATCHED_NODES", "1"))

    return (
        sig["top_score"] < top_score_threshold
        or sig["matched_nodes"] < min_matched_nodes
        or sig["coverage_ratio"] < min_coverage_ratio
    )

