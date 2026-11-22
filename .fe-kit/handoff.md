# Handoff — audit lens vào review-diff, tách pass trong review_lenses, dọn docs chết

## 1. Logic

Review-diff pass 1 trước đây có 6 lens checklist; `references/audit.md` bị playbook cấm rõ ("Do not apply the Architecture smell list") nên flow, error handling, extension cost không được soi ở diff. Đồng thời `review_lenses.py list` in trộn lens pass 1, pass 2 và invariants — tác giả fan-out theo `list` sẽ spawn cả lens không thuộc pass.

Đường đi mới:

1. `list --pass 1` → 7 lens: 6 checklist + `audit`. Lens `audit` không có item; task brief (`brief audit`) chỉ đạo đọc `audit.md` và chạy Architecture, Operational flow, Error handling, Extension — bỏ Reuse và Performance-and-load vì checklist đã có (D*, P*, F10).
2. `list --pass 2` → 4 lens: `correctness`, `contract` (`pass: [1,2]`), `probe`, `invariant` — chỉ khi fix tạo mặt contract mới.
3. `list --pass invariants` → `coverage`, `regression` cho `review-invariants.md`.
4. Finding judgement của audit mang mức `có thể để sau`; defect thật (nuốt lỗi, double-submit, caller gãy) giữ level riêng. Item lens vẫn bị cấm viết paragraph judgement — cấm đó chuyển từ "cấm audit.md" sang "cấm judgement trong item lens".

## 2. Implementation

- `scripts/review_lenses.py` — thêm lens `audit` (items rỗng, có `brief`); thêm field `pass` (int, list, hoặc `"invariants"`); `list` nhận `--pass 1|2|invariants|all`, default `1` nên caller cũ không flag vẫn đúng; helper `_lens_passes()` xử lý cả int lẫn list.
- `skills/fe-kit/playbooks/review-diff.md` — fan-out dùng `list --pass 1`/`--pass 2`; step 3 bỏ câu cấm audit.md, thêm nhánh lens audit đọc `audit.md` qua `brief`; 2 đoạn mới sau step 3 định nghĩa mức finding của audit và giữ cấm judgement cho item lens.
- `skills/fe-kit/SKILL.md` — mô tả fan-out cập nhật 7 lens pass 1 + nhóm `--pass 2` + `--pass invariants`.
- `skills/fe-kit/playbooks/author-loop.md` — `list` → `list --pass 1`.
- `AGENTS.md` — viết lại: cổng `tsc` + `eslint fixtures` (xoá `extensions/checkout` và `bun test` đã chết từ commit `3f872e1`), xoá section Checkout contract, thêm mô tả flow lens.
- `CODEMAP.md` — xoá 13 dòng `test_*.py` đã xoá (`62310ca`), thêm `fixtures/`, 8→9 playbook, thêm `review-checks`/`review-output`/`codemap-host-report`, `F1..F24`→`F1..F25`, Verify block chỉ giữ lệnh sống.
- `README.md` — đoạn fan-out 6→7 lens + `--pass`; structure block: 11 lens, bỏ "+ test" khỏi `fe-gate.ts`, thêm `fixtures/`, 8→9 playbook.

Người giữ state: `LENSES` trong `review_lenses.py` là nguồn duy nhất cho tên lens, items, pass, brief. `review_packages.py merge` nhận tên lens qua `--lens` generic — không cần sửa.

## 3. Decisions

- **Audit là lens riêng, không nhét item mới vào checklist.** Item `F26` sẽ ép judgement smell vào cùng severity framework với defect; brief riêng giữ ranh giới "judgement = có thể để sau" rõ ràng, và tái dùng cơ chế no-item đã có sẵn (probe/invariant/coverage/regression).
- **`pass` field thay vì tách file.** Một nguồn `LENSES`, filter ở `list`. Tách file thứ hai cho pass 2 chỉ thêm chỗ phải đồng bộ.
- **`correctness`/`contract` chạy cả 2 pass** (`pass: [1,2]`) theo đúng spec cũ của playbook — pass 2 đã gọi tên chúng từ trước.
- **Bỏ cổng `bun test`.** Repo không còn file test nào; giữ lệnh trong AGENTS.md làm mọi task báo cổng đỏ giả.
- **Không thêm test mới.** Repo không có harness Python; verify bằng chạy trực tiếp `list`/`items`/`brief` — là đường tác giả thật sự dùng.

## 4. Debug without AI

- **Xem lens nào thuộc pass nào:** `python3 scripts/review_lenses.py list --pass all` — cột "pass X" in ngay trên từng dòng.
- **Xem brief lens audit:** `python3 scripts/review_lenses.py brief audit`.
- **Lens không in ra:** check field `pass` trong `LENSES` — `list` lọc theo `_lens_passes(lens)`; int đơn tự wrap thành list một phần tử.
- **Reviewer audit viết gì:** đọc `review-diff.md` đoạn sau step 3 — judgement `có thể để sau`, defect giữ level, không in bảng audit, không chấm Fowler.
- **Report audit bị reject ở review_check:** kiểm `file:line` phải nằm trong diff hoặc là caller từ step 5 — audit finding ngoài diff sẽ warning "outside the diff".
- **Rollback:** `git checkout HEAD -- scripts/review_lenses.py skills/fe-kit/playbooks/review-diff.md skills/fe-kit/SKILL.md skills/fe-kit/playbooks/author-loop.md AGENTS.md CODEMAP.md README.md .fe-kit/handoff.md`.

## 5. Risks and open items

- **Pass 1 nay có 7 reviewer** thay vì 6 — chi phí mỗi fan-out tăng một context. Audit finding chủ yếu `có thể để sau` nên thường không chặn verdict.
- **Checklist vẫn có lỗ hổng cũ** (SEC, T, TY, R, DOC không nằm lens nào) — có sẵn từ trước, ngoài phạm vi; `coverage_gap()` vẫn báo nếu ai gọi.
- **`CODEMAP.md` bảng payload lịch sử** (2026-11-15) giữ nguyên — ghi chép một lần chạy, không phải lệnh verify.
- **Lens audit chưa chạy thật trên diff nào** — prompt brief mới chỉ được verify bằng `brief audit` in ra đúng text; hiệu quả bắt lỗi cần một lượt fan-out thật trên `fixtures/review-seed.ts`.

## 6. Q&A

- Q: Ai là chỗ duy nhất quyết định lens nào thuộc pass nào? A (user): Field `pass` trong mảng `LENSES` của `scripts/review_lenses.py`.
- Q: Nhánh nào dễ bị sửa hỏng nhất? A (user): `_lens_passes()` — `pass` nhận cả int lẫn list; đổi thành so sánh trực tiếp sẽ làm `correctness`/`contract` mất khỏi pass 2.
- Q: Check nào chứng minh pass filter đúng? A (user): Chạy `list` / `--pass 2` / `--pass invariants` và đếm: 7 / 4 / 2 lens.
- Q: Finding của lens audit mang mức nào? A (user): Judgement smell → `có thể để sau`; defect thật (nuốt lỗi, double-submit) giữ level riêng.

Confirmed-by: nhathoang
