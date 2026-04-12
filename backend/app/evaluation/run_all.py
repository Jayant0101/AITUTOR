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
from app.evaluation.metrics import (
    groundedness_score,
    latency_ms,
    precision_at_k,
    recall_at_k,
    summarize,
)


@dataclass
class EvalCase:
    query: str
    gold_node_ids: set[str]


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
        EvalCase(query=item["query"], gold_node_ids=set(item.get("gold_node_ids", [])))
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
    else:
        retrieval_results = retrieval.search(
            query=case.query, top_n=top_k, expand_depth=expand_depth
        )

    predicted_ids = [
        item["anchor_node_id"] for item in retrieval_results if item.get("anchor_node_id")
    ]
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

    return {
        "precision@k": precision_at_k(predicted_ids, case.gold_node_ids, top_k),
        "recall@k": recall_at_k(predicted_ids, case.gold_node_ids, top_k),
        "groundedness": groundedness_score(response_text, citations),
        "latency_ms": latency_ms(start, end),
    }


def aggregate(metrics: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    if not metrics:
        return {}
    keys = metrics[0].keys()
    summary: dict[str, dict[str, float]] = {}
    for key in keys:
        vals = [m[key] for m in metrics]
        stats = summarize(vals)
        summary[key] = {
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
    }

    results: dict[str, list[dict[str, float]]] = {mode: [] for mode in modes}
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


if __name__ == "__main__":
    main()
