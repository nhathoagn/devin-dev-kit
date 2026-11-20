# fowler-checklist.md

Checklist maintainability theo 6 nhóm refactor của Fowler (*Refactoring*, 2nd ed). Reviewer đi từng mục, trả **PASS** / **FAIL** / **N/A** giống `REVIEW_CHECKLIST.md`. 28 items, F1a–F6c.

Checklist này chỉ chấm **cấu trúc**. Correctness, security, test, perf nằm ở `REVIEW_CHECKLIST.md` (nhóm C, SEC, P, T). Một diff có thể PASS hết đây mà vẫn có bug — và ngược lại, code FAIL cấu trúc vẫn có thể đúng. Hai checklist đi kèm, không thay thế nhau. Verdict borderline: ghi FAIL kèm "borderline" trong câu why — không có verdict thứ tư; khi do dự giữa PASS và FAIL, chọn FAIL.

`smells-checklist.md` đi theo chiều ngược lại: index 24 mùi của ch.3 (SM1–SM24) để phát hiện và đặt tên — file này chấm theo nhóm refactor, file kia nhìn theo triệu chứng. `posd-checklist.md` thêm lăng kính Ousterhout (O1–O16): độ sâu module, pull-complexity-down, define-errors-out — các câu hỏi hai file Fowler không hỏi.

Comment viết theo cấu trúc `smell → refactor → vì sao`, ví dụ:

> `shipClassState` đọc 4 field của `entry`, ghi 1 — Feature Envy (F2). Đề xuất Move Method sang `ShipEntry`.

---

## F1 · Composing Methods — hàm xấu bên trong

Mùi: hàm dài, ý đồ chìm trong chi tiết, biến tạm rối.

- [ ] **F1a** Test ý đồ đọc được không. FAIL nếu phải đọc chi tiết mới hiểu hàm làm gì. Đề xuất Extract Method / Extract Variable. Không có hàm mới/sửa thì N/A.
- [ ] **F1b** Test biến tạm dùng một lần. FAIL nếu `const x = expr` rồi chỉ dùng `x` đúng 1 chỗ mà `expr` ngắn. Đề xuất Inline Temp. Không có thì PASS.
- [ ] **F1c** Test một loop hai việc. FAIL nếu loop vừa tính vừa tích lũy vừa ghi, khó extract. Đề xuất Split Loop. Không có loop thì N/A.
- [ ] **F1d** Test biến tạm gán lại qua nhánh. FAIL nếu một `let` bị gán lại ở 2+ nhánh điều kiện và giá trị cuối phụ thuộc nhánh nào chạy — người đọc phải trace từng nhánh để biết state cuối. Đề xuất Split Temporary Variable thành một biến mỗi khái niệm, hoặc Replace Temp with Query (extract tính toán ra hàm/query trả giá trị). Không có temp gán lại thì PASS.

## F2 · Moving Features — trách nhiệm đặt sai chỗ

Mùi: hàm sống trên data của người khác (Feature Envy), file/class gánh hai việc.

- [ ] **F2a** Test Feature Envy. FAIL nếu hàm đọc/ghi field của một object khác nhiều hơn của receiver/class chứa nó — kể cả free function mà param đầu đóng vai `this` (method in exile). Đề xuất Move Method. Move phải tôn trọng layer rule của repo: không move làm shared phụ thuộc feature. Nếu object bị envy là record/interface không có method, move function vào module sở hữu record trong cùng feature. Không có hàm sờ object khác thì N/A.
- [ ] **F2b** Test class/file hai việc. FAIL nếu file đang hoặc sẽ giữ hai trách nhiệm — không chỉ khi diff thêm trách nhiệm thứ hai. Đề xuất Extract Class hoặc file mới theo `rules/modules.md` (D9 trùng nhưng đây là gốc Fowler). File một việc thì PASS.
- [ ] **F2c** Test delegate xâu. FAIL nếu caller phải `a.b.c.d()` nhiều tầng để làm việc của `a` — gồm cả `a.b.c` hai hop khi method đầu giấu được cả walk. Đề xuất Hide Delegate. Không có thì N/A.
- [ ] **F2d** Test Middle Man. FAIL nếu component/function chỉ forward sang target mà Reuse chưa flag. Đề xuất Remove Middle Man — caller gọi target trực tiếp. Ngược với F2c: F2c giấu chain vào method, F2d xóa wrapper thừa. Không có forwarder thì N/A.

