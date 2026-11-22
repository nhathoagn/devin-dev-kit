# Handoff — fe-kit 1.38.0: merge dedupe fix + gate widening + cleanup playbook

## 1. Logic

Bốn nhóm thay đổi, một mục tiêu: non-UI code review path đầy đủ như UI.

**(a) Merge dedupe + lens warn** — `review_packages.py merge` trước đây chỉ gộp findings theo raw string `file:line`: `helpers.ts:183` và `extensions/helpers.ts:183` thành 2 paragraph dù cùng một chỗ. Giờ `merge` có `--root`, `--files`/`--diff`/`--staged`, `--lens`: mọi cite path đi qua `review_check._resolve_ref` (basename → repo-relative duy nhất hoặc giữ nguyên raw), `--lens a,b,…` warn stderr khi lens nào không ghi report — kể cả khi report không có dòng `Lens:` (khi đó mọi lens expected đều "missing").

**(b) Gate mở rộng** — `GATED_EXT_RE` trước chỉ JS-family (`.tsx/.jsx/.js/.mjs/.cjs/.vue/.svelte/.astro/.mdx`). Edit `.ts` hay `.py` không cần declare `Runtime owner:`/`Decision:`. Giờ bằng `source_hit` list (thêm `.ts/.py/.go/.rs/.java/.kt/.kts/.rb/.php/.cs/.swift`). `wording.py` chỉ có lexer JS → edit non-JS **fail-closed**: gated, không exempt. `bash_target.py` nới tương ứng để `echo x > a.py`/`sed -i a.ts` cũng bị chặn.

**(c) Checklist** — `REVIEW_CHECKLIST.md` N2: nesting >2 FAIL khi nhánh đặc biệt viết được guard clause; >4 vẫn FAIL bất kể. `review-checks.md` thêm F24: loop tay = 1 biến đổi `filter`/`map`/`reduce`/`find`/`some`/`every` → FAIL khi pipeline ngắn và rõ hơn. F24 thuộc lens `structure`.

**(d) Playbook mới** — `cleanup.md` cho task "dọn/gọn code không phải UI". Route: `SKILL.md` table + skip rule + frontmatter. Verify thay screen-capture bằng test module hoặc throwaway harness snapshot output trước/sau.

## 2. Implementation

- `scripts/review_packages.py:71` `_ref_key` — nhận `root`/`candidates`, gọi `review_check._resolve_ref` normalize path trước khi làm dedupe key.
- `scripts/review_packages.py:83` `_merge_findings` — thread root/candidates xuống `_ref_key`.
- `scripts/review_packages.py:128` `merge` — signature `(reports, root=None, candidates=())` backward-compat.
- `scripts/review_packages.py:212-229` — CLI merge: `--root` default `.`, `add_source_arguments`, `--lens`; candidates = union cite paths ∪ diff files ∪ read files (set, không dup — dup làm `_resolve_ref` trả None); `--lens` warn unconditionally.
- `scripts/fe-gate.py:652`, `scripts/devin_gate.py:205` `GATED_EXT_RE` — full source_hit list.
- `scripts/bash_target.py:12-15` `BASH_EXT`/`BASH_EXT_MENTION_RE`/`FRONTEND_RE` — cùng list.
- `scripts/review_lenses.py:37` — structure lens +F24.
- `scripts/test_review_packages.py:100-109` — basename dedupe cases; `:127-143` — `--lens` warn/missing/Lens-less cases.
- `scripts/test_fe_gate.py:149,259,389-392`, `test_devin_gate.py:93-96,129-132` — `.ts`/`.py` giờ expect deny.
- `skills/fe-kit/playbooks/cleanup.md` — file mới; shape theo `refactor-ui.md`.
- `skills/fe-kit/SKILL.md:8,22-23,29,34,38` — scope line, 2 routing rows, 8-lens + pinned report path + `--lens` merge, skip rule.
- `skills/fe-kit/playbooks/author-loop.md:10-11`, `review-diff.md:11,14` — pinned `review-<lens>.md` + `--lens` merge.
- `skills/fe-kit/playbooks/{fix-bug,new-ui,perf-ui,refactor-ui}.md` — gate line list ext đầy đủ.
- `skills/fe-kit/references/REVIEW_CHECKLIST.md:58` N2; `review-checks.md:30` F24.
- `skills/fe-kit/CHANGELOG.md:3-13` — entry 1.38.0; `evals.json`, `README.md`, `CODEMAP.md` — counts F1–F24 / 8 playbooks / 8 lenses; xóa mention `auto-review.ts` đã mất.
- `.claude-plugin/plugin.json`, `.devin-plugin/plugin.json`, `package.json`, `.claude-plugin/marketplace.json` ×2 — `1.38.0`.

State holders: `merged`/`seen` dict trong `_merge_findings` (key = `(resolved_path, line)`); `candidates` list trong merge CLI; không có state khác.

## 3. Decisions

