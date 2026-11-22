# Agent rules — devin-dev-kit

## Trước khi báo xong
Chạy và báo **lệnh + exit code** cho từng cổng dưới đây. Một cổng đỏ thì chưa xong.

```bash
bunx tsc --noEmit -p tsconfig.json
bunx eslint extensions/checkout --max-warnings 0
bun test extensions/checkout
```

## Checkout (`extensions/checkout/`)
- Đọc `extensions/checkout/SPEC.md` trước khi sửa. Đó là hợp đồng: bất biến `INV-01…09`, threat model, rubric severity.
- Input chỉ vào qua `readOrder()` trong `schema.ts`. Không validate lại ở chỗ khác, không tự chuẩn hoá ngoài schema.
- Idempotency và trừ kho chỉ qua `CheckoutStore.attempt()`. **Không** thêm Map/LRU/tombstone dedupe trong process — lớp lỗi đó đã sinh 11 blocker.
- Key/digest chỉ tạo trong `canonical.ts`. Không `JSON.stringify`, không `join`, không digest tự chế.
- Mọi field tiền đi qua `representable()` **trước** khi chạm kho.
- Type vùng/tier lấy từ schema (`Region`, `Tier`); hằng số dùng `as const satisfies Record<Region, …>`.
- Giữ phần thuần (schema, canonical, pricing) tách khỏi phần có tác dụng phụ (store).

## Sửa lỗi
- Test đỏ trước, sửa sau. Không sửa test đã có trong cùng PR fix.
- Repro là **test trong repo**, không phải script `/tmp`.
- Cùng một cơ chế bị sửa lần thứ hai mà vẫn sinh finding cùng nhóm → **dừng vá**, viết ghi chú thiết kế lại.
- Mỗi fix một commit: `fix(checkout): <F-xxx> <tóm tắt>`.

## Không làm
- Không import `extensions/nested-if.ts` — đó là fixture đối chứng của tool review, không phải code sản phẩm.
- Không thêm eviction cho `receipts`/`settled` để "giảm bộ nhớ": evict receipt làm replay trừ kho lần hai.
