"""Tests for scripts/review_packages.py. Run: python3 scripts/test_review_packages.py (exit code = failures)."""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import review_check
import review_packages

TMP = tempfile.mkdtemp(prefix="fe-kit-packages-test-")
FAILURES = [0]
TOTAL = [0]


def check(name, got, want):
    TOTAL[0] += 1
    ok = got == want
    FAILURES[0] += not ok
    print(("OK  " if ok else "FAIL"), name + ("" if ok else "\n      got:  %r\n      want: %r" % (got, want)))


def report(verdict, finding, counts, rules, cover, gate="npm run typecheck exit 0"):
    return ("## Kết luận\n\n%s Một việc ở gói này.\n\n## Việc cần sửa\n\n%s\n\n## Tóm tắt\n\n"
            "Việc chặn đưa lên: %d. Việc nên sửa trong lượt này: %d. Việc có thể để sau: %d.\n\n"
            "## Nguồn và độ phủ\n\nLuật đã đọc: %s\nCổng: %s\nĐộ phủ: %s\n"
            % ((verdict, finding) + counts + (rules, gate, cover)))


def split_cases():
    small = ["src/a/%d.tsx" % n for n in range(10)]
    check("10 files or fewer: one package", review_packages.split(small), [sorted(small)])
    check("no files: no package", review_packages.split([]), [])
    files = ["src/a/%02d.tsx" % n for n in range(8)] + ["src/b/%02d.tsx" % n for n in range(8)] + ["src/c/x.tsx"]
    packages = review_packages.split(files, 15)
    check("folders stay whole when they fit", [len(p) for p in packages], [8, 9])
    check("every file lands in exactly one package", sorted(f for p in packages for f in p), sorted(files))
    big = ["src/big/%02d.tsx" % n for n in range(32)]
    check("one folder larger than max is cut in chunks", [len(p) for p in review_packages.split(big, 15)], [15, 15, 2])
    check("no package exceeds max", max(len(p) for p in review_packages.split(files + big, 15)) <= 15, True)
    try:
        review_packages.split(big, 0)
        got = "no error"
    except ValueError:
        got = "error"
    check("--max below 1 is an error, not a hang", got, "error")


def merge_cases():
    one = report("Sửa rồi hãy đưa.", "`a.tsx:3` lỗi A. Nên sửa trong lượt này.", (0, 1, 0), "web/rules/a.md, web/rules/b.md", "`src/a/` ✔")
    two = report("Không đưa lên.", "`b.tsx:9` lộ key. Nên sửa trước.", (1, 0, 1), "web/rules/b.md, web/rules/c.md", "`src/b/` ✔")
    merged = review_packages.merge([one, two])
    parts = review_check.sections(merged)
    check("worst verdict first", parts["Kết luận"][1].startswith("Không đưa lên."), True)
    check("each package conclusion kept, verdict word removed",
          "Gói 1: Một việc ở gói này." in parts["Kết luận"][1] and "Gói 2:" in parts["Kết luận"][1], True)
    check("findings of both packages kept", ("lỗi A" in merged, "lộ key" in merged), (True, True))
    check("counts come from merged paragraphs, not declared sums",
          "Việc chặn đưa lên: 1. Việc nên sửa trong lượt này: 1. Việc có thể để sau: 0." in merged, True)
    check("each finding names its lens", ("(Góc nhìn: Gói 1)" in merged, "(Góc nhìn: Gói 2)" in merged), (True, True))
    dup_a = report("Sửa rồi hãy đưa.", "`a.tsx:3` lỗi A. Nên sửa trong lượt này.", (0, 1, 0), "web/rules/a.md", "`src/a/` ✔")
    dup_b = report("Sửa rồi hãy đưa.", "`a.tsx:3` cũng lỗi này. Có thể để sau.", (0, 0, 1), "web/rules/b.md", "`src/a/` ✔")
    deduped = review_packages.merge([dup_a, dup_b])
    check("two lenses on one spot merge into one paragraph", deduped.count("`a.tsx:3`"), 2)
    check("the weaker level is folded, not kept", deduped.count("thể để sau"), 1)
    check("the merged paragraph names both sources", "(Góc nhìn: Gói 1, Gói 2)" in deduped, True)
    check("deduped count is one", "Việc nên sửa trong lượt này: 1." in deduped, True)
    lens_a = report("Sửa rồi hãy đưa.", "`a.tsx:5` lỗi A. Nên sửa trong lượt này.", (0, 1, 0), "không có luật dự án", "`src/a/` ✔")
    lens_b = report("Sửa rồi hãy đưa.", "`b.tsx:2` lỗi B. Nên sửa trong lượt này.", (0, 1, 0), "không có luật dự án", "`src/b/` ✔")
    lens_b = lens_b.replace("Luật đã đọc:", "Lens: correctness\nLuật đã đọc:")
    merged = review_packages.merge([lens_a, lens_b])
    check("a Lens: line names the lens instead of Gói", "(Góc nhìn: correctness)" in merged, True)
    merged = review_packages.merge([one, two])
    check("rules read is a union, no repeat",
          review_check.label_value(merged, "Luật đã đọc:"), "web/rules/a.md, web/rules/b.md, web/rules/c.md")
    check("coverage joined", review_check.label_value(merged, "Độ phủ:"), "`src/a/` ✔ · `src/b/` ✔")
    check("same gate written once", review_check.label_value(merged, "Cổng:"), "npm run typecheck exit 0")
    clean = report("Đưa được.", "", (0, 0, 0), "không có luật dự án", "`src/c/` ✔")
    merged = review_packages.merge([clean, clean])
    check("all clean stays Đưa được", review_check.sections(merged)["Kết luận"][1].startswith("Đưa được."), True)
    try:
        review_packages.merge(["## Việc cần sửa\n\nx\n"])
        got = "no error"
    except ValueError as exc:
        got = "package 1" in str(exc)
    check("package without verdict is an error", got, True)


    root = os.path.join(TMP, "repo")
    for path in ("src/a/a.tsx", "src/b/b.tsx"):
        os.makedirs(os.path.dirname(os.path.join(root, path)), exist_ok=True)
        with open(os.path.join(root, path), "w", encoding="utf-8") as handle:
            handle.write("x\n" * 10)
    one = report("Sửa rồi hãy đưa.", "`src/a/a.tsx:3` lỗi A. Nên sửa trong lượt này.", (0, 1, 0), "không có luật dự án", "`src/a/` ✔")
    two = report("Đưa được.", "", (0, 0, 0), "không có luật dự án", "`src/b/` ✔")
    errors, _ = review_check.check(root, review_packages.merge([one, two]), ["src/a/a.tsx", "src/b/b.tsx"])
    check("merged report passes review_check", errors, [])
    with open(os.path.join(root, "src/a/helpers.ts"), "w", encoding="utf-8") as handle:
        handle.write("x\n" * 200)
    short = report("Sửa rồi hãy đưa.", "`helpers.ts:3` lỗi A. Nên sửa trong lượt này.", (0, 1, 0), "không có luật dự án", "`src/a/` ✔")
    full = report("Sửa rồi hãy đưa.", "`src/a/helpers.ts:3` cũng lỗi này. Có thể để sau.", (0, 0, 1), "không có luật dự án", "`src/a/` ✔")
    deduped = review_packages.merge([short, full], root, ["src/a/helpers.ts"])
    check("a basename cite dedupes with the repo-relative cite",
          (deduped.count("(Góc nhìn:"), "(Góc nhìn: Gói 1, Gói 2)" in deduped, "cũng lỗi này" in deduped),
          (1, True, True))
    check("basename dedupe keeps one finding", "Việc nên sửa trong lượt này: 1." in deduped, True)
    undeduped = review_packages.merge([short, full])
    check("no root: a basename cite stays a separate finding", undeduped.count("(Góc nhìn:"), 2)



