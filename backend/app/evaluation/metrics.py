from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from math import log2
from statistics import mean, stdev
from typing import Iterable


@dataclass
class MetricSummary:
    mean: float
    std: float
    ci95: float


def precision_at_k(predicted: list[str], gold: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = predicted[:k]
    if not top_k:
        return 0.0
    hit = sum(1 for item in top_k if item in gold)
    return hit / float(k)


def recall_at_k(predicted: list[str], gold: set[str], k: int) -> float:
    if not gold:
        return 0.0
    top_k = predicted[:k]
    hit = sum(1 for item in top_k if item in gold)
    return hit / float(len(gold))


def precision_at_1(predicted: list[str], gold: set[str]) -> float:
    return precision_at_k(predicted, gold, 1)


def mrr(predicted: list[str], gold: set[str], k: int = 10) -> float:
    if not predicted or not gold:
        return 0.0
    for idx, node_id in enumerate(predicted[:k], start=1):
        if node_id in gold:
            return 1.0 / float(idx)
    return 0.0


def success_at_k(predicted: list[str], gold: set[str], k: int) -> float:
    if k <= 0 or not predicted or not gold:
        return 0.0
    top_k = predicted[:k]
    return 1.0 if any(item in gold for item in top_k) else 0.0


def ndcg_at_k(
    predicted: list[str], gold: set[str], k: int, relevance_by_id: dict[str, float] | None = None
) -> float:
    if k <= 0 or not predicted or not gold:
        return 0.0
    relevance_by_id = relevance_by_id or {}
    dcg = 0.0
    for rank, node_id in enumerate(predicted[:k], start=1):
        rel = float(relevance_by_id.get(node_id, 1.0 if node_id in gold else 0.0))
        if rel > 0:
            dcg += ((2.0**rel) - 1.0) / log2(rank + 1)

    ideal_rels = sorted(
        [float(relevance_by_id.get(node_id, 1.0)) for node_id in gold], reverse=True
    )[:k]
    idcg = sum((((2.0**rel) - 1.0) / log2(rank + 1)) for rank, rel in enumerate(ideal_rels, start=1))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def groundedness_score(answer: str, citations: list[dict]) -> float:
    if not answer.strip():
        return 0.0
    if not citations:
        return 0.0
    cited_heads = [c.get("heading", "") for c in citations if c.get("heading")]
    hits = sum(1 for h in cited_heads if h and h.lower() in answer.lower())
    return min(1.0, hits / max(len(cited_heads), 1))


def hallucination_rate(answer: str, citations: list[dict]) -> float:
    if not answer.strip():
        return 1.0 if citations else 0.0
    sentences = [s for s in answer.split(".") if s.strip()]
    if not sentences:
        return 0.0
    if not citations:
        return 1.0
    terms = set()
    for c in citations:
        heading = c.get("heading", "")
        for token in heading.lower().split():
            if len(token) >= 3:
                terms.add(token)
    ungrounded = 0
    for sentence in sentences:
        tokens = {t for t in sentence.lower().split() if len(t) >= 3}
        if not tokens.intersection(terms):
            ungrounded += 1
    return ungrounded / max(len(sentences), 1)


def latency_ms(start_s: float, end_s: float) -> float:
    return max(0.0, (end_s - start_s) * 1000.0)


def summarize(values: Iterable[float]) -> MetricSummary:
    vals = list(values)
    if not vals:
        return MetricSummary(mean=0.0, std=0.0, ci95=0.0)
    if len(vals) == 1:
        return MetricSummary(mean=vals[0], std=0.0, ci95=0.0)
    mu = mean(vals)
    sd = stdev(vals)
    ci = 1.96 * sd / sqrt(len(vals))
    return MetricSummary(mean=mu, std=sd, ci95=ci)
