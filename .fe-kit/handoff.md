# Handoff — module checkout theo schema + một giao dịch, và flow review invariants

## 1. Logic

Một đơn hàng đi vào, một kết quả đi ra. Đường đi:

1. **Cửa vào.** Input là `unknown`. `readOrder()` chạy schema Valibot `strictObject`: key lạ ở mọi tầng bị từ chối, `id` trim + lowercase, `tier`/`region` nằm trong `picklist`, `qty`/`price` là số nguyên an toàn 1…1e9, `email` khớp `x@y.z`, tổng từng dòng và tổng đơn phải là số nguyên an toàn. Sai → `status:"rejected"`, `orderId:null`, không chạm kho.
2. **Coupon.** `FREESHIP` và `SALE10`/`SALE20` hợp lệ; mọi mã khác → `rejected` + `invalid coupon <mã>`. Kiểm ở đây, trước khi tính tiền, cho **cả hai kênh**.
3. **Giá.** `priceOrder(order, b2b)` là hàm thuần: chiết khấu theo bậc tier + VIP + coupon phẳng, trần 30% và ≤ total; phí vùng theo `region`; express 50 000 và gift-wrap 15 000 cộng thêm ở **cả hai kênh**; miễn phí vùng chỉ miễn phí nền, không miễn phụ phí; thuế 8%, vùng `south` ×1.1, làm tròn **một lần**. `representable()` kiểm cả 5 field tiền là số nguyên an toàn ≥ 0 — sai thì `rejected` + `order total is too large`, kho không đổi.
4. **Giao dịch.** `CheckoutStore.attempt()` nhận `{key, digest, reservations, render}` và làm ba việc trong một đơn vị: (a) key chưa có → tiếp; key có mà digest khác → `conflict`; digest trùng → `replay` (trả bản copy); (b) kiểm **toàn bộ** reservation, thiếu bất kỳ sku nào → `short` kèm danh sách, không trừ gì; (c) đủ hàng → gọi `render()`, trừ kho, lưu receipt.
5. **Ra.** `replay` → kết quả cũ với `servedFromCache:true` (giữ `createdAt` gốc). `settled` → kết quả mới. `conflict`/`short`/input sai → `rejected` + `problems`.

Trạng thái: chỉ có ba trạng thái kết quả `ok | rejected`. Không còn `partial` (đơn bị từ chối toàn phần, chẩn đoán theo sku nằm trong `problems`).

Biên quyết định hành vi: `total ≥ 1 000 000` (miễn phí vùng), `≥ 500 000` và `≥ 200 000` (bậc chiết khấu), trần 30%, stock đúng bằng qty (về 0, đơn sau bị từ chối), `qty`/`price` chạm 1e9, tổng chạm 2^53.

## 2. Implementation

