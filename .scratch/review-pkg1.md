# Kết quả review

## Kết luận

Sửa rồi hãy đưa. Không có file yêu cầu. Một việc nên sửa trong lượt này: khóa gộp finding của `merge` hỏng đúng khi chạy kèm `--files`/`--diff`/`--staged`, nên một chỗ lỗi in thành hai đoạn.

## Việc cần sửa

`scripts/review_packages.py:222` nối `scope["files"]` và các file rule vào `candidates` mà không bỏ trùng, trong khi phần đầu danh sách đã là một `set` các đường dẫn được trích. Khi một file vừa nằm trong diff vừa được một report trích, nó đứng hai lần trong danh sách; `_resolve_ref` chỉ resolve khi đúng một hit nên trả `None`, cite viết tắt dạng helpers.ts:3 không gộp với src/a/helpers.ts:3 và merge in một chỗ lỗi thành hai đoạn — chính lỗi mà diff này sửa. Nên khử trùng danh sách sau khi nối, ví dụ `candidates = sorted(set(candidates + scope["files"] + [item["path"] for item in scope["read"]]))`. Nên sửa trong lượt này.

`scripts/review_packages.py:78` giữ nguyên chuỗi trích khi `_resolve_ref` trả `None`. Với basename mơ hồ — hai file cùng tên ở hai package, đúng tình huống fan-out theo package — hai chỗ lỗi ở hai file khác nhau nhưng cùng tên vẫn mang cùng key nên gộp một đoạn, và đoạn chỉ trích đường dẫn của report đến trước; người fix xong file đó mà không biết file còn lại cũng bị gắn cờ. Có thể để sau.

`scripts/review_packages.py:226` chỉ kiểm `--lens` khi có ít nhất một report mang dòng `Lens:`. Nếu fan-out viết report thiếu dòng đó — đúng lỗi mà cờ này được thêm để bắt — merge chạy êm mà không cảnh báo lens nào thiếu. Có thể để sau.

`scripts/bash_target.py:12` mở rộng `BASH_EXT` (và `BASH_EXT_MENTION_RE` ở dòng 15) sang `.ts`, `.py`, `.go`, `.rs`, `.java`, `.kt`, `.kts`, `.rb`, `.php`, `.cs`, `.swift`, nhưng `test_bash_target.py` không có case nào chạm extension mới — toàn bộ case vẫn chỉ là `.tsx`/`.mjs`. Bỏ sót một extension khỏi regex vẫn cho suite xanh; nên thêm vài case redirect/tee/`sed -i` cho `.py` hay `.ts`. Có thể để sau.

## Tóm tắt

Việc chặn đưa lên: 0. Việc nên sửa trong lượt này: 1. Việc có thể để sau: 3.

## Nguồn và độ phủ

Luật đã đọc: `rules/comments.md`, `rules/conflict-fix.md`, `rules/fe-implementation.md`, `rules/modules.md`, `rules/reuse-duplication.md`, `rules/review-diff.md`
Cổng: `python3 scripts/test_review_packages.py` 30/0 · `test_fe_gate.py` 227/0 · `test_devin_gate.py` 30/0 · `test_bash_target.py` 18/0 · `test_wording.py` 85/0 · `test_review_check.py` 25/0 · `test_project_config.py` 52/0 · `test_versions.py` 6/0
Độ phủ: `CODEMAP.md` ✔ · `README.md` ✔ · `package.json` ✔ · `.claude-plugin/marketplace.json` ✔ · `.claude-plugin/plugin.json` ✔ · `.devin-plugin/plugin.json` ✔ · `scripts/bash_target.py` ✔ · `scripts/devin_gate.py` ✔ · `scripts/fe-gate.py` ✔ · `scripts/review_lenses.py` ✔ · `scripts/review_packages.py` ✔ · `scripts/test_devin_gate.py` ✔ · `scripts/test_fe_gate.py` ✔ · `scripts/test_review_packages.py` ✔
