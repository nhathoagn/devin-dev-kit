# Kết quả review

## Kết luận

Sửa rồi hãy đưa. Một việc nên sửa trong lượt này: `skills/fe-kit/SKILL.md` vẫn hướng dẫn fan-out theo kiểu cũ — không ghim đường dẫn report và không `--lens` — nên chính lỗi mất report mà bản release này sửa vẫn xảy ra với người đọc file đó; đồng thời hàng routing của `author-loop.md` bị xóa mà không ghi thay bằng gì.

## Việc cần sửa

`.scratch/review-tool-findings.md:14` yêu cầu fan-out phải ghim đường dẫn report cho từng lens hoặc `merge` cảnh báo khi thiếu file, thay cho kiểu "succeeding quietly". `skills/fe-kit/SKILL.md:28` hướng dẫn `Merge the reports with review_packages.py merge` không kèm `--lens`, và `skills/fe-kit/SKILL.md:33` lặp lại `merge --out <file> <package reports>` không kèm `--lens`; đồng thời đoạn fan-out không yêu cầu report ghi vào `review-<lens>.md` như hai playbook vừa sửa. Cùng chỗ đó, hàng routing `Fix or rewrite existing code whose diff then goes through lens review → author-loop.md` bị xóa khỏi bảng (`skills/fe-kit/SKILL.md:22` bây giờ nhảy thẳng sang `cleanup.md`) mà changelog không nói thay bằng gì. Tác giả đi theo SKILL.md — đường chính của skill — vẫn đánh mất findings của lens không ghi file, đúng lỗi release này sửa trong `review_packages.py`. Nên sửa trong lượt này: thêm `--lens` và đường dẫn report vào hai đoạn SKILL.md, và nêu rõ `author-loop.md` vẫn là playbook của author (hoặc xóa hẳn nếu cố ý).

`skills/fe-kit/SKILL.md:28` viết `review_lenses.py list` in "the six lenses", nhưng lệnh đó in 8 (kể `probe` và `invariant`, hai lens pass-2 không có item nào). Cùng câu đó và `skills/fe-kit/playbooks/review-diff.md:11` nói "one reviewer per lens", nên người đọc nghiêm túc sẽ spawn luôn hai reviewer cho lens rỗng ở pass 1. `skills/fe-kit/SKILL.md:8` còn nói skill chỉ chạy trước "non-trivial frontend work", mâu thuẫn chính hàng routing non-UI vừa thêm ở dòng 22. Người đọc không biết fan-out lấy 6 hay 8 lens. Có thể để sau: sửa thành "the pass-1 lenses" và mở rộng câu scope.

`skills/fe-kit/CHANGELOG.md:12` nói ``GATED_EXT_RE`` in `scripts/bash_target.py`, nhưng file đó không có hằng này — đoạn regex được sửa là `BASH_EXT` và `BASH_EXT_MENTION_RE` (`scripts/bash_target.py:11,13`). Cùng dòng ghi "The four playbook gate lines", thực tế có năm dòng gate mới cùng nội dung — thêm `skills/fe-kit/playbooks/cleanup.md:16`. Ai lần theo changelog để sửa gate sẽ tìm một hằng không tồn tại. Có thể để sau: đổi tên hằng cho đúng và sửa con số.

Danh sách extension trong dòng gate — `.ts`, `.jsx`, `.js`, `.mjs`, `.cjs`, `.vue`, `.svelte`, `.astro`, `.mdx` — được viết nguyên văn ở năm file: `skills/fe-kit/playbooks/fix-bug.md:28`, `new-ui.md:13`, `perf-ui.md:12`, `refactor-ui.md:14`, `cleanup.md:16`. Danh sách này không nêu `.py`, `.go`, `.rs` dù đây là các extension mới của `GATED_EXT_RE`, và `rules/fe-implementation.md` — nguồn chuẩn mà mọi dòng trích — lại không ghi danh sách nào. Lần tới thêm extension phải sửa sáu chỗ; thiếu một chỗ thì playbook lệch gate. Có thể để sau: giữ danh sách đầy đủ ở một chỗ và để các dòng gate trỏ tới.

## Để yên

`skills/fe-kit/references/REVIEW_CHECKLIST.md:58` (N2): câu mới vẫn quyết được — nhánh đặc biệt "viết được thành guard clause/early return" là một điều kiện kiểm chứng bằng việc viết lại, không phải smell judgement bị cấm vào diff checklist. Cố ý không sửa: "sâu hơn 4 bất kể" bỏ lối thoát "không giải thích được" của bản cũ, nghĩa là nesting sâu có lý do chính đáng vẫn FAIL; đó là lựa chọn policy của release, không phải lỗi. `skills/fe-kit/references/review-checks.md:30` (F24): format ba cột khớp các hàng F-khác, ngoại lệ "stays a loop: N/A" nằm trong cột FAIL y hệt mẫu F6/F16; `review_lenses.py` xếp F24 vào lens `structure` đúng changelog. `skills/fe-kit/playbooks/cleanup.md` đi theo khung `refactor-ui.md` (ownership → reuse → perf-điều-kiện → sweep → audit → feature-isolation n/a → 4 checklist → external) và không mâu thuẫn skip rule mới ở `SKILL.md:38` hay `rules/modules.md`. `evals.json:128` đã cập nhật sang F1–F24.

## Tóm tắt

Việc chặn đưa lên: 0. Việc nên sửa trong lượt này: 1. Việc có thể để sau: 3.

## Nguồn và độ phủ

Luật đã đọc: `rules/comments.md`, `rules/conflict-fix.md`, `rules/fe-implementation.md`, `rules/modules.md`, `rules/reuse-duplication.md`, `rules/review-diff.md`
Cổng: `test_review_packages.py 30/0` · `test_fe_gate.py 227/0` · `test_devin_gate.py 30/0` · `test_bash_target.py 18/0` · `test_wording.py 85/0` · `test_review_check.py 25/0` · `test_project_config.py 52/0` · `test_versions.py 6/0` — tất cả pass (task gửi kết quả)
Độ phủ: `skills/fe-kit/CHANGELOG.md` ✔ · `skills/fe-kit/SKILL.md` ✔ · `skills/fe-kit/evals/evals.json` ✔ · `skills/fe-kit/playbooks/author-loop.md` ✔ · `skills/fe-kit/playbooks/cleanup.md` ✔ · `skills/fe-kit/playbooks/fix-bug.md` ✔ · `skills/fe-kit/playbooks/new-ui.md` ✔ · `skills/fe-kit/playbooks/perf-ui.md` ✔ · `skills/fe-kit/playbooks/refactor-ui.md` ✔ · `skills/fe-kit/playbooks/review-diff.md` ✔ · `skills/fe-kit/references/REVIEW_CHECKLIST.md` ✔ · `skills/fe-kit/references/review-checks.md` ✔