## F3 · Organizing Data — data tổ chức sai

Mùi: primitive làm việc của type, giá trị đi lẻ, shared mutable reference.

- [ ] **F3a** Test primitive thay type. FAIL nếu string/number đang chứa domain concept có giá trị hữu hạn hoặc rule riêng (ví dụ `displayMode: string` nhận `'1'|'2'`). Đề xuất union type hoặc Replace Data Value with Object. Chỉ đề xuất type repo đã có hoặc union literal — không invent type mới repo chưa có. Không có thì N/A.
- [ ] **F3b** Test magic value. FAIL nếu literal cứng có nghĩa business (giống N3). Đề xuất named constant hoặc Replace Type Code with Class/enum. Không có thì N/A.
- [ ] **F3c** Test shared mutable constant. FAIL nếu gán `x = CONST_OBJECT` (by-ref) rồi một nơi khác `{...CONST}` — bất đối xứng là lỗ chờ mutate. Đề xuất `Object.freeze` hoặc spread đồng nhất. Không có object const thì N/A.
- [ ] **F3d** Test giá trị đi lẻ. FAIL nếu 3+ biến luôn đi cùng nhau qua call chain mà không có object bọc. Đề xuất Introduce Parameter Object (gốc ở đây, dùng chung F5c). Không có thì N/A.
- [ ] **F3e** Test field song trùng. FAIL nếu record giữ field mirror của field khác (`x` và `x_keep`, `x` và `x_old`) đọc/ghi xen kẽ trong cùng luồng mà không có snapshot object rõ ràng bọc chúng. Đề xuất gom các field gốc vào một snapshot object (`original`, `keep`) thay vì hậu tố trên từng field. Không có field song trùng thì N/A.

## F4 · Simplifying Conditionals — nhánh xấu

Mùi: nesting, điều kiện lặp, flag rối, `null` check khắp nơi.

- [ ] **F4a** Test guard clause. FAIL nếu nhánh đặc biệt chôn trong else sâu thay vì return sớm. Đề xuất Replace Nested Conditional with Guard Clauses. Case ≤3 nhánh phẳng thì PASS.
- [ ] **F4b** Test nhánh cùng kết quả. FAIL nếu 2+ điều kiện ra cùng một xử lý mà viết tách. Đề xuất Consolidate Conditional (`||`). Ngược lại: FAIL nếu `||` đang gom hai điều kiện mang nghĩa domain khác nhau (ví dụ `next === '' || next === keep` khi "clear" và "unchanged" là hai case khác nhau) — tách thành named predicates (`isCleared`, `isUnchanged`). Không có thì N/A.
- [ ] **F4c** Test điều kiện lặp. FAIL nếu cùng predicate hoặc expression xuất hiện ở 2+ chỗ trong diff. Đề xuất Decompose Conditional thành hàm/biến đặt tên. Không có thì N/A.
- [ ] **F4d** Test null check lặp. FAIL nếu `if (x == null)` rải ở nhiều call site cùng một object. Đề xuất Introduce Null Object hoặc optional chain ở boundary. Không có thì N/A.
- [ ] **F4e** Test nên thành table/polymorphism. FAIL nếu dispatch theo một key mà viết if-else 5+ nhánh đồng cấu trúc, hoặc cùng một `if`/`switch` trên một type lặp ở 2+ file. Đề xuất lookup table hoặc Replace Conditional with Polymorphism. Dưới 5 nhánh một chỗ thì PASS.
- [ ] **F4f** Test else-if không đầy đủ. FAIL nếu chain không có else/default và có combo input rơi qua mọi nhánh trong khi phần còn lại của hàm vẫn chạy (ví dụ field A vẫn bị ghi nhưng lock giữ giá trị cũ). Mỗi combo không khớp phải có lý do rõ ràng hoặc default rõ ràng. Chain có else cuối, hoặc rơi qua là behavior có chủ đích, thì PASS.