- **Dedupe theo cite đầu tiên thôi**: một finding có thể cite nhiều `file:line`; chỉ ref đầu làm key — đúng convention report (câu đầu chứa spot chính). Ambiguous basename (2 file cùng tên khác folder) → `_resolve_ref` trả None → giữ raw key, merge vẫn có thể nhầm nếu hai package cite cùng basename — deferred, edge hiếm.
- **`--lens` warn unconditionally**: trước có `if any(named)` — trường hợp không report nào có `Lens:` line (đúng bug cần bắt) lại im lặng. Giờ thiếu `Lens:` = mọi expected đều missing.
- **Fail-closed non-JS**: không viết lexer mới cho `.py/.go` — wording_exempt trả False → gated. Cost: mọi edit `.py` cần declare, kể cả typo comment (`.py` không có dialect → không wording-exempt được). Chấp nhận vì consistency; nếu ồn thì thêm dialect sau.
- **`.ts` gated**: `.ts` vốn source_hit nhưng bị loại khỏi gated — giờ gated luôn. Test pin "allow" đã flip.
- **N2 >2 chỉ khi guard-able**: judgement có điều kiện, không phải smell thuần — giữ checklist ở mức testable ("viết được thành guard clause" là câu hỏi trả lời được).
- **Cleanup.md verify = tests hoặc harness**: không có screen cho non-UI; snapshot output exported functions là tương đương byte-for-byte gần nhất.
- **`auto-review.ts` mentions xóa**: file đã mất trong working tree (session trước) và khỏi `omp.extensions` — docs không mô tả file không tồn tại.

## 4. Debug without AI

- **Reproduce basename dedupe fail**: hai report cite `helpers.ts:3` và `src/a/helpers.ts:3` cùng một lỗi → `python3 scripts/review_packages.py merge --root <repo> --out /tmp/m.md r1.md r2.md` → mở `/tmp/m.md`: 2 paragraph thay vì 1 với `(Góc nhìn: A, B)`.
- **Watch**: `scripts/review_packages.py:71` `_ref_key` — print `(path, resolved, key)`; `review_check.py:45` `_resolve_ref` — print `hits` list; >1 hit = ambiguous → None → raw key.
- **`--lens` warn không bắn**: `merge --lens a,b --out x.md r1.md` với r1 thiếu `Lens:` line → stderr phải có `no report from lens a, b` (và b). Im lặng = `named` set lọc sai — check `label_value` có match `Lens:` ở đầu dòng không.
- **Gate `.py` mở thoải mái**: edit `.py` không label mà không bị deny → `GATED_EXT_RE` (`fe-gate.py:652`) thiếu ext hoặc `gated_view` điều kiện khác short-circuit trước — print `gated_view` components.
- **`git add x.py` bị deny nhầm**: `bash_target.write_target` trả target cho `git add` → `BASH_EXT` ăn `.py` trong path của git add — check `write_target_in` có nhảy vào nhánh targets cho lệnh không phải write không; `git` là read-only command — check `READ_ONLY_COMMANDS`/command detection.
- **Verify fix**: `python3 scripts/test_review_packages.py` (merge), `test_fe_gate.py` + `test_devin_gate.py` + `test_bash_target.py` (gate widening), `test_review_check.py`, `test_versions.py`. Tất cả = `failures: 0`.
- **Rollback**: `git checkout -- scripts/review_packages.py scripts/fe-gate.py scripts/devin_gate.py scripts/bash_target.py scripts/test_*.py` rollback phần code đang chạy; docs/playbook rollback riêng (`git checkout -- skills/`).

## 5. Risks and open items

- **`git add`/`python3 test` false positive trên `.py`**: `bash_target` mở `BASH_EXT` sang `.py` — `git add a.py`/`python3 test_x.py` về lý thuyết không phải write target, nhưng regex mới chưa có case phủ → risk FP chặn nhầm lệnh thường. Đã verify tay `python3 -I scripts/test_fe_gate.py` (test suite chính nó) — allow. Cần theo dõi report thực tế.
- **9/10 gated ext chưa có deny-case test** — drop một ext khỏi regex vẫn xanh. Cost: regression im lặng khi sửa list.
- **Ambiguous basename merge nhầm** — deferred theo review.
- **`.py` comment-only edit cần declare** — hơi ồn; nếu user phàn nàn thì thêm py dialect vào `wording.py`.
- **Stale "sáu góc nhìn"** — có thể còn nguồn khác ngoài 2 chỗ đã sửa.
- **`extensions/` deletions + `.scratch/` + `helpers.ts` untracked** — artifacts session trước, không thuộc change này; không commit cùng.

## 6. Q&A

User cancelled the Q&A round and asked to commit directly. Proposed default answers are recorded
unconfirmed:

- Q: `git add a.py` có bị deny nhầm sau khi `.py` vào BASH_EXT? A: (unconfirmed) Không — `git`/`python3`
  nằm trong read-only commands; verified `python3 -I scripts/test_fe_gate.py` allow.
- Q: Edit `.py` chỉ đổi comment giờ phải declare labels? A: (unconfirmed) Chấp nhận — declare
  `Decision: n/a`; thêm Python dialect vào wording.py sau nếu ồn.
- Q: Ambiguous basename merge nhầm deferred? A: (unconfirmed) Đúng — Cách viết bắt repo-relative path.
- Q: Check chứng minh `--lens` warn? A: (unconfirmed) CLI case trong test_review_packages.py.
- Q: `extensions/` deletions + `helpers.ts` commit cùng? A: (unconfirmed) Không — chỉ file của change này.