- `extensions/checkout/schema.ts` — `readOrder()` sở hữu toàn bộ việc validate và chuẩn hoá. Không nơi nào khác validate lại.
- `extensions/checkout/canonical.ts` — `canonicalForm()` và `idempotencyKey()`: `fast-json-stable-stringify` trên dữ liệu đã qua schema (dòng gom theo `sku`+`price` rồi sắp xếp, `null` optional coi như vắng) + SHA-256.
- `extensions/checkout/pricing.ts` — hàm thuần: `lineTotal`, `couponProblem`, `discountFor`, `shippingFor`, `taxFor`, `priceOrder`, `representable`, `copyResult`, `reject`. Đây là chỗ duy nhất chứa luật tiền.
- `extensions/checkout/store.ts` — port `CheckoutStore.attempt()` (async) + `MemoryCheckoutStore`. Adapter giữ `stock: Map`, `settled: Map<key,{digest,result}>`, và một mutex `Promise.withResolvers` để hai attempt song song không chen nhau.
- `extensions/checkout/checkout.ts` — `checkout(input, channel, {store, now})`: parse → coupon → `representable` → `store.attempt` → dịch `AttemptOutcome` sang `CheckoutResult`. `now()` được inject để `createdAt` tất định.
- `extensions/checkout/checkout.test.ts` — 58 test: 32 test hành vi, 5 property test fast-check, 4 test contract có `Promise.all` đua, 17 test tham số hoá.
- `extensions/checkout/SPEC.md` — hợp đồng: `INV-01…09`, threat model, danh tính đơn, rubric severity, điều kiện dừng.
- `extensions/nested-if.ts` — **fixture đối chứng** cho tool review (bản cũ 640 dòng, không phải code sản phẩm, không được import).
- `tsconfig.json` — `include` chỉ `extensions/checkout/**`; `fe-gate.ts` chưa qua `--strict` với các cờ này nên nằm ngoài.
- `eslint.config.mjs` — `strictTypeChecked` + `max-depth 3`, `complexity 10`, `max-lines-per-function 60`, cấm `for...in`, cấm toán tử `in`, cấm import `nested-if*`, cấm `JSON.stringify` ngoài `canonical.ts`. Test được nới 3 rule (độ dài, `require-await`, floating promise).
- `stryker.config.json` — mutate 3 file logic, command runner `bun test extensions/checkout`, break 80.
- `AGENTS.md` — cổng bắt buộc + luật riêng cho module checkout + luật sửa lỗi.
- `scripts/review_lenses.py` — thêm 2 lens `coverage`, `regression` (chế độ invariants) → 10 lens.
- `skills/fe-kit/playbooks/review-invariants.md` — flow review mới: bất biến → test → mất mát so bản cũ → verdict `HỘI TỤ`/`CHƯA HỘI TỤ`, kèm cổng vận hành, 2 prompt, A0–A7.
- `skills/fe-kit/playbooks/review-diff.md`, `skills/fe-kit/SKILL.md` — định tuyến: diff có test suite thì chuyển sang playbook invariants.
- `package.json` — deps (`valibot`, `fast-check`, `fast-json-stable-stringify`), devDeps (`@types/bun`, `eslint`, `typescript-eslint`, `@stryker-mutator/core`), scripts `typecheck`/`lint`/`mutate`/`gates`/`test`.

Người giữ state: `MemoryCheckoutStore` giữ `stock` và `settled`; `checkout.ts` không giữ gì giữa hai lần gọi. Transaction là **một** hàm, không có state trung gian nào khác.

## 3. Decisions

- **Một giao dịch thay vì cache trong RAM.** Bản cũ thiết kế lại idempotency 7 lần (map → stringify key → join → tombstone → LRU → ledger → pending/reconcile) và sinh 11 blocker; mỗi bản vá chỉ dời lỗ hổng. Port `attempt()` là chỗ duy nhất biết cả key lẫn kho, nên "claim + trừ + settle" không tách rời được nữa.
- **Schema ở cửa, không validate rải.** 16 finding (G4) đến từ validate từng field; schema `strictObject` đóng luôn lớp prototype pollution, padded id, `null`, số tràn.
- **Từ chối `orderCount`/`name`/`category`.** Chúng không ảnh hưởng tiền; giữ lại thì phải chuẩn hoá và đưa vào canonical mà không ai dùng. Giá phải trả: caller cũ phải bỏ các field này.
- **`orderId` toàn cục, không theo inventory.** Đã thử gắn inventory vào receipt (identity `===`) và nó phá retry khi caller nạp lại inventory mỗi request; đã thử eviction và nó làm replay trừ kho hai lần. Chọn: order id là idempotency key, replay không trừ kho.
- **Async ngay từ đầu.** Adapter DB không thể đồng bộ; đổi sau sẽ phá toàn bộ bất biến đã chứng minh.
- **Thuế làm tròn một lần.** Làm tròn hai bước (nền rồi ×1.1) lệch 1 đồng so với port.
- **Không evict `settled`.** Evict làm replay trừ lại. Bộ nhớ là giá phải trả; production dùng bảng receipts + retention (SPEC §6).
- **Playbook mới là mode riêng, không sửa playbook cũ.** Diff không có test vẫn dùng `review-diff.md`; hai mode trộn vào nhau sẽ làm cả hai mơ hồ.

## 4. Debug without AI

