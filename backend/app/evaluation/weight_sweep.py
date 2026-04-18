from __future__ import annotations

import json
import os
from pathlib import Path

from app.evaluation.run_all import aggregate, build_retrieval, load_config, run_case
from app.teaching.teaching_agent import TeachingAgent


def _set_weights(weights: dict[str, float]) -> None:
    os.environ["RERANK_W_BM25"] = str(weights["bm25"])
    os.environ["RERANK_W_PHRASE"] = str(weights["phrase"])
    os.environ["RERANK_W_TITLE"] = str(weights["title"])
    os.environ["RERANK_W_ENTITY"] = str(weights["entity"])
    os.environ["RERANK_W_GRAPH"] = str(weights["graph"])
    os.environ["RERANK_DIVERSITY_PENALTY"] = str(weights["diversity"])


def main() -> None:
    config_path = Path("backend/app/evaluation/configs/auto.yaml")
    out_path = Path("backend/app/evaluation/results/weight_sweep_results.json")
    runs = 5
    config = load_config(str(config_path))

    configs = [
        {"name": "A_balanced", "bm25": 0.34, "phrase": 0.28, "title": 0.18, "entity": 0.15, "graph": 0.05, "diversity": 0.22},
        {"name": "B_phrase_up", "bm25": 0.30, "phrase": 0.32, "title": 0.18, "entity": 0.15, "graph": 0.05, "diversity": 0.22},
        {"name": "C_entity_up", "bm25": 0.32, "phrase": 0.26, "title": 0.16, "entity": 0.21, "graph": 0.05, "diversity": 0.20},
        {"name": "D_title_up", "bm25": 0.30, "phrase": 0.24, "title": 0.24, "entity": 0.17, "graph": 0.05, "diversity": 0.24},
        {"name": "E_diversity_strong", "bm25": 0.33, "phrase": 0.27, "title": 0.17, "entity": 0.18, "graph": 0.05, "diversity": 0.30},
        {"name": "F_graph_up", "bm25": 0.31, "phrase": 0.25, "title": 0.17, "entity": 0.15, "graph": 0.12, "diversity": 0.24},
    ]

    results = []
    for cfg in configs:
        _set_weights(cfg)
        retrieval = build_retrieval(config.data_dir)
        teacher = TeachingAgent()

        mode_metrics = []
        for _ in range(runs):
            for case in config.cases:
                metrics = run_case(
                    case=case,
                    retrieval=retrieval,
                    teacher=teacher,
                    top_k=config.top_k,
                    expand_depth=config.expand_depth_full,
                    mode="full_system",
                )
                mode_metrics.append(metrics)

        summary = aggregate(mode_metrics)
        row = {
            "config": cfg["name"],
            "weights": cfg,
            "precision@1": summary["precision@1"]["mean"],
            "precision@3": summary["precision@3"]["mean"],
            "ndcg@3": summary["ndcg@3"]["mean"],
            "mrr": summary["mrr"]["mean"],
        }
        results.append(row)

    # Constraint: precision@1 >= 0.95
    feasible = [r for r in results if r["precision@1"] >= 0.95]
    best = max(feasible, key=lambda r: r["ndcg@3"]) if feasible else None

    payload = {"runs": runs, "results": results, "best_feasible": best}
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # Intentionally no stdout spam in production-grade runs.


if __name__ == "__main__":
    main()
