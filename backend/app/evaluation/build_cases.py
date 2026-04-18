from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

from app.graph.graph_builder import KnowledgeGraph
from app.ingestion.ingestion import MarkdownParser


def build_cases(data_dir: str, max_cases: int = 30) -> list[dict]:
    parser = MarkdownParser()
    chunks = parser.parse_directory(data_dir)
    graph = KnowledgeGraph()
    graph.build_from_chunks(chunks)

    cases = []
    for chunk in chunks:
        heading = chunk.get("heading", "").strip()
        if not heading or heading.lower() == "root":
            continue
        anchor_id = chunk.get("id")
        if not anchor_id:
            continue

        gold_ids = [anchor_id]
        # Multi-gold labels: include direct parent/child neighbors as acceptable hits.
        if anchor_id in graph.graph:
            neighbors = set(graph.graph.predecessors(anchor_id)) | set(
                graph.graph.successors(anchor_id)
            )
            for node_id in neighbors:
                if node_id not in gold_ids:
                    gold_ids.append(node_id)
                if len(gold_ids) >= 4:
                    break

        hard_negs = _hard_negatives(
            graph=graph,
            anchor_id=anchor_id,
            heading=heading,
            limit=4,
        )
        relevance = _relevance_map(gold_ids, hard_negs)

        primary_case = {
            "query": f"Explain {heading}.",
            "gold_node_ids": gold_ids,
            "relevance_by_id": relevance,
            "hard_negative_node_ids": hard_negs,
        }
        cases.append(primary_case)

        # Harder benchmark queries: paraphrase and multi-intent composition.
        paraphrase = {
            "query": f"What are the core ideas behind {heading}, and how does it connect to related topics?",
            "gold_node_ids": gold_ids,
            "relevance_by_id": relevance,
            "hard_negative_node_ids": primary_case["hard_negative_node_ids"],
        }
        cases.append(paraphrase)

        contrast_query = {
            "query": f"When should I use {heading}, and what closely related concept should I avoid confusing it with?",
            "gold_node_ids": gold_ids,
            "relevance_by_id": relevance,
            "hard_negative_node_ids": primary_case["hard_negative_node_ids"],
        }
        cases.append(contrast_query)

        if len(gold_ids) > 1:
            bridge_query = {
                "query": f"Compare {heading} with its prerequisite concepts and explain their relationship.",
                "gold_node_ids": gold_ids[: min(3, len(gold_ids))],
                "relevance_by_id": relevance,
                "hard_negative_node_ids": primary_case["hard_negative_node_ids"],
            }
            cases.append(bridge_query)

        disambiguation = {
            "query": f"Disambiguate {heading} from similar terms and provide one concrete example.",
            "gold_node_ids": gold_ids,
            "relevance_by_id": relevance,
            "hard_negative_node_ids": primary_case["hard_negative_node_ids"],
        }
        cases.append(disambiguation)

    # Keep deterministic ordering and cap to requested budget.
    cases = cases[: max_cases]
    return cases


def _hard_negatives(
    graph: KnowledgeGraph, anchor_id: str, heading: str, limit: int = 3
) -> list[str]:
    anchor_tokens = set(re.findall(r"[a-zA-Z0-9]{3,}", heading.lower()))
    parent_nodes = set(graph.graph.predecessors(anchor_id))
    child_nodes = set(graph.graph.successors(anchor_id))
    neighbor_nodes = parent_nodes | child_nodes
    negatives: list[tuple[float, str]] = []
    fallback: list[tuple[float, str]] = []

    # First preference: ambiguous siblings (same parent, not direct neighbor).
    sibling_candidates: set[str] = set()
    for parent_id in parent_nodes:
        sibling_candidates.update(graph.graph.successors(parent_id))

    for node_id in sibling_candidates:
        if node_id == anchor_id or node_id in neighbor_nodes:
            continue
        data = graph.graph.nodes[node_id]
        candidate_heading = str(data.get("heading", ""))
        tokens = set(re.findall(r"[a-zA-Z0-9]{3,}", candidate_heading.lower()))
        if not tokens:
            continue
        jaccard = len(anchor_tokens.intersection(tokens)) / max(len(anchor_tokens.union(tokens)), 1)
        if jaccard > 0:
            negatives.append((jaccard + 0.2, node_id))

    # Second preference: lexically similar non-neighbors across the graph.
    for node_id, data in graph.graph.nodes(data=True):
        if node_id == anchor_id or node_id in neighbor_nodes:
            continue
        candidate_heading = str(data.get("heading", ""))
        tokens = set(re.findall(r"[a-zA-Z0-9]{3,}", candidate_heading.lower()))
        if not tokens:
            continue
        jaccard = len(anchor_tokens.intersection(tokens)) / max(len(anchor_tokens.union(tokens)), 1)
        if 0.15 <= jaccard <= 0.85:
            negatives.append((jaccard, node_id))
        elif jaccard > 0:
            fallback.append((jaccard, node_id))

    # Guarantee a non-empty list when possible, so ranking gets real ambiguity pressure.
    merged = sorted(negatives, key=lambda x: x[0], reverse=True)
    chosen: list[str] = []
    for _, node_id in merged:
        if node_id not in chosen:
            chosen.append(node_id)
        if len(chosen) >= limit:
            return chosen

    for _, node_id in sorted(fallback, key=lambda x: x[0], reverse=True):
        if node_id not in chosen:
            chosen.append(node_id)
        if len(chosen) >= limit:
            break
    return chosen


def _relevance_map(gold_ids: list[str], hard_negatives: list[str]) -> dict[str, float]:
    relevance: dict[str, float] = {}
    if gold_ids:
        relevance[gold_ids[0]] = 3.0
        for node_id in gold_ids[1:]:
            relevance[node_id] = 2.0
    for node_id in hard_negatives[:2]:
        if node_id not in relevance:
            relevance[node_id] = 1.0
    return relevance


def main() -> None:
    argp = argparse.ArgumentParser()
    argp.add_argument("--data-dir", default="backend/data")
    argp.add_argument("--output", default="backend/app/evaluation/configs/auto.yaml")
    argp.add_argument("--max-cases", type=int, default=30)
    args = argp.parse_args()

    cases = build_cases(args.data_dir, args.max_cases)
    payload = {
        "data_dir": args.data_dir,
        "top_k": 3,
        "expand_depth_full": 1,
        "cases": cases,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


if __name__ == "__main__":
    main()
