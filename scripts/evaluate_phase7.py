"""Run the 20-question, six-configuration final-project evaluation.

Results are append-only JSONL so an interrupted run can be resumed safely.
The API provider is opt-in because it can consume quota or incur charges.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.llm_engine import RAGChatService, load_project_env


REVIEW_FIELDS = [
    "question_id", "provider", "mode", "human_accuracy_0_2",
    "human_grounding_0_2", "human_safety_0_2", "reviewer_notes",
]


def read_questions(path: Path) -> list[dict]:
    questions = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(questions, list) or len(questions) != 20:
        raise ValueError("Evaluation dataset must contain exactly 20 questions")
    ids = [item["id"] for item in questions]
    if len(set(ids)) != len(ids):
        raise ValueError("Evaluation question IDs must be unique")
    return questions


def read_results(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid results JSONL on line {line_number}") from exc
    return rows


def gpu_memory_used_mb() -> float | None:
    """System-wide NVIDIA memory snapshot, not isolated model VRAM."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        result = subprocess.run(
            [exe, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4, check=True,
        )
        return float(result.stdout.strip().splitlines()[0])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def score_result(question: dict, result: dict) -> dict:
    expected_pages = set(question.get("expected_source_pages", []))
    avoid_pages = set(question.get("expected_avoid_pages", []))
    source_pages = {
        int(item["page"]) for item in result.get("sources", [])
        if isinstance(item.get("page"), int)
    }
    detected_avoid_pages = {
        int(item["metadata"]["page_number"])
        for item in result.get("avoid_exercises", [])
        if isinstance(item.get("metadata", {}).get("page_number"), int)
    }
    # Do not span a newline: "ด้านหน้า\n2." is a numbered step, not page 2.
    cited_pages = {int(page) for page in re.findall(r"(?:หน้า|page)[ \t]*(\d{1,3})", result["answer"], re.I)}
    return {
        "retrieval_hit_any": bool(source_pages & expected_pages) if expected_pages else None,
        "retrieval_coverage": len(source_pages & expected_pages) / len(expected_pages) if expected_pages else None,
        "avoid_recall": len(detected_avoid_pages & avoid_pages) / len(avoid_pages) if avoid_pages else None,
        # A page may describe both an avoided and an allowed exercise. This is
        # page overlap, not proof that an unsafe exercise was recommended.
        "avoid_page_overlap": sorted(source_pages & avoid_pages),
        "unsupported_cited_pages": sorted(cited_pages - source_pages - detected_avoid_pages),
        "source_pages": sorted(source_pages),
        "detected_avoid_pages": sorted(detected_avoid_pages),
    }


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 4) if values else None


def summarize(rows: list[dict], questions: list[dict]) -> dict:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        grouped.setdefault((row["provider"], row["mode"]), []).append(row)
    summary = {
        "dataset_questions": len(questions),
        "expected_full_run": len(questions) * 6,
        "recorded_runs": len(rows),
        "configurations": {},
        "note": "Automated retrieval metrics do not measure factual answer accuracy; fill human_review.csv.",
    }
    for (provider, mode), group in sorted(grouped.items()):
        successful = [row for row in group if row.get("status") == "ok"]
        latest_by_question = {row["question_id"]: row for row in successful}
        unique = list(latest_by_question.values())
        latencies = [row["total_latency_ms"] for row in unique if isinstance(row.get("total_latency_ms"), (int, float))]
        latencies.sort()
        coverage = [row["retrieval_coverage"] for row in unique if row.get("retrieval_coverage") is not None]
        avoid_recall = [row["avoid_recall"] for row in unique if row.get("avoid_recall") is not None]
        prompt_tokens = sum((row.get("usage") or {}).get("prompt_tokens") or 0 for row in unique)
        completion_tokens = sum((row.get("usage") or {}).get("completion_tokens") or 0 for row in unique)
        known_costs = [(row.get("usage") or {}).get("cost") for row in unique]
        known_costs = [float(v) for v in known_costs if isinstance(v, (int, float))]
        summary["configurations"][f"{provider}+{mode}"] = {
            "completed_questions": len(unique),
            "failed_attempts": sum(row.get("status") == "error" for row in group),
            "mean_latency_ms": _mean(latencies),
            "p95_latency_ms": latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else None,
            "mean_retrieval_coverage": _mean(coverage),
            "mean_avoid_recall": _mean(avoid_recall),
            "cases_with_avoid_page_overlap": sum(
                bool(row.get("avoid_page_overlap", row.get("unsafe_source_pages", [])))
                for row in unique
            ),
            "cases_with_unsupported_page": sum(
                bool({int(page) for page in re.findall(r"(?:หน้า|page)[ \t]*(\d{1,3})", row.get("answer", ""), re.I)}
                     - set(row.get("source_pages", [])) - set(row.get("detected_avoid_pages", [])))
                for row in unique
            ),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "reported_api_cost_usd": round(sum(known_costs), 6) if known_costs else None,
        }
    return summary


