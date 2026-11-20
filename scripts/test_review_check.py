"""Tests for scripts/review_check.py. Run: python3 scripts/test_review_check.py (exit code = failures).

Each case writes a report for a small repo and checks the exit code and the error text.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "review_check.py")
TMP = tempfile.mkdtemp(prefix="fe-kit-review-check-")
ROOT = os.path.join(TMP, "repo")
FILES = {
    "src/order/OrderForm.tsx": "".join("line %d\n" % n for n in range(1, 21)),
    "src/order/use-order.ts": "a\nb\nc\n",
    "src/lib/price.ts": "x\ny\n",
    "docs/order.md": "# Order\n- address is required\n",
    "web/rules/forms.md": "rule\n",
    "web/src/routeTree.gen.ts": "gen\n",
    ".fe-kit/config.yaml": ("rules:\n  - glob: \"src/**\"\n    read: [web/rules/forms.md]\nexclude: [\"web/src/routeTree.gen.ts\"]\n"
                            "presets: [legacy-rewrite]\n"
                            "legacy:\n  source: ./dev\n  cr: \"works/screens/{SID}.yaml\"\n"),
    "dev/OrderEntry.java": "a\nb\n",
    "works/screens/S1.yaml": "sid: S1\n",
    "src/cart/OrderForm.tsx": "x\n",
    "sp ace.ts": "x\n",
}
DIFF = ["src/order/OrderForm.tsx", "src/order/use-order.ts", "web/src/routeTree.gen.ts"]

SCOPE = ("## Nguồn và độ phủ\n\n"
         "Luật đã đọc: web/rules/forms.md\n"
         "Cổng: npm run typecheck exit 0\n"
         "Độ phủ: src/order/OrderForm.tsx ✔ · src/order/use-order.ts ✔\n")
FIX_NOW = ("## Kết luận\n\nSửa rồi hãy đưa. Một việc trong lượt này.\n\n"
           "## Việc cần sửa\n\n`OrderForm.tsx:12` bỏ lỗi submit. Nên sửa trong lượt này.\n\n")
SUMMARY = "## Tóm tắt\n\nViệc chặn đưa lên: 0. Việc nên sửa trong lượt này: 1. Việc có thể để sau: 0.\n\n"

CASES = [
    ("valid report passes", FIX_NOW + SUMMARY + SCOPE, 0, []),
    ("clean verdict passes even with level words in Tóm tắt",
     "## Kết luận\n\nĐưa được. Không còn việc phải sửa.\n\n" + SUMMARY.replace(": 1.", ": 0.") + SCOPE, 0, []),
    ("missing Kết luận", "## Việc cần sửa\n\n`OrderForm.tsx:1` x. Nên sửa trong lượt này.\n\n" + SCOPE, 1, ["missing `## Kết luận`"]),
    ("verdict word not first", "## Kết luận\n\nBáo cáo: Đưa được.\n\n" + SCOPE, 1, ["must start with"]),
    ("Đưa được with a must-fix finding",
     "## Kết luận\n\nĐưa được.\n\n## Việc cần sửa\n\n`OrderForm.tsx:3` x. Nên sửa trước.\n\n" + SCOPE, 1, ["verdict `Đưa được`"]),
    ("Sửa rồi hãy đưa with a blocker",
     "## Kết luận\n\nSửa rồi hãy đưa.\n\n## Việc cần sửa\n\n`OrderForm.tsx:3` x. Nên sửa trước.\n\n" + SCOPE, 1, ["use `Không đưa lên`"]),
    ("Không đưa lên with no blocker",
     "## Kết luận\n\nKhông đưa lên.\n\n## Việc cần sửa\n\n`OrderForm.tsx:3` x. Có thể để sau.\n\n" + SCOPE, 1, ["no finding that says `nên sửa trước`"]),
    ("missing Cổng", FIX_NOW + SCOPE.replace("Cổng: npm run typecheck exit 0\n", ""), 1, ["missing `Cổng:`"]),
    ("empty Luật đã đọc", FIX_NOW + SCOPE.replace("Luật đã đọc: web/rules/forms.md", "Luật đã đọc:"), 1, ["missing `Luật đã đọc:`"]),
    ("coverage misses a diff file", FIX_NOW + SCOPE.replace(" · src/order/use-order.ts ✔", ""), 1, ["Độ phủ does not name: src/order/use-order.ts"]),
    ("coverage by folder prefix", FIX_NOW + SCOPE.replace("src/order/OrderForm.tsx ✔ · src/order/use-order.ts ✔", "src/order/ ✔"), 0, []),
    ("coverage by base name", FIX_NOW + SCOPE.replace("src/order/OrderForm.tsx", "OrderForm.tsx"), 0, []),
    ("excluded file need not be covered", FIX_NOW + SCOPE, 0, []),
    ("line past end of file", FIX_NOW.replace("OrderForm.tsx:12", "OrderForm.tsx:21") + SCOPE, 1, ["outside the file (20 lines)"]),
    ("range past end", FIX_NOW.replace("OrderForm.tsx:12", "OrderForm.tsx:18-25") + SCOPE, 1, ["outside the file"]),
    ("unknown file", FIX_NOW.replace("OrderForm.tsx:12", "Missing.tsx:2") + SCOPE, 1, ["not in the repo or the diff"]),
    ("caller outside the diff warns only", FIX_NOW + "`src/lib/price.ts:2` gãy vì hook đổi kiểu. Nên sửa trong lượt này.\n\n" + SCOPE,
     0, ["! `src/lib/price.ts:2` is outside the diff"]),
    ("spec line does not warn", FIX_NOW + "`docs/order.md:2` yêu cầu địa chỉ.\n\n" + SCOPE, 0, ["0 warnings"]),
    ("a built-in preset rule cited by its relative path", FIX_NOW + "`presets/legacy-rewrite/review.md:8` đòi trích dòng hệ cũ.\n\n" + SCOPE,
     0, ["0 errors, 0 warnings"]),
    ("old-system and CR lines do not warn", FIX_NOW +"`dev/OrderEntry.java:2` kiểm độ dài trước. `works/screens/S1.yaml:1` không có CR.\n\n" + SCOPE,
     0, ["0 warnings"]),
    ("a line of a file the diff deleted warns, no crash", FIX_NOW + "`src/order/removed.ts:4` export bị xoá.\n\n"
     + SCOPE.replace(" · src/order/use-order.ts ✔", " · src/order/use-order.ts ✔ · src/order/removed.ts ✔"),
     0, ["! `src/order/removed.ts:4` names a file the diff deleted"]),
]
# Each case runs against DIFF; the deleted-file case adds a diff file that is not on disk.
EXTRA_DIFF = {"a line of a file the diff deleted warns, no crash": ["src/order/removed.ts"]}


def setup():
    for path, text in FILES.items():
        full = os.path.join(ROOT, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)


def run(report, diff=None):
    path = os.path.join(TMP, "report.md")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(report)
    result = subprocess.run([sys.executable, "-I", SCRIPT, "--root", ROOT, "--report", path, "--files"] + (diff or DIFF),
                            capture_output=True, text=True, encoding="utf-8")
    return result.returncode, result.stdout + result.stderr


def main():
    failures = 0
    for name, report, want_code, needles in CASES:
        code, out = run(report, DIFF + EXTRA_DIFF.get(name, []))
        ok = code == want_code and all(needle in out for needle in needles)
        failures += not ok
        print(("OK  " if ok else "FAIL"), name + ("" if ok else "  (exit %d)\n%s" % (code, out)))
    code, out = subprocess.run([sys.executable, "-I", SCRIPT, "--root", ROOT, "--report", os.path.join(TMP, "none.md"),
                                "--files", "a.tsx"], capture_output=True, text=True, encoding="utf-8").returncode, ""
    ok = code == 2
    failures += not ok
    print(("OK  " if ok else "FAIL"), "missing report file exits 2")
    # Two diff files named OrderForm.tsx: the bare name covers neither.
    code, out = run(FIX_NOW + SCOPE.replace("src/order/OrderForm.tsx", "OrderForm.tsx"),
                    DIFF + ["src/cart/OrderForm.tsx"])
    ok = code == 1 and "Độ phủ does not name: src/order/OrderForm.tsx, src/cart/OrderForm.tsx" in out
    failures += not ok
    print(("OK  " if ok else "FAIL"), "a bare name shared by two diff files covers neither" + ("" if ok else "  (exit %d)\n%s" % (code, out)))
    # A root file whose name holds a space, and a renamed file's old name that no longer exists.
    code, out = run(FIX_NOW + SCOPE.replace("src/order/use-order.ts ✔", "src/order/use-order.ts ✔ · `sp ace.ts` ✔"),
                    DIFF + ["sp ace.ts", "src/order/old-name.ts"])
    ok = code == 0
    failures += not ok
    print(("OK  " if ok else "FAIL"), "a name with a space is covered; an old name is not required" + ("" if ok else "  (exit %d)\n%s" % (code, out)))
    code, out = run(FIX_NOW + SCOPE.replace("src/order/OrderForm.tsx ✔", "src/order/OrderForm.ts ✔"))
    ok = code == 1 and "Độ phủ does not name: src/order/OrderForm.tsx" in out
    failures += not ok
    print(("OK  " if ok else "FAIL"), "`OrderForm.ts` does not cover `OrderForm.tsx`" + ("" if ok else "  (exit %d)\n%s" % (code, out)))
    print("cases: %d, failures: %d" % (len(CASES) + 4, failures))
    return failures


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        setup()
        result = main()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(result)
