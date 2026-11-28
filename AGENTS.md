# Agent rules — plugin-architecture

## Trước khi báo xong
Chạy và báo **lệnh + exit code** cho từng cổng dưới đây. Một cổng đỏ thì chưa xong.

```bash
bunx tsc --noEmit -p tsconfig.json
bunx eslint fixtures --max-warnings 0
python3 scripts/test_review_lenses.py
python3 scripts/test_review_check.py
```

Hai test Python là suite duy nhất của repo — không chạy `bun test` làm cổng.

## Review flow (`scripts/`)
- Fan-out review: `python3 scripts/review_lenses.py list --pass 1` in danh sách lens pass 1 (8 checklist lens + `audit` đi `references/audit.md`); `--pass 2` in lens pass 2 (`correctness`, `contract`, `probe`, `invariant`); `--pass invariants` in `coverage` + `regression` cho playbook `review-invariants.md`.
- Một lens một reviewer. Report ghi `Lens: <name>` rồi merge bằng `python3 scripts/review_packages.py merge --root <repo> --lens <a,b,…> --out <file> <reports>`.
- Report cuối phải qua `python3 scripts/review_check.py --root <repo> --report <file>`.

## Sửa lỗi
- Test đỏ trước, sửa sau. Không sửa test đã có trong cùng PR fix.
- Repro là test trong repo, không phải script `/tmp`.
- Mỗi fix một commit: `fix(<scope>): <F-xxx> <tóm tắt>`.

## Không làm
- Không import file fixture (`fixtures/` chứa input cố tình lỗi để kiểm review tool). Fixture sống ngoài code sản phẩm.
- Không thêm eviction cho `receipts`/`settled` để "giảm bộ nhớ": evict receipt làm replay trừ kho lần hai.
