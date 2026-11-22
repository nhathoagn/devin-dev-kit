"""Tests for review_lenses.py: pass filtering, items/brief output, coverage gap."""
import io
import os
import re
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_lenses

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_list(*args):
    out = io.StringIO()
    with redirect_stdout(out):
        code = review_lenses.main(["list", *args])
    return code, out.getvalue()


class PassFilter(unittest.TestCase):
    def test_default_lists_pass_1(self):
        code, out = run_list()
        self.assertEqual(code, 0)
        names = re.findall(r"lens \d+: (\w+)", out)
        self.assertEqual(
            names,
            ["hygiene", "correctness", "contract", "security", "tests",
             "structure", "naming", "performance", "audit"],
        )

    def test_pass_2(self):
        _, out = run_list("--pass", "2")
        self.assertEqual(re.findall(r"lens \d+: (\w+)", out),
                         ["correctness", "contract", "probe", "invariant"])

    def test_invariants(self):
        _, out = run_list("--pass", "invariants")
        self.assertEqual(re.findall(r"lens \d+: (\w+)", out),
                         ["coverage", "regression"])

    def test_all_lists_every_lens(self):
        _, out = run_list("--pass", "all")
        self.assertIn("lenses: 13", out)

    def test_no_item_lens_prints_dash(self):
        _, out = run_list()
        self.assertIn("lens 9: audit", out)
        self.assertRegex(out, r"lens 9: audit .* items -")

    def test_brief_prints_brief_for_no_item_lens(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = review_lenses.main(["brief", "audit"])
        self.assertEqual(code, 0)
        self.assertIn("audit.md", out.getvalue())

    def test_brief_falls_back_to_title(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = review_lenses.main(["brief", "hygiene"])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), "Vệ sinh diff")

    def test_unknown_lens_exits_2(self):
        err = io.StringIO()
        stderr = sys.stderr
        sys.stderr = err
        try:
            code = review_lenses.main(["items", "nope"])
        finally:
            sys.stderr = stderr
        self.assertEqual(code, 2)
        self.assertIn("unknown lens", err.getvalue())


class Coverage(unittest.TestCase):
    def _checklist_items(self):
        items = set()
        for rel in ("skills/fe-kit/references/REVIEW_CHECKLIST.md",
                    "skills/fe-kit/references/review-checks.md"):
            with open(os.path.join(REPO, rel), encoding="utf-8") as handle:
                text = handle.read()
            for a, b in re.findall(r"\*\*([A-Z]+\d+)\*\*|^\|\s*([A-Z]+\d+)\s*\|",
                                   text, re.M):
                items.add(a or b)
        items -= {"L1", "L2", "L3"}
        return items

    def test_every_checklist_item_has_a_lens(self):
        missing, extra = review_lenses.coverage_gap(self._checklist_items())
        self.assertEqual(missing, [])
        self.assertEqual(extra, [])

    def test_no_item_in_two_lenses(self):
        items = review_lenses.all_items()
        self.assertEqual(len(items), len(set(items)))

    def test_pass_2_lenses_have_no_items(self):
        for lens in review_lenses.LENSES:
            if "invariants" in str(lens.get("pass")):
                self.assertEqual(lens["items"], [])


if __name__ == "__main__":
    unittest.main()
