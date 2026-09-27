"""Offline checks for the evaluation and reporting pipeline."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_final_report import build_report
from scripts.evaluate_phase7 import read_questions, score_result, summarize, update_human_review


ROOT = Path(__file__).resolve().parent.parent


class FinalPhaseTests(unittest.TestCase):
    def test_dataset_has_required_split(self):
        questions = read_questions(ROOT / "evaluation" / "questions.json")
        self.assertEqual(len(questions), 20)
        self.assertEqual([sum(q["category"] == name for q in questions)
                          for name in ("procedural", "relational", "complex")], [5, 5, 10])

    def test_retrieval_metrics_do_not_claim_answer_accuracy(self):
        question = {"expected_source_pages": [6, 8], "expected_avoid_pages": [12]}
        result = {
            "answer": "ดูหน้า 6 และหน้า 99",
            "sources": [{"page": 6}, {"page": 12}],
            "avoid_exercises": [{"metadata": {"page_number": 12}}],
        }
        score = score_result(question, result)
        self.assertEqual(score["retrieval_coverage"], 0.5)
        self.assertEqual(score["avoid_recall"], 1.0)
        self.assertEqual(score["avoid_page_overlap"], [12])
        self.assertEqual(score["unsupported_cited_pages"], [99])
        self.assertNotIn("answer_accuracy", score)

    def test_numbered_step_after_newline_is_not_a_page_citation(self):
        question = {"expected_source_pages": [21], "expected_avoid_pages": []}
        result = {"answer": "ผลักไปด้านหน้า\n2. หายใจเข้า (หน้า 21)",
                  "sources": [{"page": 21}], "avoid_exercises": []}
        self.assertEqual(score_result(question, result)["unsupported_cited_pages"], [])

    def test_summary_counts_partial_results(self):
        questions = read_questions(ROOT / "evaluation" / "questions.json")
        rows = [{
            "question_id": "P01", "provider": "local", "mode": "dense", "status": "ok",
            "total_latency_ms": 1000, "retrieval_coverage": 1.0,
            "avoid_recall": None, "avoid_page_overlap": [],
            "unsupported_cited_pages": [], "usage": {"prompt_tokens": 20, "completion_tokens": 10},
        }]
        summary = summarize(rows, questions)
        self.assertEqual(summary["expected_full_run"], 120)
        self.assertEqual(summary["configurations"]["local+dense"]["completed_questions"], 1)

    def test_human_review_scores_survive_resummarize(self):
        rows = [{"question_id": "P01", "provider": "local", "mode": "dense", "status": "ok"}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "human_review.csv"
            update_human_review(path, rows)
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                original = list(csv.DictReader(handle))
            original[0]["human_accuracy_0_2"] = "2"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=original[0].keys())
                writer.writeheader()
                writer.writerows(original)
            update_human_review(path, rows)
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle))[0]["human_accuracy_0_2"], "2")

    def test_report_labels_incomplete_experiment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "summary.json").write_text(json.dumps({"configurations": {}}), encoding="utf-8")
            report = build_report(path)
        self.assertIn("ยังไม่ครบ 6 รูปแบบ", report)
        self.assertIn("0 / 20", report)
        self.assertIn("ห้ามสรุป", report)


if __name__ == "__main__":
    unittest.main()
