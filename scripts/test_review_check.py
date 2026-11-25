"""Tests for review_check.py: verdict/level consistency and the outside-diff warning."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_check


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


REPORT_HEAD = """# Kết quả review

## Kết luận

Sửa rồi hãy đưa. Một việc nên sửa trong lượt này.

## Việc cần sửa

`%s:1` đang sai. Nên sửa trong lượt này.

## Nguồn và độ phủ

Luật đã đọc: không có luật dự án
Cổng: chưa chạy (task không gửi kết quả)
Độ phủ: `a.ts` ✔
"""


class ImportContext(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        write(self.root, "src/a.ts",
              'import { helper } from "./lib/helper.ts";\nexport const x = helper();\n')
        write(self.root, "src/lib/helper.ts", "export function helper() { return 1; }\n")
        write(self.root, "src/other.ts", "export const y = 2;\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _check(self, report):
        return review_check.check(self.root, report, ["src/a.ts"])

    def test_imported_file_is_not_a_warning(self):
        errors, warnings = self._check(REPORT_HEAD % "src/lib/helper.ts")
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_unrelated_file_warns(self):
        errors, warnings = self._check(REPORT_HEAD % "src/other.ts")
        self.assertEqual(errors, [])
        self.assertTrue(any("outside the diff" in w for w in warnings))

    def test_missing_file_is_an_error(self):
        errors, _ = self._check(REPORT_HEAD % "src/ghost.ts")
        self.assertTrue(any("not in the repo" in e for e in errors))


class VerdictConsistency(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        write(self.root, "a.ts", "const a = 1;\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _report(self, verdict, body):
        return ("# Kết quả review\n\n## Kết luận\n\n%s\n\n## Việc cần sửa\n\n%s\n"
                "## Nguồn và độ phủ\n\nLuật đã đọc: x\nCổng: x\nĐộ phủ: `a.ts` ✔\n"
                % (verdict, body))

    def test_ship_with_open_blocker_fails(self):
        errors, _ = review_check.check(
            self.root, self._report("Đưa được.", "`a.ts:1` lỗi. Nên sửa trước."),
            ["a.ts"])
        self.assertTrue(any("Đưa được" in e for e in errors))

    def test_clean_verdict_passes(self):
        errors, _ = review_check.check(
            self.root, self._report("Đưa được. Không còn việc phải sửa.", ""),
            ["a.ts"])
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
