"""Tests for scripts/review_record.py. Run: python3 scripts/test_review_record.py (exit code = failures)."""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "review_record.py")
sys.path.insert(0, HERE)
import review_record

TMP = tempfile.mkdtemp(prefix="fe-kit-record-test-")
FAILURES = [0]
TOTAL = [0]
REPORT = ("## Kết luận\n\nSửa rồi hãy đưa.\n\n## Việc cần sửa\n\n`a.tsx:3` lỗi A,\nhai dòng. Nên sửa trong lượt này.\n\n"
          "`b.tsx:9` lỗi B. Có thể để sau.\n\n## Tóm tắt\n\nViệc chặn đưa lên: 0.\n")


def check(name, got, want):
    TOTAL[0] += 1
    ok = got == want
    FAILURES[0] += not ok
    print(("OK  " if ok else "FAIL"), name + ("" if ok else "\n      got:  %r\n      want: %r" % (got, want)))


def run(*args):
    result = subprocess.run([sys.executable, "-I", SCRIPT] + list(args), capture_output=True, text=True, encoding="utf-8")
    return result.returncode, result.stdout, result.stderr


def git(root, *args):
    subprocess.run(["git", "-C", root, "-c", "user.email=t@example.invalid", "-c", "user.name=t"] + list(args),
                   capture_output=True, check=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        root = os.path.join(TMP, "repo")
        os.makedirs(root)
        git(root, "init", "-q", "-b", "feat/order-form")
        with open(os.path.join(root, "a.txt"), "w") as handle:
            handle.write("1\n")
        git(root, "add", ".")
        git(root, "commit", "-qm", "one")
        head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

        check("no record: base none", review_record.last(root), (None, []))
        code, out, _ = run("last", "--root", root)
        check("CLI last with no record exits 0", (code, out.strip()), (0, "base: none"))

        report = os.path.join(TMP, "r.md")
        with open(report, "w", encoding="utf-8") as handle:
            handle.write(REPORT)
        code, out, _ = run("save", "--root", root, "--report", report)
        check("save names the branch file, slash encoded", (code, out.strip()), (0, "saved: .fe-kit/reviews/feat%2Forder-form.md"))
        base, findings = review_record.last(root)
        check("last returns the saved head", base, head)
        check("last returns each finding paragraph", [f.split()[0] for f in findings], ["`a.tsx:3`", "`b.tsx:9`"])
        code, out, _ = run("last", "--root", root)
        check("CLI last prints base and one line per finding",
              (code, out.splitlines()[0] == "base: " + head, "finding 1: `a.tsx:3` lỗi A, hai dòng." in out), (0, True, True))

        review_record.save(root, REPORT, head="abc1234", branch="other")
        check("explicit branch and head", review_record.last(root, "other")[0], "abc1234")
        try:
            review_record.save(root, REPORT, head="not-a-sha")
            got = "no error"
        except review_record.RecordError:
            got = "error"
        check("a head that is not a sha is refused", got, "error")
        check("feat/x and feat-x keep separate records",
              review_record.record_path(root, "feat/x") != review_record.record_path(root, "feat-x"), True)

        with open(os.path.join(root, "a.txt"), "w") as handle:
            handle.write("2\n")
        code, _, err = run("save", "--root", root, "--report", report)
        check("save refuses while reviewed code is not committed", (code, "commit the reviewed code first" in err and "a.txt" in err), (2, True))
        code, _, _ = run("save", "--root", root, "--report", report, "--allow-dirty")
        check("--allow-dirty saves anyway", code, 0)
        git(root, "commit", "-qam", "two")
        code, _, _ = run("save", "--root", root, "--report", report)
        check("a record file alone does not block save", code, 0)

        sub = os.path.join(root, "web")
        os.makedirs(sub)
        with open(os.path.join(sub, "w.txt"), "w") as handle:
            handle.write("w\n")
        git(root, "add", ".")
        git(root, "commit", "-qm", "web")
        with open(os.path.join(root, "outside.txt"), "w") as handle:
            handle.write("x\n")
        first = run("save", "--root", sub, "--report", report)[0]
        second = run("save", "--root", sub, "--report", report)[0]
        check("sub-folder root: its own record and files outside it do not block save", (first, second), (0, 0))
        os.remove(os.path.join(root, "outside.txt"))
        git(root, "add", ".")
        git(root, "commit", "-qm", "records")

        git(root, "checkout", "-q", "--detach")
        code, _, err = run("last", "--root", root)
        check("detached HEAD asks for --branch", (code, "--branch" in err), (2, True))
        git(root, "checkout", "-q", "feat/order-form")

        with open(review_record.record_path(root, "broken"), "w", encoding="utf-8") as handle:
            handle.write("no header\n")
        code, _, err = run("last", "--root", root, "--branch", "broken")
        check("a record with no head line exits 2", (code, "head=" in err), (2, True))
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print("cases: %d, failures: %d" % (TOTAL[0], FAILURES[0]))
    sys.exit(FAILURES[0])
