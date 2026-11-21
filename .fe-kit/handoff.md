# Handoff — checkout-form before/after demo + author-loop playbook

## 1. Logic

Hai thay đổi:

**(a) `extensions/checkout-form-smells.ts`** — file demo song song: `export namespace Smelly` giữ nguyên code cũ đầy lỗi để so sánh; phần clean cùng tên export dưới mỗi hàm có comment `// Before:` chỗ đổi semantics. Mọi hàm clean trả `Result<T>` (`{ok:true,value,warning?}` / `{ok:false,error}`) thay sentinel union; guard `isObject` chặn non-object/array ở mọi entry; tra bảng qua `Object.hasOwn`/`Map` (không dính prototype); undo per-form `WeakMap` với `replaceContents` (delete-all-keys rồi assign); receipt `RCP|id|country|name|total` encodeURIComponent ↔ `parseReceipt` decode; id đơn bắt buộc + `submittedIds` chống duplicate; audit warn trên result không nuốt vào `stats.lastError`.

**(b) `skills/fe-kit/playbooks/author-loop.md` + `SKILL.md`** — playbook 10 bước cho author của diff đi qua lens review: rules → edit → verify mỗi batch → fan-out lens → `review_packages.py merge` → fix một pass → quét boundary toàn cục → pass 2 (correctness/contract/probe/invariant) → verify từng finding ở HEAD → commit + `review_record.py save`. Kèm danh sách anti-pattern rút từ session demo.

Ngoài ra `extensions/anti-patterns.ts` + `.test.ts` đã được refactor sẵn trong worktree (bỏ guard thừa trong `shippingFee`/`discount`/`calcSubtotal`, thêm test discount) — không phải phần việc trên nhưng đi cùng commit vì diff sạch và test xanh.

## 2. Implementation

- `extensions/checkout-form-smells.ts:349-373` — `COUNTRY_RULES`/`COUPON_RULES`/`SHIPPING_FEES`/`ZONE_BUCKETS`: toàn bộ logic country→currency/tax/zones và zone→fee sống ở bảng, không if-chain.
- `:493-512` `STATE_CHECKS`/`ITEM_CHECKS`/`firstError`/`validate` — validation là data + một helper tìm lỗi đầu tiên.
- `:554-575` `submitOrder` — pipeline: validate → computeTotal → orderId → dedupe → `notify`/`recordOrder`/`auditWithRetries`/`receiptFor` (helper một-việc-một).
- `:582,628-640` `receiptField`/`receiptFor`/`parseReceipt` — emit và parse là inverse của nhau, dùng chung `RECEIPT_PREFIX`.
- `:643-668` `startAutoSave`/`anonId` — interval trả stop fn xóa `keys` Set; key ẩn danh unique per state.
- `skills/fe-kit/playbooks/author-loop.md` — file mới, hình dạng theo `review-diff.md`.
- `skills/fe-kit/SKILL.md:22` — một dòng đăng ký playbook.

State holder: `submittedOrders`/`submittedIds` (đơn đã gửi), `undoStacks` (undo per form), `auditCache`/`warmTotals`/`drafts` (cache có bound `CACHE_LIMIT` qua `setBounded`), `stats`, `current`. Mỗi thứ một holder; không holder nào đọc lại ngoài `stats`/`submittedOrders`/`current` — ba map cache là cố ý cho demo.

## 3. Decisions

