import json
import unittest

from pairblind.score import compare_endpoints, grade_blind, habit_report
from pairblind.stats import js_divergence, mcnemar
from collections import Counter


class GradeTests(unittest.TestCase):
    def test_sum_ignores_words(self):
        task = {"kind": "sum", "expect": 10902410}
        self.assertTrue(grade_blind(task, "10902410", "n"))
        self.assertFalse(grade_blind(task, "10902411", "n"))

    def test_nonce_must_be_exact(self):
        task = {"kind": "contains_nonce"}
        self.assertTrue(grade_blind(task, "ab12", "ab12"))
        self.assertFalse(grade_blind(task, "the nonce is ab12", "ab12"))

    def test_json_keys(self):
        task = {"kind": "json_keys", "keys": ["bird", "count"], "count": 3}
        self.assertTrue(grade_blind(task, '{"bird":"wren","count":3}', "n"))
        self.assertFalse(grade_blind(task, '{"bird":"wren","count":3,"extra":1}', "n"))
        self.assertFalse(grade_blind(task, "not json", "n"))


class StatTests(unittest.TestCase):
    def test_identical_distributions_are_near_zero(self):
        left = Counter({"43": 29, "47": 1})
        self.assertLess(js_divergence(left, left), 1e-9)

    def test_disjoint_is_large(self):
        left = Counter({"43": 30})
        right = Counter({"叮": 30})
        # Prior 0.5 on two singleton alphabets caps JS below 1 bit.
        self.assertGreater(js_divergence(left, right), 0.85)

    def test_mcnemar_no_discordance(self):
        self.assertEqual(mcnemar(10, 0, 0)["p"], 1.0)

    def test_mcnemar_one_sided_split_is_small(self):
        result = mcnemar(0, 8, 0)
        self.assertLess(result["p_two_sided"], 0.01)

    def test_habit_report_does_not_invent_identity(self):
        rows = [
            {"kind": "habit", "probe_id": "int-19-71", "ok": True, "text": "43"},
            {"kind": "habit", "probe_id": "int-19-71", "ok": True, "text": "43"},
            {"kind": "habit", "probe_id": "int-19-71", "ok": False, "text": ""},
        ]
        report = habit_report(rows)
        self.assertIn("not model identity", report["warning"])
        self.assertEqual(report["habit"]["int-19-71"]["n"], 2)
        self.assertEqual(report["habit"]["int-19-71"]["mode_share"], 1.0)

    def test_compare_pairs_on_nonce(self):
        left = [
            {"kind": "blind", "task_id": "add", "nonce": "aa", "ok": True, "passed": True},
            {"kind": "blind", "task_id": "add", "nonce": "bb", "ok": True, "passed": False},
        ]
        right = [
            {"kind": "blind", "task_id": "add", "nonce": "aa", "ok": True, "passed": False},
            {"kind": "blind", "task_id": "add", "nonce": "bb", "ok": True, "passed": False},
        ]
        report = compare_endpoints(left, right)
        self.assertEqual(report["paired_blind"]["only_left"], 1)
        self.assertEqual(report["paired_blind"]["only_right"], 0)
        blob = json.dumps(report)
        self.assertNotIn("identity probability", blob)


if __name__ == "__main__":
    unittest.main()
