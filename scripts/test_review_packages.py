"""Tests for review_packages.py: split grouping, merge verdict/dedupe, and the --lens warning."""
import io
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_check
import review_packages


def write(root, rel, text):
    path = os.path.join(root, rel)
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def report(lens, verdict, findings="", leave="", rules="không có luật dự án",
           gate="chưa chạy (task không gửi kết quả)", coverage="`a.ts` ✔",
           heading="## Việc cần sửa"):
    return ("# Kết quả review\n\n"
            "Lens: %s\n\n"
            "## Kết luận\n\n%s\n\n"
            "%s\n\n%s\n\n"
            "## Để yên\n\n%s\n\n"
            "## Nguồn và độ phủ\n\n"
            "Luật đã đọc: %s\nCổng: %s\nĐộ phủ: %s\n"
            % (lens, verdict, heading, findings, leave, rules, gate, coverage))


def findings_of(merged):
    body = "\n".join(review_check.sections(merged).get("Việc cần sửa", []))
    return [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]


def cite_candidates(texts):
    # The same candidate list main() builds from the reports.
    return sorted(set(match.group(1) for text in texts
                      for match in review_check.REF_RE.finditer(text)))


class Split(unittest.TestCase):
    def test_empty_gives_no_packages(self):
        self.assertEqual(review_packages.split([]), [])

    def test_at_or_below_threshold_is_one_package(self):
        files = ["src/%02d.ts" % number for number in range(10)]
        self.assertEqual(review_packages.split(files), [sorted(files)])

    def test_max_size_bounds_a_package(self):
        files = ["src/%02d.ts" % number for number in range(20)]
        packages = review_packages.split(files, maximum=15)
        self.assertEqual([len(package) for package in packages], [15, 5])
        self.assertEqual(sum(packages, []), sorted(files))

    def test_folder_stays_together_when_it_fits(self):
        files = (["a/%02d.ts" % number for number in range(8)]
                 + ["b/%02d.ts" % number for number in range(8)])
        packages = review_packages.split(files, maximum=16)
        self.assertEqual(len(packages), 1)
        packages = review_packages.split(files, maximum=10)
        self.assertEqual([len(package) for package in packages], [8, 8])
        self.assertTrue(all(path.startswith("a/") for path in packages[0]))

    def test_max_below_one_rejected(self):
        with self.assertRaises(ValueError):
            review_packages.split(["a.ts"] * 12, maximum=0)


class WorstVerdict(unittest.TestCase):
    def test_blocker_beats_clean(self):
        merged = review_packages.merge([
            report("a", "Đưa được."),
            report("b", "Không đưa lên."),
        ])
        conclusion = review_check.sections(merged)["Kết luận"]
        self.assertTrue(any(line.startswith("Không đưa lên.") for line in conclusion))

    def test_fix_first_beats_ship(self):
        merged = review_packages.merge([
            report("a", "Đưa được."),
            report("b", "Sửa rồi hãy đưa."),
            report("c", "Đưa được."),
        ])
        conclusion = review_check.sections(merged)["Kết luận"]
        self.assertTrue(any(line.startswith("Sửa rồi hãy đưa.") for line in conclusion))

    def test_missing_verdict_is_an_error(self):
        with self.assertRaises(ValueError):
            review_packages.merge([report("a", "Còn phải xem lại.")])


class SameSpotDedupe(unittest.TestCase):
    def test_identical_cite_merges_into_one_paragraph(self):
        merged = review_packages.merge([
            report("weaker", "Sửa rồi hãy đưa.",
                   "`a.ts:3` tên biến khó đọc. Nên sửa trong lượt này."),
            report("stronger", "Không đưa lên.",
                   "`a.ts:3` ném ngoại lệ khi rỗng. Nên sửa trước."),
        ])
        findings = findings_of(merged)
        self.assertEqual(len(findings), 1)
        paragraph = findings[0]
        self.assertIn("(Góc nhìn: weaker, stronger)", paragraph)
        self.assertIn("`a.ts:3` ném ngoại lệ khi rỗng. Nên sửa trước.", paragraph)
        self.assertIn("`a.ts:3` tên biến khó đọc.", paragraph)
        self.assertNotIn("Nên sửa trong lượt này", paragraph)
        summary = "\n".join(review_check.sections(merged)["Tóm tắt"])
        self.assertIn("Việc chặn đưa lên: 1.", summary)
        self.assertIn("Việc nên sửa trong lượt này: 0.", summary)


class MergeLensWarning(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        write(self.root, "a.ts", "const a = 1;\n")
        write(self.root, "r1.md", report("a", "Đưa được."))

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_lens_warns(self):
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = review_packages.main([
                "merge", "--root", self.root, "--files", "a.ts",
                "--lens", "a,b,c",
                "--out", os.path.join(self.root, "merged.md"),
                os.path.join(self.root, "r1.md"),
            ])
        self.assertEqual(code, 0)
        self.assertIn("warning: no report from lens b, c", err.getvalue())

    def test_all_lenses_present_no_warning(self):
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = review_packages.main([
                "merge", "--root", self.root, "--files", "a.ts",
                "--lens", "a",
                "--out", os.path.join(self.root, "merged.md"),
                os.path.join(self.root, "r1.md"),
            ])
        self.assertEqual(code, 0)
        self.assertEqual(err.getvalue(), "")


class MergeRegressions(unittest.TestCase):
    # regression: locks bugs B1, B3a, B3b — expected to fail until the fix lands.

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_cross_format_cite_dedupes(self):
        # B1: `helpers.ts:3` and `extensions/helpers.ts:3` cite the same spot.
        write(self.root, "extensions/helpers.ts", "export const h = 1;\n")
        texts = [
            report("contract", "Sửa rồi hãy đưa.",
                   "`helpers.ts:3` dùng tên sai. Nên sửa trong lượt này.",
                   coverage="`extensions/helpers.ts` ✔"),
            report("correctness", "Không đưa lên.",
                   "`extensions/helpers.ts:3` ném ngoại lệ. Nên sửa trước.",
                   coverage="`extensions/helpers.ts` ✔"),
        ]
        merged = review_packages.merge(texts, self.root, cite_candidates(texts))
        findings = findings_of(merged)
        self.assertEqual(len(findings), 1)
        self.assertIn("(Góc nhìn: contract, correctness)", findings[0])
        summary = "\n".join(review_check.sections(merged)["Tóm tắt"])
        self.assertIn("Việc chặn đưa lên: 1.", summary)

    def test_finding_without_cite_or_level_survives(self):
        # B3a: a finding is never silently dropped by the merge.
        texts = [
            report("deep", "Sửa rồi hãy đưa.",
                   "Luồng retry chạy hai lần khi mạng chập chờn."),
        ]
        merged = review_packages.merge(texts, self.root, cite_candidates(texts))
        self.assertIn("Luồng retry chạy hai lần khi mạng chập chờn", merged)

    def test_deeper_findings_heading_stays_out_of_conclusion(self):
        # B3b: `### Việc cần sửa` parses like `## Việc cần sửa`.
        write(self.root, "x.ts", "const x = 1;\n")
        texts = [
            report("deep", "Sửa rồi hãy đưa.",
                   "`x.ts:9` sai. Nên sửa trước.",
                   heading="### Việc cần sửa"),
        ]
        merged = review_packages.merge(texts, self.root, cite_candidates(texts))
        parts = review_check.sections(merged)
        self.assertIn("`x.ts:9`", "\n".join(parts.get("Việc cần sửa", [])))
        self.assertNotIn("`x.ts:9`", "\n".join(parts.get("Kết luận", [])))


if __name__ == "__main__":
    unittest.main()