- `namespace Smelly` chứ không hai file: so sánh đọc trong một file, `bun` chạy được namespace, import `Smelly.f` vs `f` tự giải thích.
- `Result<T>` chung một type ở top-level thay discriminated union per-hàm: đủ cho demo, khớp convention `anti-patterns.ts`.
- `encodeURIComponent` thay escape tự viết cho receipt: ký tự `|` chỉ là một trong nhiều ký tự nguy hiểm; encode giải quyết tất cả và decode là inverse sẵn có.
- `WeakMap` thay `Map<id,stack>` cho undo: key theo object identity = đúng nghĩa "undo của form này", tự GC khi form chết; `anonId` cũng WeakMap để hai form ẩn danh không đụng key.
- `Object.hasOwn` thay `in`/index cho lookup theo input: `Record` lookup `"__proto__"` trả prototype object — guard truthy không đủ.
- Bỏ `history` global: cross-form contamination và merge-only undo là hai lỗi từ một root — stack per-form + `replaceContents` xóa cả hai.
- Không bound `submittedOrders`/`submittedIds`/`undoStacks` (chỉ `stack` cap 128): store nghiệp vụ, evict = mất đơn/mất undo hợp lệ; `drafts`/`auditCache`/`warmTotals` là cache nên có bound.

## 4. Debug without AI

- Reproduce bất kỳ hành vi nào: `bun /tmp/checkout-smoke*.ts` (các script trong `/tmp`, hoặc viết `import * as C from "..."` rồi gọi). `bun -e 'import("./extensions/checkout-form-smells.ts").then(m=>console.log(m.computeShipping({shippingZone:"A",items:[{sku:"x",price:100,qty:1}]})))'`.
- So sánh trước/sau cho một hàm: `Smelly.<fn>` vs `<fn>` cùng input — ví dụ `Smelly.dedupeItems` mất qty trùng, `dedupeItems` giữ.
- Watch: mọi lỗi trả `error` string đọc được ngay — `"missing order id"` (submit thiếu `state.id`), `"duplicate order: X"` (`submittedIds` đã có), `"unknown shipping zone"` (zone không trong `SHIPPING_FEES`), `"unsupported country"` (country không trong `COUNTRY_RULES`), `"audit: ..."` trong `warning` khi `recordAudit` fail hết retry.
- Verify fix: `bunx tsc --noEmit --strict --lib esnext,dom --target esnext extensions/checkout-form-smells.ts` + chạy lại input gây lỗi.
- Rollback: `git checkout extensions/checkout-form-smells.ts` nếu chưa commit — file untracked thì `git clean -f` hoặc giữ nếu chỉ muốn bản smelly: xóa phần từ dòng `// Clean version` trở xuống rồi bỏ namespace `Smelly`.
- Playbook: kiểm đăng ký `grep author-loop skills/fe-kit/SKILL.md`; đổi flow thì sửa `author-loop.md`, không cần đổi gì khác.

## 5. Risks and open items

- `extensions/anti-patterns.ts/.test.ts` diff đi kèm chưa qua lens review — là refactor có sẵn trong worktree, test 9/9 pass; rủi ro thấp nhưng nói rõ để biết.
- Các mục `có thể để sau` còn mở (19): `Session` chưa export, `TET_BONUS` literal, ba cache chỉ-ghi, `recordAudit` nhánh `!id` unreachable, ordering `isObject`/block validate trong file, banner comment — chi tiết `/tmp/r3reports/merged.md`.
- `undoStacks` stack cap dùng `shift()` FIFO — undo quá 128 lần select mất snapshot cũ nhất; chấp nhận được cho demo.
- File demo không có test runner chính thức — verify bằng smoke script /tmp, không có `bun test` file trong repo.

## 6. Q&A

- Q: `submittedOrders` và `drafts` đều grow không bound — có cần cap không? A: Không — store nghiệp vụ, evict = mất đơn/draft; chỉ cache mới bound.
- Q: `warning` audit-fail trả ok:true — caller nên treat là success hay cần retry? A: Success — audit là side-channel, đơn đã ghi; warning chỉ để log/hiển thị.
- Q: `parseReceipt` cho phép `country`/`customerName` rỗng — đó là spec đúng hay nên reject? A: Đúng — field optional trong form nên empty field hợp lệ, chỉ id/total bắt buộc.
- Q: Commit gộp cả diff `anti-patterns` có sẵn trong worktree hay tách? A: Commit chung — diff sạch, cùng chủ đề.
