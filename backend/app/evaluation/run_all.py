from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.graph.graph_builder import KnowledgeGraph
from app.ingestion.ingestion import MarkdownParser
from app.retrieval.retrieval import RetrievalEngine
from app.teaching.teaching_agent import TeachingAgent
from app.learner.learner_tracker import LearnerTracker
from app.evaluation.metrics import (
    groundedness_score,
    hallucination_rate,
    latency_ms,
    mrr,
    ndcg_at_k,
    precision_at_1,
    precision_at_k,
    recall_at_k,
    success_at_k,
    summarize,
)
from app.pipeline import apply_hybrid_retrieval, build_verified_web_retrieval_results
from app.evaluation.llm_judge import evaluate_answer


@dataclass
class EvalCase:
    query: str
    gold_node_ids: set[str]
    relevance_by_id: dict[str, float]
    hard_negative_node_ids: set[str]


@dataclass
class EvalConfig:
    data_dir: str
    top_k: int
    expand_depth_full: int
    cases: list[EvalCase]


def load_config(path: str) -> EvalConfig:
    with open(path, "r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    cases = [
        EvalCase(
            query=item["query"],
            gold_node_ids=set(item.get("gold_node_ids", [])),
            relevance_by_id={
                str(node_id): float(score)
                for node_id, score in (item.get("relevance_by_id", {}) or {}).items()
            },
            hard_negative_node_ids=set(item.get("hard_negative_node_ids", [])),
        )
        for item in payload.get("cases", [])
    ]
    return EvalConfig(
        data_dir=payload.get("data_dir", "backend/data"),
        top_k=int(payload.get("top_k", 3)),
        expand_depth_full=int(payload.get("expand_depth_full", 1)),
        cases=cases,
    )


def build_retrieval(data_dir: str) -> RetrievalEngine:
    parser = MarkdownParser()
    chunks = parser.parse_directory(data_dir)
    graph = KnowledgeGraph()
    graph.build_from_chunks(chunks)
    return RetrievalEngine(graph)


def _tokenize(text: str) -> set[str]:
    import re

    return set(re.findall(r"[a-zA-Z0-9]{3,}", (text or "").lower()))


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _map_web_item_to_gold(
    item: dict[str, Any],
    gold_node_ids: set[str],
    gold_token_index: dict[str, set[str]],
) -> str | None:
    anchor_id = str(item.get("anchor_node_id") or item.get("id") or "").strip()
    if anchor_id in gold_node_ids:
        return anchor_id

    anchor_node = item.get("anchor_node") or {}
    heading = str(anchor_node.get("heading") or "")
    content = str(anchor_node.get("content") or "")
    tokens = _tokenize(heading + " " + content)
    if not tokens:
        return None

    best_gold: str | None = None
    best_score = 0.0
    for gold_id in gold_node_ids:
        gold_tokens = gold_token_index.get(gold_id, set())
        if not gold_tokens:
            continue
        overlap = len(tokens.intersection(gold_tokens))
        score = overlap / float(max(1, len(tokens)))
        if score > best_score:
            best_score = score
            best_gold = gold_id

    # If no meaningful lexical overlap, don't hallucinate a mapping.
    min_overlap = float(os.getenv("WEB_EVAL_MIN_GOLD_OVERLAP", "0.08"))
    if best_score < min_overlap:
        return None
    return best_gold


def _map_web_retrieval_results_to_gold(
    retrieval_results: list[dict[str, Any]],
    gold_node_ids: set[str],
    retrieval: RetrievalEngine,
    top_k: int,
) -> tuple[list[str], list[str]]:
    gold_token_index: dict[str, set[str]] = {}
    for gold_id in gold_node_ids:
        if gold_id not in retrieval.kg.graph:
            gold_token_index[gold_id] = set()
            continue
        node = retrieval.kg.graph.nodes[gold_id]
        heading = str(node.get("heading") or "")
        content = str(node.get("content") or "")
        keywords = node.get("keywords") or []
        gold_token_index[gold_id] = _tokenize(
            heading + " " + content + " " + " ".join(map(str, keywords))
        )

    anchor_ids: list[str] = []
    expanded_ids: list[str] = []

    for res in retrieval_results[:top_k]:
        mapped_anchor = _map_web_item_to_gold(
            res, gold_node_ids=gold_node_ids, gold_token_index=gold_token_index
        )
        if mapped_anchor:
            anchor_ids.append(mapped_anchor)
            expanded_ids.append(mapped_anchor)

        for ped in res.get("pedagogical_context") or []:
            mapped_ped = _map_web_item_to_gold(
                {"anchor_node_id": ped.get("id"), "anchor_node": ped},
                gold_node_ids=gold_node_ids,
                gold_token_index=gold_token_index,
            )
            if mapped_ped:
                expanded_ids.append(mapped_ped)

    return _dedupe_preserve_order(anchor_ids), _dedupe_preserve_order(expanded_ids)


