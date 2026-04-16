from __future__ import annotations

import argparse
import json
from pathlib import Path


def latest_summary(results_dir: Path) -> Path | None:
    summaries = sorted(results_dir.glob("summary_*.json"))
    return summaries[-1] if summaries else None


def write_report(summary_path: Path, output_dir: Path) -> None:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})

    headers = ["mode", "metric", "mean", "std", "ci95"]
    csv_lines = [",".join(headers)]
    md_lines = ["| Mode | Metric | Mean | Std | CI95 |", "|---|---|---:|---:|---:|"]

    for mode, metrics in summary.items():
        for metric, stats in metrics.items():
            mean = f"{stats.get('mean', 0.0):.4f}"
            std = f"{stats.get('std', 0.0):.4f}"
            ci = f"{stats.get('ci95', 0.0):.4f}"
            csv_lines.append(f"{mode},{metric},{mean},{std},{ci}")
            md_lines.append(f"| {mode} | {metric} | {mean} | {std} | {ci} |")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.csv").write_text("\n".join(csv_lines), encoding="utf-8")
    (output_dir / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")


def main() -> None:
    argp = argparse.ArgumentParser()
    argp.add_argument("--results-dir", default="backend/app/evaluation/results")
    argp.add_argument("--summary", default="")
    args = argp.parse_args()

    results_dir = Path(args.results_dir)
    summary_path = Path(args.summary) if args.summary else latest_summary(results_dir)
    if not summary_path:
        raise SystemExit("No summary JSON found in results directory.")

    write_report(summary_path, results_dir)


if __name__ == "__main__":
    main()
