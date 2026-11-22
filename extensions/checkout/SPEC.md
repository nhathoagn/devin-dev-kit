# SPEC — checkout

Nguồn chân lý cho module `extensions/checkout/`. Reviewer chấm theo file này, không theo cảm nhận.
Đổi file này là đổi hợp đồng: cần người duyệt, không nằm trong PR fix.

## 1. Phạm vi

| Trong phạm vi | Ngoài phạm vi |
|---|---|
| JSON thường đến từ mạng: mọi giá trị JSON hợp lệ, kể cả key `__proto__`, số rất lớn, chuỗi rỗng, mảng rỗng, `null` | `Proxy`, getter/setter tự định nghĩa, object đã `freeze`, `Symbol`, `BigInt`, hàm — tức object do code nội bộ truyền vào |
| Nhiều request đồng thời trên cùng store | Nhiều process/instance chia sẻ store (adapter phải tự lo, xem §5) |
| Store bộ nhớ cho test, store DB cho production | Tính đúng của chính DB (transaction isolation do DB lo) |

Finding cần input ngoài phạm vi: tối đa `minor`. Không có ngoại lệ.

## 2. Input hợp lệ

Không viết lại bằng lời. Nguồn: `extensions/checkout/schema.ts`.

- `id`: chuỗi, trim, **lowercase**, 1–64 ký tự, chỉ `[a-z0-9._:-]`.
- `items`: 1–500 phần tử, mỗi phần tử `strictObject{sku, qty, price}` — `qty`/`price` là **số nguyên an toàn** 1…1e9; tổng từng dòng và tổng đơn phải là số nguyên an toàn.
- `customer`: `strictObject{id, tier, email, region, vip}`; `tier ∈ {gold, silver, bronze}`, `region ∈ {north, south, central}`, `email` khớp `x@y.z`, `vip` boolean.
- `couponCode`, `express`, `giftWrap`, `note`: optional, `null` = không có.
- **Key lạ ở mọi tầng bị từ chối.**

## 3. Bất biến

Mỗi bất biến phải có ít nhất một test đỏ được khi nó bị phá. Reviewer dùng đúng mã `INV-xx`.

| Mã | Bất biến | Test chặn |
|---|---|---|
| INV-01 | Tồn kho không bao giờ âm | `stock never goes negative` (property) |
| INV-02 | Một idempotency key trừ kho đúng một lần, dù replay bao nhiêu lần | `a settled payload deducts exactly once…` (property), `concurrent attempts on one key settle exactly once` |
| INV-03 | Một cart trừ tất cả hoặc không trừ gì | `never deducts part of a cart`, `a short cart leaves every sku untouched` |
| INV-04 | Cùng key khác payload → conflict, không replay, không trừ | `the same id with a different payload is a conflict…`, `a conflict under concurrency still deducts nothing` |
| INV-05 | Mọi field tiền là số nguyên an toàn ≥ 0 và `grandTotal = total − discount + shipping + tax` | `money stays integral and self-consistent` (property), `money above the safe-integer range is refused…` |
| INV-06 | Đơn `ok` làm giảm stock đúng bằng tổng qty | `an ok result moves stock by exactly the ordered quantity` (property) |
| INV-07 | Receipt bất biến: caller sửa kết quả không làm bẩn replay | `a receipt is immutable…` |
| INV-08 | Đơn bị từ chối không để lại receipt; restock rồi retry được | `a rejected attempt leaves no receipt…` |
| INV-09 | Hai kênh có không gian key riêng; luật phí/coupon giống nhau trừ chỗ §4 ghi khác | `retail and b2b key spaces do not collide`, `b2b still charges express and gift wrap`, `an unknown coupon is rejected on both channels` |

## 4. Luật giá (khác nhau giữa kênh phải ghi ở đây)

| Luật | retail | b2b |
|---|---|---|
| Chiết khấu | bậc theo tier + VIP 5% + coupon phẳng, trần 30% và ≤ total | phẳng 20%, ≤ total |
| Phí vùng | theo `region` | 0 |
| Express 50 000 / gift-wrap 15 000 | cộng thêm | **cộng thêm** (giữ nguyên từ F-074) |
| Miễn phí vùng | coupon `FREESHIP` hoặc `total ≥ 1 000 000` (phụ phí vẫn thu) | luôn 0 |
| Coupon | áp dụng | chỉ **validate**, không áp dụng |
| Thuế | 8% của `total − discount`; vùng `south` ×1.1, làm tròn **một lần** | như retail |

## 5. Danh tính đơn (canonical)

`canonical.ts` sinh digest từ: `id`, các dòng đã gom theo `(sku, price)` và sắp xếp, `customer.{id,tier,region,vip}`, `email`, `couponCode`, `express`, `giftWrap`, `note`.

- Thứ tự dòng và việc tách/gộp dòng cùng `(sku, price)` **không** đổi danh tính.
- Sửa `note`/`email` **đổi** danh tính → cùng id khác payload trả conflict. Đây là chủ ý: danh tính đơn gồm mọi field người dùng gửi.
- Key idempotency = `channel + ":" + orderId`; digest chỉ dùng để phát hiện payload khác.

## 6. Hợp đồng store

`CheckoutStore.attempt(entry): Promise<AttemptOutcome>` phải, trong **một** đơn vị công việc:

1. Nếu key đã có: digest khác → `conflict`; digest trùng → `replay` (bản copy).
2. Nếu chưa có: kiểm **toàn bộ** reservation; thiếu bất kỳ sku nào → `short` kèm danh sách, **không** trừ gì.
3. Đủ hàng: gọi `render()`, trừ kho, lưu receipt — cả ba hoặc không cái nào.

Crash ở bất kỳ bước nào phải để lại stock và key **không đổi**. Adapter DB: `receipts(key PRIMARY KEY, digest, result, created_at)` + `UPDATE stock SET qty = qty - $1 WHERE sku = $2 AND qty >= $1` trong cùng transaction; 0 dòng → rollback và trả `short`.

## 7. Rubric severity

| Mức | Định nghĩa | Chặn merge |
|---|---|---|
| blocker | Vi phạm INV với input **trong** phạm vi, có test repro, gây sai tiền/kho/mất dữ liệu | có |
| major | Vi phạm INV cần điều kiện hiếm nhưng trong phạm vi; hoặc sai kết quả không liên quan tiền | có |
| minor | Input ngoài phạm vi; chẩn đoán/message kém; trùng lặp code | không |
| nit | Đặt tên, style | không |

## 8. Điều kiện dừng

Merge khi: `tsc` xanh, `eslint` xanh, toàn bộ test xanh, mọi INV ở §3 có test, mutation score ≥ 80%, và lượt review cuối không sinh fingerprint mới thuộc mức chặn merge.
Tối đa 3 lượt review sau lượt đầu. Hết ngân sách mà còn fingerprint mới → dừng, báo người: vấn đề ở spec/thiết kế, không phải code.