def run_case(
    case: EvalCase,
    retrieval: RetrievalEngine,
    teacher: TeachingAgent,
    top_k: int,
    expand_depth: int,
    mode: str,
) -> dict[str, Any]:
    start = time.time()
    if mode == "llm_only":
        retrieval_results = []
    elif mode == "web_only":
        retrieval_results = build_verified_web_retrieval_results(case.query)
    else:
        # Local retrieval (graph) is always used for candidate retrieval/anchor selection.
        retrieval_results = retrieval.search(
            query=case.query,
            top_n=top_k,
            expand_depth=expand_depth,
            use_rerank=(mode in ("full_system", "local_only", "hybrid")),
        )
        if mode == "hybrid":
            retrieval_results = apply_hybrid_retrieval(
                case.query, retrieval_results, top_k=top_k
            )

    if mode in ("web_only", "hybrid"):
        anchor_ids, expanded_ids = _map_web_retrieval_results_to_gold(
            retrieval_results=retrieval_results,
            gold_node_ids=case.gold_node_ids,
            retrieval=retrieval,
            top_k=top_k,
        )
    else:
        anchor_ids = [
            item["anchor_node_id"]
            for item in retrieval_results
            if item.get("anchor_node_id")
        ]
        expanded_ids = []
        seen_ids: set[str] = set()
        for result in retrieval_results:
            anchor_id = result.get("anchor_node_id")
            if anchor_id and anchor_id not in seen_ids:
                seen_ids.add(anchor_id)
                expanded_ids.append(anchor_id)
            for node in result.get("pedagogical_context", []):
                node_id = node.get("id")
                if node_id and node_id not in seen_ids:
                    seen_ids.add(node_id)
                    expanded_ids.append(node_id)

    mastery_stub: dict[str, dict] = {}
    answer = teacher.generate(
        query=case.query,
        retrieval_results=retrieval_results,
        mastery_by_node=mastery_stub,
        mode="socratic",
    )
    end = time.time()

    citations = answer.get("citations", []) if isinstance(answer, dict) else []
    response_text = answer.get("text", "") if isinstance(answer, dict) else ""
    ungrounded = answer.get("ungrounded_sentences", []) if isinstance(answer, dict) else []

    prior_mastery = 0.25
    is_correct = True if expanded_ids else False
    learning_gain = LearnerTracker.estimate_learning_gain(prior_mastery, is_correct, "medium")
    hallucination = (
        len(ungrounded) / max(len(response_text.split(".")), 1)
        if ungrounded
        else hallucination_rate(response_text, citations)
    )

    lowered_answer = response_text.lower()
    answer_correctness = 1.0 if any(
        str(gold_id).lower() in lowered_answer for gold_id in case.gold_node_ids
    ) else 0.0
    concept_coverage = 1.0 if set(expanded_ids).intersection(case.gold_node_ids) else 0.0
    citation_support = 1.0 if citations and groundedness_score(response_text, citations) > 0 else 0.0

    gold_in_topk = len(set(anchor_ids[:top_k]).intersection(case.gold_node_ids))
    concept_coverage = gold_in_topk / max(len(case.gold_node_ids), 1)

    rank_weights = []
    for gold_id in case.gold_node_ids:
        rank = None
        if gold_id in anchor_ids:
            rank = anchor_ids.index(gold_id) + 1
        elif gold_id in expanded_ids:
            rank = expanded_ids.index(gold_id) + 1
        if rank is not None:
            rank_weights.append(1.0 / float(rank))
    weighted_concept_coverage = (
        sum(rank_weights) / max(len(case.gold_node_ids), 1) if rank_weights else 0.0
    )

    per_case_log = {
        "query": case.query,
        "mode": mode,
        "gold_node_ids": sorted(case.gold_node_ids),
        "relevance_by_id": case.relevance_by_id,
        "hard_negative_node_ids": sorted(case.hard_negative_node_ids),
        "ranked_anchor_nodes": [
            {
                "node_id": item.get("anchor_node_id"),
                "score": item.get("score", 0.0),
                "confidence": item.get("confidence", 0.0),
                "ranking_features": item.get("ranking_features", {}),
                "heading": (item.get("anchor_node", {}) or {}).get("heading", ""),
            }
            for item in retrieval_results
        ],
        "candidate_pool_node_ids": retrieval_results[0].get("candidate_pool_node_ids", [])
        if retrieval_results
        else [],
        "expanded_context_node_ids": expanded_ids,
        "answer_text": response_text,
        "citations": citations,
        "ungrounded_sentences": ungrounded,
    }

    unique_headings = {
        (item.get("anchor_node", {}) or {}).get("heading", "").strip().lower()
        for item in retrieval_results
        if (item.get("anchor_node", {}) or {}).get("heading")
    }
    heading_diversity = len(unique_headings) / max(len(retrieval_results), 1) if retrieval_results else 0.0

    unique_sources = {
        (item.get("anchor_node", {}) or {}).get("source", "").strip().lower()
        for item in retrieval_results
        if (item.get("anchor_node", {}) or {}).get("source")
    }
    source_diversity = len(unique_sources) / max(len(retrieval_results), 1) if retrieval_results else 0.0

    llm_evaluation = evaluate_answer(
        query=case.query,
        answer=response_text,
        sources=retrieval_results,
    )
    per_case_log["llm_evaluation"] = llm_evaluation

    return {
        "precision@1": precision_at_1(anchor_ids, case.gold_node_ids),
        "precision@3": precision_at_k(anchor_ids, case.gold_node_ids, min(3, top_k)),
        "success@3": success_at_k(anchor_ids, case.gold_node_ids, min(3, top_k)),
        "ndcg@3": ndcg_at_k(
            anchor_ids, case.gold_node_ids, min(3, top_k), relevance_by_id=case.relevance_by_id
        ),
        "mrr": mrr(anchor_ids, case.gold_node_ids, k=max(top_k, 3)),
        "precision@k": precision_at_k(expanded_ids, case.gold_node_ids, top_k),
        "recall@k": recall_at_k(expanded_ids, case.gold_node_ids, top_k),
        "groundedness": groundedness_score(response_text, citations),
        "hallucination_rate": hallucination,
        "learning_gain": learning_gain,
        "answer_correctness": answer_correctness,
        "concept_coverage": concept_coverage,
        "weighted_concept_coverage": weighted_concept_coverage,
        "heading_diversity": heading_diversity,
        "source_diversity": source_diversity,
        "citation_support": citation_support,
        "latency_ms": latency_ms(start, end),
        "_case_log": per_case_log,
    }


