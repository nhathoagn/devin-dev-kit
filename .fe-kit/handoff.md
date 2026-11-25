# Handoff — đóng coverage gap, audit cho diff lớn, approve ra file riêng, test suite mới

## 1. Logic

Bốn việc trong một đợt, tất cả quanh đường review-diff:

1. **Coverage gap đóng hẳn.** Trước đây 41 item của REVIEW_CHECKLIST (SEC, T, TY, R, DOC) không thuộc lens nào — reviewer fan-out sẽ không bao giờ đi qua chúng. Giờ mọi item có đúng một chủ: `SEC1-10` → lens `security` mới, `T1-11` → lens `tests` mới, `TY1-9` → `contract`, `R1-8` + `DOC1-5` → `hygiene`. Pass 1 có 9 lens.
2. **Audit đi xuyên gói.** Diff >10 file trước chỉ có reviewer `contract` trên toàn range; giờ thêm `--lens audit` vì flow/fingerprint/field-list không nằm trong một package.
3. **Approve không đụng file người đọc.** `handoff.py approve` trước ghi stamp `Confirmed-by/at` vào cuối `handoff.md` — làm file dirty sau mỗi approve và in ra diff `+1` lơ lửng. Giờ stamp ghi `.fe-kit/handoff.approved`, một file local-state riêng, `.gitignore`d. Stamp cũ trong `handoff.md` vẫn được công nhận (fallback).
4. **Warning giả.** `review_check.py` trước warn "outside the diff" khi reviewer cite file mà diff import — audit lens chạy seed đã dính 6 warning kiểu này. Giờ `_import_context()` quét `import ... from "..."` trong file diff và coi đó là context hợp lệ.
5. **Test quay lại.** `scripts/test_review_lenses.py` (11 test) + `scripts/test_review_check.py` (5 test) — suite unittest duy nhất của repo, là cổng trong `AGENTS.md`.

## 2. Implementation

- `scripts/review_lenses.py` — thêm `security` + `tests` (`"pass": 1`); `hygiene` nhận `R1-8`/`DOC1-5`; `contract` nhận `TY1-9`; `list` in `items -` cho lens rỗng; docstring 6→8 item lens, ghi rõ `L1-3` placeholder ngoài coverage.
- `scripts/review_check.py` — `_import_context(root, diff_files)`: quét regex `import[^;"']*["']([^"']+)["']` trong mỗi diff file, resolve path tương đối theo thư mục file, giữ cái tồn tại trong repo. `check()` thêm `context` vào điều kiện warn; message đổi thành "…or a file the diff imports".
- `scripts/handoff.py` — `APPROVED_PATH = ".fe-kit/handoff.approved"`; `_approval_text()` đọc `.approved`, rỗng thì fallback stamp trong `handoff.md`; `problems()` đọc stamp từ `_approval_text()` và thêm check `handoff.md` mtime > `Confirmed-at` cũng là stale; `stamp(by)` không còn nhận text mà trả 2 dòng stamp; `approve()` ghi `.approved`.
- `skills/fe-kit/references/handoff.md` — spec: stamp sống ở `.approved`, "keep it out of commits — local state, like a lock"; stamp cũ trong handoff.md vẫn tính; sửa handoff.md sau approve cũng vô hiệu.
- `skills/fe-kit/playbooks/review-diff.md` — diff lớn: `--lens contract` + `--lens audit` trên toàn range.
- `skills/fe-kit/SKILL.md`, `README.md`, `CODEMAP.md` — số lens 7→9/13, mô tả audit cho diff lớn, test suite mới.
- `AGENTS.md` — cổng thêm 2 lệnh `python3 scripts/test_review_*.py`.
- `.gitignore` — `.fe-kit/handoff.approved`.
- `scripts/test_review_lenses.py`, `scripts/test_review_check.py` — file mới, unittest thuần, không dep.

Người giữ state: `LENSES` trong `review_lenses.py` là nguồn duy nhất cho item→lens; `handoff.approved` là nguồn duy nhất cho stamp approve (fallback `handoff.md` chỉ khi `.approved` trống hoặc thiếu).

## 3. Decisions

