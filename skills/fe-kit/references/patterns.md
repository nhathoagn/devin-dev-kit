# patterns.md

Từ điển tra thuận `tín hiệu → pattern` theo *Head First Design Patterns* (GoF qua JS). **Không phải checklist** — không có PASS/FAIL; đây là bảng tra khi một FAIL trong `smells-checklist.md`/`fowler-checklist.md`/`posd-checklist.md` cần cure lớn hơn một tidying.

Luật đầu bảng: **pattern là cure cho vấn đề có thật hôm nay, không phải mục tiêu**. "Sau này sẽ cần" = SM17 Speculative Generality / O7 Special-General Mixture / D3 — tìm thấy pattern phù hợp nhưng không có điều kiện áp thì câu trả lời là *đừng áp*. Cấu trúc là option (Beck): chỉ mua option cho chỗ thay đổi sẽ đến.

Finding viết theo `tín hiệu → pattern → điều kiện áp có đứng không`:

> `switch (bird.type)` lặp 3 hàm → Strategy — đứng vì có 3 biến thể thật và caller cần thêm loại mới không sửa hàm cũ.

---

## Nhóm 1 · Hành vi biến thể

| Tín hiệu trong code | Pattern | Áp khi | Đừng áp khi |
|---|---|---|---|
| `if`/`switch` trên type/flag để chọn thuật toán, lặp ở nhiều chỗ | **Strategy** — mỗi biến thể một object cùng interface, inject vào | Có ≥2 biến thể thật + cần đổi/thêm biến thể không sửa caller. Chữa SM19 Repeated Switches, SM21 phần nào | Chỉ 1 biến thể — Strategy cho một impl = SM17. Biến thể khác nhau ở *dữ liệu* không phải *thuật toán* → lookup table đủ |
| `if`/`switch` trên `this.state` rải khắp; transition rules trộn trong nghiệp vụ | **State** — mỗi trạng thái một object tự quyết hành vi + chuyển tiếp | Nhiều state + transition phức tạp; quan trọng: state biết nó sang đâu tiếp (khác Strategy — caller không chọn) | 2–3 trạng thái đơn giản → cờ/enum đủ. Hành vi do *caller* chọn → đó là Strategy, không phải State |
| 2+ class cùng skeleton flow, khác vài bước | **Template Method** — superclass giữ flow, subclass cài hooks (Hollywood: cha gọi con) | Flow cố định, chỉ bước đổi + quan hệ is-a thật | Cần đổi cả flow runtime → Strategy. Chỉ 1 implementation → SM17. Subclass phải gọi cha → dependency ngược, dấu hiệu sai chỗ |
| Hành vi đổi khi tạo ra là do param — không cần subclass | **Param injection** (JS nhẹ hơn pattern) — truyền hàm/config vào | Khác biệt nhỏ, JS first-class function đủ | Đã thành class family phức tạp → lúc đó mới cần Strategy |

## Nhóm 2 · Tạo object

| Tín hiệu trong code | Pattern | Áp khi | Đừng áp khi |
|---|---|---|---|
| `new ConcreteX()` rải nhiều nơi theo type; caller biết quá nhiều về việc tạo | **Factory Method** / factory function — hàm trả instance theo tham số, caller chỉ thấy interface | Caller không nên biết concrete class; sẽ thêm loại mới (thêm case ở một chỗ). Chữa SM19 ở tầng tạo | Một concrete class duy nhất → `new` thẳng đủ. Factory bọc một new = Lazy Element (SM16) |
| Nhóm object phải đi cùng nhau nhất quán (dough+sauce+cheese cùng vùng; theme+font+lang cùng locale) | **Abstract Factory** — một factory trả cả *họ* | Có ràng buộc chéo giữa các member của family — trộn nửa NY nửa Chicago là sai | Không có ràng buộc giữa members → từng factory riêng rẻ hơn |
| Cần đúng một instance chia sẻ | **Singleton** — trong JS: `export const x = new X()` — module cache đã là singleton | Resource thật sự một (connection pool, registry) | Để che global mutable state → đó là SM6 Global Data và U5 làm test fragile, không phải pattern hợp lệ |

## Nhóm 3 · Quan hệ giữa objects