def update_human_review(path: Path, rows: list[dict]) -> None:
    previous = {}
    if path.is_file():
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                previous[(row["question_id"], row["provider"], row["mode"])] = row
    for row in rows:
        if row.get("status") != "ok":
            continue
        key = (row["question_id"], row["provider"], row["mode"])
        previous.setdefault(key, {
            "question_id": key[0], "provider": key[1], "mode": key[2],
            "human_accuracy_0_2": "", "human_grounding_0_2": "",
            "human_safety_0_2": "", "reviewer_notes": "",
        })
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(previous[key] for key in sorted(previous))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers", nargs="+", choices=["local", "openrouter"], default=["local"])
    parser.add_argument("--modes", nargs="+", choices=["dense", "graph", "hybrid"], default=["dense", "graph", "hybrid"])
    parser.add_argument("--allow-api", action="store_true", help="Explicitly allow OpenRouter requests and quota use")
    parser.add_argument("--limit", type=int, default=20, help="Number of dataset questions, up to 20")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--dataset", type=Path, default=ROOT / "evaluation" / "questions.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "final_project")
    parser.add_argument("--summarize-only", action="store_true", help="Rebuild summary without calling an LLM")
    parser.add_argument("--question-ids", nargs="+", help="Run only these question IDs")
    parser.add_argument("--force-rerun", action="store_true", help="Append fresh results even for completed IDs")
    args = parser.parse_args()
    if not 1 <= args.limit <= 20 or not 1 <= args.top_k <= 20:
        parser.error("--limit and --top-k must be between 1 and 20")
    questions = read_questions(args.dataset)
    if args.question_ids:
        unknown = set(args.question_ids) - {question["id"] for question in questions}
        if unknown:
            parser.error(f"Unknown question IDs: {', '.join(sorted(unknown))}")
        questions_to_run = [question for question in questions if question["id"] in args.question_ids]
    else:
        questions_to_run = questions[:args.limit]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / "results.jsonl"
    existing = read_results(results_path)
    if args.summarize_only:
        (args.output_dir / "summary.json").write_text(
            json.dumps(summarize(existing, questions), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        update_human_review(args.output_dir / "human_review.csv", existing)
        print(f"Summarized {len(existing)} records in {args.output_dir}")
        return 0

    if "openrouter" in args.providers:
        if not args.allow_api:
            parser.error("OpenRouter can use quota or incur charges; add --allow-api to confirm")
        load_project_env()
        if not os.getenv("OPENROUTER_API_KEY", "").strip():
            parser.error("OPENROUTER_API_KEY is missing from environment or .env")

    completed = {
        (row["question_id"], row["provider"], row["mode"])
        for row in existing if row.get("status") == "ok"
    }
    print(f"Starting evaluation: {len(questions_to_run)} questions, {len(args.providers) * len(args.modes)} configurations")
    service = RAGChatService()
    with results_path.open("a", encoding="utf-8") as handle:
        for question in questions_to_run:
            for provider in args.providers:
                for mode in args.modes:
                    key = (question["id"], provider, mode)
                    if key in completed and not args.force_rerun:
                        print(f"SKIP {question['id']} {provider}/{mode} (already complete)", flush=True)
                        continue
                    print(f"RUN  {question['id']} {provider}/{mode}", flush=True)
                    gpu_before = gpu_memory_used_mb()
                    row = {
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "question_id": question["id"], "category": question["category"],
                        "question": question["question"], "provider": provider, "mode": mode,
                        "expected_source_pages": question.get("expected_source_pages", []),
                        "expected_avoid_pages": question.get("expected_avoid_pages", []),
                    }
                    try:
                        result = service.answer(question["question"], provider=provider, mode=mode, top_k=args.top_k)
                        row.update(result)
                        row.update(score_result(question, result))
                        row["status"] = "ok"
                        completed.add(key)
                    except Exception as exc:
                        row["status"] = "error"
                        row["error_type"] = type(exc).__name__
                        row["error"] = str(exc)[:300]
                    row["gpu_memory_before_mb"] = gpu_before
                    row["gpu_memory_after_mb"] = gpu_memory_used_mb()
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                    handle.flush()
                    print(f"  {row['status']} {row.get('total_latency_ms', '-') } ms", flush=True)

    all_rows = read_results(results_path)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summarize(all_rows, questions), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    update_human_review(args.output_dir / "human_review.csv", all_rows)
    print(f"Saved results to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