def aggregate(metrics: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    if not metrics:
        return {}
    keys = [key for key in metrics[0].keys() if not key.startswith("_")]
    summary: dict[str, dict[str, float]] = {}
    for key in keys:
        vals = [m[key] for m in metrics]
        stats = summarize(vals)
        summary[key] = {
            "mean": stats.mean,
            "std": stats.std,
            "ci95": stats.ci95,
        }
    
    # Handle nested LLM evaluation metrics
    llm_eval_metrics = {
        "correctness": [],
        "relevance": [],
        "completeness": [],
    }
    for m in metrics:
        if "_case_log" in m and "llm_evaluation" in m["_case_log"]:
            eval_data = m["_case_log"]["llm_evaluation"]
            if "correctness" in eval_data and "score" in eval_data["correctness"]:
                llm_eval_metrics["correctness"].append(eval_data["correctness"]["score"])
            if "relevance" in eval_data and "score" in eval_data["relevance"]:
                llm_eval_metrics["relevance"].append(eval_data["relevance"]["score"])
            if "completeness" in eval_data and "score" in eval_data["completeness"]:
                llm_eval_metrics["completeness"].append(eval_data["completeness"]["score"])

    for key, vals in llm_eval_metrics.items():
        if vals:
            stats = summarize(vals)
            summary[f"llm_{key}"] = {
                "mean": stats.mean,
                "std": stats.std,
                "ci95": stats.ci95,
            }

    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="backend/app/evaluation/results")
    args = parser.parse_args()

    config = load_config(args.config)
    os.environ["PYTHONHASHSEED"] = str(args.seed)

    retrieval = build_retrieval(config.data_dir)
    teacher = TeachingAgent()

    modes = {
        "llm_only": 0,
        "bm25_only": 0,
        "full_system": config.expand_depth_full,
        "local_only": config.expand_depth_full,
        "web_only": 0,
        "hybrid": config.expand_depth_full,
    }

    results: dict[str, list[dict[str, float]]] = {mode: [] for mode in modes}
    case_logs: list[dict[str, Any]] = []
    for _ in range(args.runs):
        for case in config.cases:
            for mode, depth in modes.items():
                metrics = run_case(
                    case=case,
                    retrieval=retrieval,
                    teacher=teacher,
                    top_k=config.top_k,
                    expand_depth=depth,
                    mode=mode,
                )
                results[mode].append(metrics)
                if "_case_log" in metrics:
                    case_logs.append(metrics["_case_log"])

    summary = {mode: aggregate(metrics) for mode, metrics in results.items()}

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    output_path = output_dir / f"summary_{timestamp}.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "config": {
                    "data_dir": config.data_dir,
                    "top_k": config.top_k,
                    "expand_depth_full": config.expand_depth_full,
                    "runs": args.runs,
                    "seed": args.seed,
                },
                "summary": summary,
            },
            handle,
            indent=2,
        )

    logs_path = output_dir / f"case_logs_{timestamp}.json"
    with logs_path.open("w", encoding="utf-8") as handle:
        json.dump({"cases": case_logs}, handle, indent=2)


if __name__ == "__main__":
    main()
