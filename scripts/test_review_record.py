"""Tests for review_record.py: save refuses dirty work, branch paths, and the last-read."""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_record

REPORT = """# Kết quả review

## Kết luận

Sửa rồi hãy đưa.

## Việc cần sửa

`a.ts:1` tên biến khó đọc. Nên sửa trong lượt này.

`a.ts:7` thiếu kiểm tra rỗng. Nên sửa trước.
"""


def run(*args):
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = review_record.main(list(args))
    return code, out.getvalue(), err.getvalue()


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        self.write("a.ts", "const a = 1;\n")
        self.git("add", "a.ts")
        self.git("commit", "-m", "init")
        self.head = self.git("rev-parse", "HEAD")
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        self.report = os.path.join(outside.name, "report.md")
        with open(self.report, "w", encoding="utf-8") as handle:
            handle.write(REPORT)

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        result = subprocess.run(["git", "-C", self.root] + list(args),
                                capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def _save(self, *extra):
        return run("save", "--root", self.root, "--report", self.report, *extra)


class Save(Repo):
    def test_clean_save_writes_record(self):
        code, out, _ = self._save()
        self.assertEqual(code, 0)
        self.assertIn("saved: .fe-kit/reviews/main.md", out.replace("\\", "/"))

    def test_uncommitted_file_refused(self):
        self.write("b.ts", "const b = 1;\n")
        code, _, err = self._save()
        self.assertEqual(code, 2)
        self.assertIn("Not committed: b.ts", err)

    def test_allow_dirty_overrides(self):
        self.write("b.ts", "const b = 1;\n")
        code, out, _ = self._save("--allow-dirty")
        self.assertEqual(code, 0)
        self.assertIn("saved:", out)

    def test_record_folder_is_not_dirty(self):
        code, _, _ = self._save()
        self.assertEqual(code, 0)
        code, _, err = self._save()
        self.assertEqual(code, 0, err)

    def test_detached_head_requires_branch(self):
        self.git("checkout", "--detach", "HEAD")
        code, _, err = self._save("--allow-dirty")
        self.assertEqual(code, 2)
        self.assertIn("HEAD is detached", err)
        code, out, _ = self._save("--allow-dirty", "--branch", "main")
        self.assertEqual(code, 0)
        self.assertIn("saved:", out)

    def test_slash_branch_percent_encodes(self):
        code, out, _ = self._save("--branch", "feat/x")
        self.assertEqual(code, 0)
        self.assertIn("saved: .fe-kit/reviews/feat%2Fx.md", out.replace("\\", "/"))
        path = os.path.join(self.root, ".fe-kit", "reviews", "feat%2Fx.md")
        self.assertTrue(os.path.isfile(path))


class Last(Repo):
    def test_no_record_prints_none(self):
        code, out, _ = run("last", "--root", self.root)
        self.assertEqual(code, 0)
        self.assertIn("base: none", out)

    def test_prints_base_and_findings(self):
        code, _, _ = self._save()
        self.assertEqual(code, 0)
        code, out, _ = run("last", "--root", self.root)
        self.assertEqual(code, 0)
        self.assertIn("base: %s" % self.head, out)
        self.assertIn("finding 1: `a.ts:1` tên biến khó đọc. Nên sửa trong lượt này.", out)
        self.assertIn("finding 2: `a.ts:7` thiếu kiểm tra rỗng. Nên sửa trước.", out)


class SaveRegressions(Repo):
    # regression: locks bugs B4a, B4b — expected to fail until the fix lands.

    def test_head_not_in_repo_refused(self):
        # B4a: --head must name a commit that exists in the repo.
        code, _, err = self._save("--head", "cafebabecafebabecafebabecafebabecafebabe",
                                  "--allow-dirty")
        self.assertEqual(code, 2)
        self.assertIn("cafebabe", err)

    def test_head_still_refuses_dirty(self):
        # B4b: --head does not skip the uncommitted-files check.
        self.write("b.ts", "const b = 1;\n")
        code, _, err = self._save("--head", self.head)
        self.assertEqual(code, 2)
        self.assertIn("Not committed: b.ts", err)


if __name__ == "__main__":
    unittest.main()