| Tín hiệu trong code | Pattern | Áp dụng khi | Đừng áp khi |
|---|---|---|---|
| "X đổi thì Y và Z phải cập nhật" viết tay bằng calls rải khắp | **Observer** — subject giữ set listener, đổi thì notify | Một-nhiều, listener thêm/bớt động; JS: EventEmitter, `addEventListener`, store subscribe sẵn có | Hai object một-một cố định → call trực tiếp. Quên unsubscribe = leak — pattern này đi kèm lifecycle cleanup |
| Tổ hợp trách nhiệm → class explosion (MochaWhipSoyLatte) hoặc cần stack runtime | **Decorator** — wrapper cùng interface, mỗi lớp cộng phần mình | Cần xếp chồng trách nhiệm lúc runtime, giữ nguyên interface ngoài. Chữa SM5 dạng tổ hợp | Combos ít và cố định → vài class thường. Caller cần biết concrete type của lớp bọc → lộ wrapper, sai chỗ |
| Class/3rd-party làm đúng việc nhưng interface lệch | **Adapter** — lớp bọc đổi interface sang dạng client cần | Không sửa được source (vendor, legacy); muốn một chỗ duy nhất chịu impedance mismatch | Sửa interface gốc rẻ hơn → sửa thẳng. Adapter giữ lâu mà hai phía đều kiểm soát được = Middle Man tiềm ẩn (SM14) |
| Client phải tự điều phối nhiều object của subsystem | **Facade** — một interface mức cao che cả cụm | Caller chỉ cần việc mức cao (`watchMovie()` thay 7 lệnh); giảm tiếp xúc SM13/SM15 | Facade chỉ forward từng call mà không gom việc → Middle Man (SM14/O5), xóa đi gọi thẳng |
| Request cần undo/queue/log/macro, hoặc invoker không nên biết receiver | **Command** — request thành object `{ execute, undo }` | Invoker tách khỏi receiver; request có lifecycle (queue, retry, log); gom macro | Một call đơn giản → gọi thẳng — Command bọc một call = Replace Command with Function (Fowler ch.11) |
| Object đắt/từ xa/cần guard mà caller không nên biết | **Proxy** — đại diện cùng interface: lazy init, access control, remote stub — JS có `Proxy` native | Lazy-load object nặng, check quyền trước khi chạm, client API bọc fetch | Logic guard/init có chỗ đứng rõ hơn (constructor, middleware) → đừng intercept nếu không cần |
| Cây part-whole, client cần xử lý lá và nhánh đồng nhất | **Composite** — mọi node cùng interface (`item` và `menu` đều `.print()`) | Client không nên phân biệt node lá/nhánh — React component tree là ví dụ | Client *phải* phân biệt lá/nhánh → ép đồng nhất làm giao diện mập mờ, type guard thẳng rõ hơn |

## Nhóm 4 · Pattern JS đã hút vào ngôn ngữ — đừng build tay

| Pattern | Dạng JS sẵn có | Ghi chú |
|---|---|---|
| Iterator | `for...of`, `Symbol.iterator`, `map`/`filter`/`reduce`, generators | Viết generator/collection thường; class Iterator thủ công = SM16 |
| Observer | `EventEmitter`, `addEventListener`, `new Proxy` trap, store `.subscribe` | Xem hàng Observer ở trên |
| Singleton | `export const instance = new X()` | Module cache đảm bảo một instance |
| MVC | Compound pattern: Model=Observer + Controller=Strategy + View=Composite | Không cần "triển MVC" như một pattern riêng — nó là kết quả pattern đi theo bầy |

---

## Khi nào mở bảng này

| Tình huống | Dùng |
|---|---|
| Refactor (`playbooks/refactor-ui.md`): FAIL nào đó có cure lớn hơn tidying | Tra tín hiệu → pattern → kiểm cột "Đừng áp khi" trước khi đề xuất |
| Thiết kế interface/hệ thống mới | Chỉ áp pattern cho vấn đề *đang có*; phần "sau này" để SM17/O7 cảnh giác |
| Review diff | Pattern được áp đúng = không finding; pattern ép vào chỗ không cần = ghi SM17/O7 kèm hàng này |
| Đặt tên | Gọi đúng tên pattern trong code (`XStrategy`, `YAdapter`, `ZFactory`) — tên là từ vựng chung của team |

## Giới hạn

- Bảng này là **hướng đề xuất**, không phải verdict — cột "Đừng áp khi" thắng cột "Áp khi" khi do dự.
- 9 pattern GoF còn lại (Bridge, Builder, CoR, Flyweight, Interpreter, Mediator, Memento, Prototype, Visitor) sách chỉ lướt — gặp tín hiệu tương ứng thì tra catalog đầy đủ, bảng này không cover.
- Áp pattern là thay đổi cấu trúc — behavior giữ nguyên, test phải xanh trước và sau; nếu test vỡ mà behavior không đổi thì test đang pin vào implementation (U1).
- Severity: đề xuất pattern tối đa minor — quyết định cuối cùng nằm ở người own feature, không phải bảng tra.