## F5 · Simplifying Calls — interface giữa hàm xấu

Mùi: param lẻ nhiều, một hàm vừa hỏi vừa làm, tên không nói contract.

- [ ] **F5a** Test param count. FAIL nếu signature >4 param lẻ không có lý do. Đề xuất Introduce Parameter Object. Không đổi signature thì N/A.
- [ ] **F5b** Test Command-Query tách. FAIL nếu hàm tên `get*`/`find*`/`load*` mà trong thân có side-effect ghi, hoặc ngược lại. Đề xuất Separate Query from Command. Không có hàm đọc thì N/A.
- [ ] **F5c** Test tham số đi chùm. FAIL nếu caller nào cũng truyền cùng một cụm `(mode, displayMode)` — nên là một object. Trùng F3d; đếm 1 lần. Không có thì N/A.
- [ ] **F5d** Test tên hàm nói contract. FAIL nếu phải đọc body mới biết hàm trả/ghi gì. Đề xuất Rename Function. Không có hàm mới thì N/A.
- [ ] **F5e** Test param dễ nhầm. FAIL nếu hai param liền nhau cùng type và cùng họ tên (ví dụ `mode, displayMode`) — caller swap được mà compiler không bắt. Đề xuất đổi tên phân biệt hoặc bundle vào một object. Không có thì N/A.
- [ ] **F5f** Test spread-merge ghi đè ngầm. FAIL nếu object kết quả được dựng bằng nhiều spread liên tiếp (`{ ...a, fields, ...b(...) }`) mà source sau có thể mang key trùng source trước — key bị ghi đè câm, thứ tự spread là contract ẩn. Đề xuất đặt tên key rõ hoặc merge tường minh cho phần overlap. Không có spread chain thì N/A.

## F6 · Dealing with Generalization — kế thừa xấu

Mùi: kế thừa chỉ để reuse, hierarchy nông vô nghĩa, hai class giống nhau không chung base.

- [ ] **F6a** Test kế thừa vì reuse. FAIL nếu subclass không thỏa is-a mà chỉ mượn code cha, hoặc subclass thỏa is-a nhưng bỏ qua phần lớn surface cha (Refused Bequest). Đề xuất Replace Inheritance with Delegation hoặc composition. Không có subclass mới thì N/A.
- [ ] **F6b** Test hierarchy nông. FAIL nếu subclass chỉ override 1 method nhỏ hoặc khác cha gần như không. Đề xuất Collapse Hierarchy. Không có thì N/A.
- [ ] **F6c** Test code lặp giữa anh em. FAIL nếu 2 subclass copy cùng method/field. Đề xuất Pull Up Method/Field. Không có thì N/A.

---

## Khi nào chạy

| Diff | Nhóm nên chạy |
|---|---|
| <50 dòng, sửa hàm sẵn | F1, F4, F5 |
| File mới / feature mới | Cả 6 |
| Pure move/rename | F2 + nhóm R ở `REVIEW_CHECKLIST.md` (F Fowler không đủ) |

## Giới hạn

- Không chấm correctness — nhánh logic sai vẫn PASS cấu trúc.
- Không chấm security/perf/test — dùng `REVIEW_CHECKLIST.md`.
- "Nên refactor X" là **gợi ý**, không phải verdict — major trở xuống. Blocker phải do correctness/security, không phải do mùi.