- **Gán item vào lens có sẵn thay vì tạo 4 lens mới.** `SEC` và `T` là nhóm tự nhiên riêng nên mỗi nhóm một lens; `TY` (schema/contract) và `R`/`DOC` (hygiene/docs) khớp lens có sẵn — ít lens hơn = ít reviewer hơn mỗi fan-out.
- **`security` + `tests` là 2 lens mới** vì 10+11 item quá nặng để nhét vào correctness/naming — một lens đi 21+ item sẽ không bao giờ hoàn thành trong một context.
- **Stamp riêng thay vì sửa cấu trúc `handoff.md`.** Tách file giữ file người đọc immutable sau khi viết — sửa `handoff.md` sau approve giờ là tín hiệu stale (check mới ở `problems()`), còn approve chỉ đụng `.approved`.
- **Fallback stamp cũ.** Repo đang có approve hợp lệ trong `handoff.md` trước thay đổi này — xoá fallback sẽ vô hiệu mọi approve cũ. Fallback chỉ kích hoạt khi `.approved` trống hoặc thiếu.
- **`_import_context` chỉ bắt quoted import** (`import ... from "x"`, `import "x"`) — đủ cho TS/JS hiện tại của repo; `require()` và dynamic `import()` cùng shape nháy cũng khớp. Extension-less import (`import './x'` không đuôi `.ts`) không resolve — giới hạn đã biết, accept vì repo luôn viết đuôi.

## 4. Debug without AI

- **Xem item nào thuộc lens nào:** `python3 scripts/review_lenses.py list --pass all` — cột items in đầy đủ, `-` cho lens không item.
- **Kiểm gap còn không:** `python3 -c "import sys; sys.path.insert(0,'scripts'); import review_lenses,re; items=set(); [items.update(a or b for a,b in re.findall(r'\*\*([A-Z]+\d+)\*\*|^\|\s*([A-Z]+\d+)\s*\|', open(p).read(), re.M)) for p in ['skills/fe-kit/references/REVIEW_CHECKLIST.md','skills/fe-kit/references/review-checks.md']]; items-={'L1','L2','L3'}; print(review_lenses.coverage_gap(items))"` — hoặc đơn giản chạy `python3 scripts/test_review_lenses.py`.
- **Warning "outside the diff" bất thường:** check `_import_context()` — nếu cite vẫn warn mà file đích là import, xem spec import có đuôi `.ts`/`/index` không (extension-less không resolve).
- **Approve bị reject sau khi sửa `handoff.md`:** đúng thiết kế — `problems()` giờ check mtime của `handoff.md` vs `Confirmed-at`; chạy lại `handoff.py approve`.
- **Rollback:** `git checkout HEAD -- scripts/review_lenses.py scripts/review_check.py scripts/handoff.py skills/fe-kit/references/handoff.md skills/fe-kit/playbooks/review-diff.md skills/fe-kit/SKILL.md AGENTS.md CODEMAP.md README.md .gitignore && rm scripts/test_review_*.py`.

## 5. Risks and open items

- **Pass 1 nay 9 reviewer** — chi phí fan-out tăng 3 context so với bản 6 lens gốc. Nếu diff nhỏ (1-2 file, ≤200 dòng) có thể cân nhắc chế độ single-reviewer toàn checklist — playbook chưa có nhánh đó.
- **Extension-less import không resolve** trong `_import_context` — repo hiện luôn viết đuôi `.ts`; nếu sau này có code `import './x'` sẽ vẫn warn.
- **`stale_files` so mtime theo `Confirmed-at`** — checkout branch khác rồi quay lại có thể làm mtime file giữ nguyên nhưng nội dung khác (mtime cũ hơn approve mới). Hiếm gặp; accept.
- **`handoff.py` legacy stamp trong `handoff.md`** vẫn được công nhận — stamp cũ không có version, không phân biệt được stamp nào là "của hệ mới trong handoff.md". Accept vì tín hiệu stale mtime đã cover.
- **`security`/`tests` lens chưa có brief riêng** — chúng là item lens thuần, không cần brief; `brief <lens>` fallback về title.

## 6. Q&A

- Q: Chỗ duy nhất quyết định checklist item nào do lens nào giữ? A (user): Mảng `items` trong từng dict của `LENSES` — thêm item ở đây, `coverage_gap()` sẽ phát hiện nếu sót.
- Q: Nhánh dễ hỏng nhất khi ai sửa sau này? A (user): `_approval_text()` — file `.approved` rỗng sẽ rơi về stamp cũ trong `handoff.md`; ai xoá fallback sẽ vô hiệu approve cũ đang chạy.
- Q: Check nào chứng minh coverage gap đã đóng hẳn? A (user): `test_every_checklist_item_has_a_lens` trong `test_review_lenses.py` — parse REVIEW_CHECKLIST + review-checks rồi gọi `coverage_gap()`.
- Q: Khi reviewer cite file ngoài diff, warning nào hợp lệ? A (user): File mà một diff file import trực tiếp → không warn (context hợp lệ); file không import và không phải caller → vẫn warn.
