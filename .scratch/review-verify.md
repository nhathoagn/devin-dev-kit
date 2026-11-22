Verdict: Đưa được — all 7 findings FIXED at HEAD.

| # | Status | Evidence |
|---|--------|----------|
| 1 | FIXED | `skills/fe-kit/SKILL.md` routing table has BOTH rows: line 22 `Clean up, shorten, or restructure existing code that is not UI → playbooks/cleanup.md`, line 23 `Fix or rewrite existing code whose diff then goes through lens review → playbooks/author-loop.md`. |
| 2 | FIXED | `grep -n "auto-review" CODEMAP.md README.md package.json` → zero hits (exit 2 no-match); `extensions/auto-review.ts` is `D` in `git status` and absent from the file lists read. |
| 3 | FIXED | `scripts/review_packages.py` ~line 223: `if args.lens:` block computes `named = {review_check.label_value(text, "Lens:") …}` and warns unconditionally — `if any(named)` guard gone. New test at `test_review_packages.py:142` "merge warns when no report carries a Lens line" prints OK. `python3 scripts/test_review_packages.py` → `cases: 31, failures: 0`. |
| 4 | FIXED | `scripts/review_packages.py` lines ~218-221: `candidates = sorted(set(REF_RE finds))`, then `candidates = sorted(set(candidates) \| set(scope["files"]) \| {item["path"] for item in scope["read"]})` — set union, no duplicate candidates. Tests "a basename cite dedupes with the repo-relative cite" and "basename dedupe keeps one finding" OK. `cases: 31, failures: 0`. |
| 5 | FIXED | `SKILL.md` line 8 reads "…frontend work … and before cleaning up or restructuring non-UI source code" — no longer frontend-only. Line 29: "prints the eight lenses — six walk checklist items … `probe` and `invariant` belong to the second pass" and pins `review-<lens>.md` (`.scratch/` else `/tmp/`). Line ~34: `merge --root <repo> --diff <range> --out <file> … — adding --lens <a,b,…> when the fan-out was by lens`. |
| 6 | FIXED | `skills/fe-kit/CHANGELOG.md` line 12 now names `BASH_EXT`/`BASH_EXT_MENTION_RE` in `scripts/bash_target.py` (real names confirmed at `bash_target.py:12,15`) and says "The five playbook gate lines" — exactly five found (cleanup.md:16, fix-bug.md:28, new-ui.md:13, perf-ui.md:12, refactor-ui.md:14). |
| 7 | FIXED | `ls "Pasted"*.textClipping` / `ls *.textClipping` at repo root → No such file or directory; no `.textClipping` entry in `git status`. |

Test run (findings 3, 4): `python3 scripts/test_review_packages.py` → last line `cases: 31, failures: 0` — all 31 cases OK including "merge warns when no report carries a Lens line", "merge warns when a lens report is missing", "a basename cite dedupes with the repo-relative cite".

Observation (not a merged finding, reported for the record): `README.md:299` still says `scripts/review_lenses.py` "chia review thành sáu góc nhìn" (six lenses) while `SKILL.md` and `review_lenses.py` now describe eight — the same stale-count class as finding 5, in a file that finding covered only for the auto-review mention.
