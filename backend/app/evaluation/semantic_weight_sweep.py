from __future__ import annotations

import json
import os
from pathlib import Path

from app.evaluation.run_all import aggregate, build_retrieval, load_config, run_case
from app.teaching.teaching_agent import TeachingAgent


def _set_semantic_weights(concept: float, multi: float, relationship: float) -> None:
    os.environ["RERANK_W_CONCEPT_COVERAGE"] = str(concept)
    os.environ["RERANK_W_MULTI_CONCEPT"] = str(multi)
    os.environ["RERANK_W_RELATIONSHIP"] = str(relationship)


def main() -> None:
    config = load_config("backend/app/evaluation/configs/auto.yaml")
    runs = 5
    out_path = Path("backend/app/evaluation/results/semantic_weight_sweep_results.json")

    grid = [
        ("S1_balanced", 0.12, 0.08, 0.07),
        ("S2_concept_up", 0.16, 0.07, 0.06),
        ("S3_multi_up", 0.10, 0.12, 0.06),
        ("S4_relation_up", 0.10, 0.07, 0.11),
        ("S5_concept_relation", 0.15, 0.06, 0.09),
        ("S6_light_semantic", 0.08, 0.05, 0.05),
    ]

    rows = []
    for name, w_concept, w_multi, w_rel in grid:
        _set_semantic_weights(w_concept, w_multi, w_rel)
        retrieval = build_retrieval(config.data_dir)
        teacher = TeachingAgent()

        metrics = []
        for _ in range(runs):
            for case in config.cases:
                metrics.append(
                    run_case(
                        case=case,
                        retrieval=retrieval,
                        teacher=teacher,
                        top_k=config.top_k,
                        expand_depth=config.expand_depth_full,
                        mode="full_system",
                    )
                )
        summary = aggregate(metrics)
        rows.append(
            {
                "config": name,
                "weights": {
                    "concept_coverage": w_concept,
                    "multi_concept": w_multi,
                    "relationship": w_rel,
                },
                "precision@1": summary["precision@1"]["mean"],
                "precision@3": summary["precision@3"]["mean"],
                "ndcg@3": summary["ndcg@3"]["mean"],
                "mrr": summary["mrr"]["mean"],
            }
        )

    feasible = [
        row
        for row in rows
        if row["precision@1"] >= 0.95 and row["ndcg@3"] >= 0.8
    ]
    best = max(feasible, key=lambda r: r["precision@3"]) if feasible else None

    payload = {"runs": runs, "results": rows, "best_feasible": best}
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # Intentionally no stdout spam in production-grade runs.


if __name__ == "__main__":
    main()