- **Reproduce một lỗi tiền:** `bun -e 'import {checkout} from "./extensions/checkout/checkout.ts"; import {MemoryCheckoutStore} from "./extensions/checkout/store.ts"; const s=MemoryCheckoutStore.from({A:10}); console.log(await checkout({...}, "retail", {store:s}))'` — thay input, xem `grandTotal` và `s.read("A")`.
- **Xem chỗ quyết định giá:** `extensions/checkout/pricing.ts` — `discountFor` (chiết khấu), `shippingFor` (phí), `taxFor` (thuế), `representable` (chặn tiền không biểu diễn được).
- **Xem chỗ quyết định trừ kho / idempotency:** `extensions/checkout/store.ts` — `MemoryCheckoutStore.settle()`. Ba nhánh: `existing` (replay/conflict), `short`, `settled`.
- **Ý nghĩa lỗi:** `order is invalid` → schema từ chối, xem `problems` để biết field nào; `order total is too large` → `representable()` thất bại, tiền vượt 2^53 hoặc âm; `<sku>: insufficient stock` → `short`, **kho không bị trừ**; `already settled with a different payload` → cùng key khác digest, tức cùng `orderId` nhưng payload khác.
- **Verify một fix:** `bun run gates` (tsc → eslint → test → stryker). Một mình `bun test extensions/checkout` chỉ bắt test sai, không bắt test yếu.
- **Rollback:** bỏ `extensions/checkout/` và 5 file config (`tsconfig.json`, `eslint.config.mjs`, `stryker.config.json`, `AGENTS.md`, `bun.lock`) khôi phục nguyên trạng repo; không file cũ nào bị sửa ngoài `package.json`, `scripts/review_lenses.py`, 3 file trong `skills/fe-kit/` (đều có thể `git checkout --`).

## 5. Risks and open items

- **Adapter DB chưa có.** `INV-02`/`INV-03` mới chứng minh trên `MemoryCheckoutStore`. Port đã async và có contract test đua, nhưng transaction thật (`UPDATE … WHERE stock >= qty` + `receipts(key PRIMARY KEY)`) chưa viết.
- **`settled` không cap.** Đo ~561 B/đơn; chạy dài sẽ phình. Giải pháp là bảng DB có retention, **không** phải eviction trong RAM.
- **43 mutant sống** (`reports/mutation/mutation.json`, đã xoá cùng rác — chạy `bun run mutate` để sinh lại). Đáng chú ý: nhánh `if (!representable(priced)) throw` trong `render()` bị mutant `if (false)` sống ⇒ chưa có test chứng minh `render()` ném; hiện chỉ chặn ở `checkout()` trước khi gọi store.
- **`extensions/fe-gate.ts` không qua `tsconfig` mới** (5 lỗi `noPropertyAccessFromIndexSignature` + handler type). Nằm ngoài phạm vi; cần một lượt riêng.
- **Playbook mới chưa publish** lên plugin đã cài, nên `skill://fe-kit/playbooks/review-invariants.md` chưa resolve; đường dẫn repo dùng được.
- **A7 trên fixture:** bắt 5/6 lớp lỗi (G1, G2, G4, G5, G6). G3 không chứng minh được trên plain object — ghi là unproven, không phải đã sạch.

## 6. Q&A

- Q: Ai giữ state của tồn kho và receipt (chỗ phải sửa đầu tiên khi "trừ kho sai")? A: `MemoryCheckoutStore` — chỉ trong `store.ts`, `checkout.ts` không giữ gì.
- Q: Nhánh nào dễ bị sửa hỏng nhất khi có người "tối ưu" sau này? A: Nhánh `short` trong `settle()` — phải kiểm toàn bộ reservation trước khi trừ đồng nào.
- Q: Khi response của `checkout()` đổi shape, caller nào hỏng trước? A: Không có caller thật trong repo — chỉ test và script probe; đổi shape phá 58 test trước tiên.
- Q: Lệnh nào là bằng chứng một fix về trừ kho/tiền là đúng? A: `bun run gates` — gồm cả mutation ≥ 80%, vì test xanh vẫn có thể là test rỗng.

Confirmed-by: nhathoang
Confirmed-at: 2026-11-22T09:24:13Z