def cli_cases():
    script = os.path.join(HERE, "review_packages.py")
    paths = []
    for number in (1, 2):
        path = os.path.join(TMP, "p%d.md" % number)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(report("Đưa được.", "", (0, 0, 0), "không có luật dự án", "`src/x%d/` ✔" % number))
        paths.append(path)
    out = os.path.join(TMP, "merged.md")
    result = subprocess.run([sys.executable, "-I", script, "merge", "--out", out] + paths, capture_output=True, text=True, encoding="utf-8")
    check("CLI merge writes the file", (result.returncode, os.path.isfile(out)), (0, True))
    result = subprocess.run([sys.executable, "-I", script, "split", "--root", TMP, "--files"] + ["src/a/%d.tsx" % n for n in range(12)],
                            capture_output=True, text=True, encoding="utf-8")
    check("CLI split prints packages", (result.returncode, "packages: 1, files: 12" in result.stdout), (0, True))
    lensed = report("Đưa được.", "", (0, 0, 0), "không có luật dự án", "`src/a/` ✔").replace(
        "Luật đã đọc:", "Lens: hygiene\nLuật đã đọc:")
    lens_path = os.path.join(TMP, "lens.md")
    with open(lens_path, "w", encoding="utf-8") as handle:
        handle.write(lensed)
    result = subprocess.run([sys.executable, "-I", script, "merge", "--lens", "hygiene,correctness",
                             "--out", out, lens_path], capture_output=True, text=True, encoding="utf-8")
    check("merge warns when a lens report is missing",
          (result.returncode, "no report from lens correctness" in result.stderr), (0, True))
    result = subprocess.run([sys.executable, "-I", script, "merge", "--lens", "hygiene",
                             "--out", out, lens_path], capture_output=True, text=True, encoding="utf-8")
    check("merge quiet when every lens reported", result.stderr, "")
    result = subprocess.run([sys.executable, "-I", script, "merge", "--lens", "hygiene",
                             "--out", out] + paths, capture_output=True, text=True, encoding="utf-8")
    check("merge warns when no report carries a Lens line",
          "no report from lens hygiene" in result.stderr, True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        split_cases()
        merge_cases()
        cli_cases()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print("cases: %d, failures: %d" % (TOTAL[0], FAILURES[0]))
    sys.exit(FAILURES[0])
