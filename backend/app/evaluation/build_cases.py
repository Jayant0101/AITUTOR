from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from app.ingestion.ingestion import MarkdownParser


def build_cases(data_dir: str, max_cases: int = 30) -> list[dict]:
    parser = MarkdownParser()
    chunks = parser.parse_directory(data_dir)
    cases = []
    for chunk in chunks:
        heading = chunk.get("heading", "").strip()
        if not heading or heading.lower() == "root":
            continue
        cases.append(
            {
                "query": f"Explain {heading}.",
                "gold_node_ids": [chunk.get("id")],
            }
        )
    return cases[:max_cases]


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
