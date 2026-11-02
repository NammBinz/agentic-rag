"""Draft evaluation set integrity and proxy scorer behaviour."""
import importlib.util
import unittest
from pathlib import Path

from agentic_rag.catalog import Catalog

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EvalSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = load("build_eval_set")
        cls.items = cls.build.build(0.3, 37)

    def test_ids_unique_and_split_stable(self):
        ids = [i["id"] for i in self.items]
        self.assertEqual(len(ids), len(set(ids)))
        again = {i["id"]: i["split"] for i in self.build.build(0.3, 37)}
        self.assertEqual(again, {i["id"]: i["split"] for i in self.items})
        self.assertTrue({"dev", "test"} <= {i["split"] for i in self.items})

    def test_gold_sources_exist_and_items_are_draft(self):
        chunk_ids = {c["id"] for c in Catalog("project", None, "K37").chunks}
        for item in self.items:
            self.assertEqual(item["review_status"], "draft")
            self.assertTrue(set(item["gold_sources"]) <= chunk_ids, item["id"])

    def test_blank_prerequisite_forbids_no_prerequisite_claim(self):
        blank = [i for i in self.items if i["group"] == "blank_prerequisite"]
        self.assertTrue(blank)
        for item in blank:
            self.assertIn("không có tiên quyết", item["gold_forbidden_terms"])


class ScorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.score = load("score_experiment")

    def run_row(self, status, answer, gold, citations=()):
        return self.score.score_run({"id": "X", "mode": "agent", "group": "g", "run_status": "completed", "gold": gold,
                                     "result": {"status": status, "answer": answer, "metrics": {},
                                                "citations": [{"id": c} for c in citations]}})

    def test_numbers_match_on_word_boundary(self):
        self.assertTrue(self.score.contains("co 12 ma", "12"))
        self.assertFalse(self.score.contains("ma 112", "12"))
        self.assertTrue(self.score.contains("IT320 có 3 tín chỉ", "3 tín chỉ"))

    def test_terms_sources_and_outcome_lists(self):
        gold = {"gold_outcome": ["answer", "abstain"], "gold_required_terms": [["CS122"], ["4,0", "4.0"]],
                "gold_forbidden_terms": ["không có tiên quyết"], "gold_sources": ["COURSE-IT320"]}
        row = self.run_row("insufficient_data", "Cần CS122, điểm 4.0", gold, ["COURSE-IT320", "GAP-G05"])
        self.assertTrue(row["outcome_ok"])
        self.assertEqual(row["term_recall"], 1.0)
        self.assertEqual(row["citation_precision"], 0.5)
        self.assertFalse(row["forbidden_hit"])
        self.assertTrue(self.run_row("answered", "Không có tiên quyết", gold)["forbidden_hit"])

    def test_negated_forbidden_phrase_is_not_a_violation(self):
        self.assertFalse(self.score.asserts("Ô trống, không thể kết luận là không có tiên quyết.", "không có tiên quyết"))
        self.assertTrue(self.score.asserts("AD242 không có tiên quyết.", "không có tiên quyết"))

    def test_refuse_accepts_clarifying_question(self):
        self.assertTrue(self.run_row("needs_input", "Chọn khóa", {"gold_outcome": "refuse"})["outcome_ok"])
        self.assertFalse(self.run_row("catalog_summary", "45 mã", {"gold_outcome": "refuse"})["outcome_ok"])
