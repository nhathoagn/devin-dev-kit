# smells-checklist.md

Index 24 code smells của Fowler (*Refactoring*, 2nd ed, ch.3), dùng để **phát hiện** mùi khi đọc code và đặt tên cho finding. Mỗi mục trả **PASS** / **FAIL** / **N/A** giống `REVIEW_CHECKLIST.md`. 24 items, SM1–SM24, theo 7 nhóm.

File này là **bản đồ phát hiện**; `fowler-checklist.md` là bản chấm theo 6 nhóm refactor. Nhiều mùi đã có item tương đương ở `fowler-checklist.md` hoặc `REVIEW_CHECKLIST.md` — item nào trùng ghi chú ngay ở mục đó, đếm một lần, không nhân đôi finding.

Finding viết theo cấu trúc `smell → refactor → vì sao`:

> `SM12 Feature Envy`: `monthlyCost()` đọc 3 field của `sub`, ghi 0 của mình — Move Function về `Subscription`.

---

## Nhóm 1 · Cấu trúc / độ dài

- [ ] **SM1 Mysterious Name** Test tên symbol. FAIL nếu phải đọc body hoặc call site mới biết hàm/biến/class làm gì — tên chung chung (`data`, `calc`, `handle`, `temp`) hoặc tên nói sai việc nó làm. Không nghĩ ra tên hay thường là dấu hiệu làm hai việc → extract trước rồi mới đặt tên. Đề xuất Rename Variable/Field, Change Function Declaration. Trùng F5d; đếm 1 lần. Không có symbol mới/đổi thì N/A.
- [ ] **SM2 Duplicated Code** Test code trùng. FAIL nếu cùng cụm statement xuất hiện 2+ chỗ trong phạm vi (mỗi bản là một chỗ phải nhớ sửa). Đề xuất Extract Function; lặp giữa anh em class → Pull Up Method; lặp quanh chỗ gọi → Move Statements into Function. Trùng D2 và `rules/reuse-duplication.md`; đếm 1 lần. Không có thì PASS.
- [ ] **SM3 Long Function** Test ý đồ hàm. FAIL nếu hàm trộn 2+ mức abstraction, hoặc có đoạn cần comment để giải thích — đoạn đó là hàm con chờ Extract. Độ dài chỉ là dấu hiệu, không phải verdict: hàm dài một mức abstraction thì PASS. Đề xuất Extract Function, Replace Temp with Query, Decompose Conditional. Trùng F1a; đếm 1 lần. Không có hàm trong phạm vi thì N/A.
- [ ] **SM4 Long Parameter List** Test signature. FAIL nếu >4 param lẻ, hoặc caller phải tính hộ thứ callee tự lấy được, hoặc một cờ boolean/chuỗi rẽ nhánh ý đồ hàm. Đề xuất Introduce Parameter Object, Replace Parameter with Query, Remove Flag Argument, Preserve Whole Object. Trùng F5a/F5c/F5e; đếm 1 lần. Không đổi signature thì N/A.
- [ ] **SM5 Large Class** Test trách nhiệm class/file. FAIL nếu giữ 2+ lý do để sửa — dấu hiệu: một nhóm field+method luôn đi cùng nhau. Đề xuất Extract Class, Extract Superclass, hoặc file mới theo `rules/modules.md`. Trùng F2b/D9; đếm 1 lần. File một việc thì PASS.

## Nhóm 2 · Dữ liệu

- [ ] **SM6 Global Data** Test mutable tầm module trở lên. FAIL nếu biến module-level được ghi từ >1 nơi mà không qua hàm — điểm đổi không truy được. Đề xuất Encapsulate Variable (mọi truy cập qua get/set, trả copy nếu mutable). Không có global mutable thì N/A.
- [ ] **SM7 Mutable Data** Test side effect. FAIL nếu hàm hỏi đổi state, một biến bị gán lại cho nhiều mục đích, hoặc field đổi được sau khi tạo dù không cần. Đề xuất Separate Query from Modifier, Split Variable, Remove Setting Method, Replace Derived Variable with Query. Trùng F5b/F1d; đếm 1 lần. Không có thì N/A.
- [ ] **SM8 Data Clumps** Test cụm data đi cùng nhau. FAIL nếu 2-3+ giá trị luôn truyền/gán cùng nhau (start/end, lat/lng, first/last) mà không có object bọc — khái niệm domain chưa được đặt tên. Đề xuất Introduce Parameter Object, Extract Class, Preserve Whole Object. Trùng F3d/F5c; đếm 1 lần. Không có thì N/A.
- [ ] **SM9 Primitive Obsession** Test primitive mang domain rule. FAIL nếu string/number chứa khái niệm có hành vi riêng (validate, format, so sánh: tiền, SĐT, email, range) mà rule đó rải ở call site. Đề xuất Replace Primitive with Object, union type, hoặc type repo đã có — không invent type mới. Trùng F3a; đếm 1 lần. Không có thì N/A.

## Nhóm 3 · Thay đổi (cặp đối lập)

- [ ] **SM10 Divergent Change** Test lý do sửa file. FAIL nếu một file/module bị sửa vì nhiều lý do độc lập (đổi schema sửa nó, đổi wording mail cũng sửa nó) — ôm nhiều trách nhiệm theo trục thời gian. Đề xuất Split Phase, Extract Class, Move Function theo từng lý do. Gần SM5 nhưng nhìn *lý do thay đổi*, không nhìn cấu trúc tĩnh. Không đọc được lịch sử sửa thì N/A.
- [ ] **SM11 Shotgun Surgery** Test chiều ngược lại. FAIL nếu một thay đổi nghiệp vụ buộc sửa 3+ file không liên quan — tri thức một việc rải khắp codebase (thêm `type` mới phải săn 4 file `if`). Đề xuất Move Function/Field gom lại, Combine Functions into Class/Transform. Không có thay đổi đa-file trong phạm vi thì N/A.

## Nhóm 4 · Quan hệ giữa objects

- [ ] **SM12 Feature Envy** Test hàm sống trên data người khác. FAIL nếu hàm đọc/ghi member của object khác nhiều hơn của chủ nó — kể cả free function có param đóng vai `this`. Đề xuất Move Function; chỉ một phần envy thì Extract phần đó rồi move. Trùng F2a; đếm 1 lần. Không có thì N/A.
- [ ] **SM13 Message Chains** Test chuỗi `a.b.c.d`. FAIL nếu caller bước qua 2+ lớp cấu trúc để làm việc của `a` — mỗi mắt là một coupling, đứt một mắt hỏng cả chuỗi. Đề xuất Hide Delegate (thêm method hỏi ở mặt ngoài), Extract + Move Function. Trùng F2c; đếm 1 lần. Không có thì N/A.
- [ ] **SM14 Middle Man** Test forwarder thừa. FAIL nếu hàm/class/component chỉ chuyển tiếp call không thêm gì — thường là dư của chữa SM13 quá tay. Đề xuất Remove Middle Man, Inline Function. Trùng F2d; đếm 1 lần. Không có forwarder thì N/A.
- [ ] **SM15 Insider Trading** Test mò internals. FAIL nếu code đọc/ghi phần nội bộ của module khác (field `_private`, object lồng, mảng ruột) thay vì qua API — hai module biết chuyện riêng của nhau. Đề xuất Move Function/Field giảm tiếp xúc, Hide Delegate, Replace Subclass/Superclass with Delegate. Không có thì N/A.

## Nhóm 5 · Code không cần thiết

- [ ] **SM16 Lazy Element** Test phần tử không trả được tiền thuê. FAIL nếu hàm/wrapper/class được tách ra nhưng không thêm ý nghĩa — body một dòng trùng tên, wrapper bọc một call. Đề xuất Inline Function/Class, Collapse Hierarchy. Gần SM14; SM14 nhìn forwarder giữa hai object, SM16 nhìn mọi phần tử thừa. Không có thì PASS.
- [ ] **SM17 Speculative Generality** Test trừu tượng suy đoán. FAIL nếu thêm param, hook, subclass, abstraction "để sau này dùng" mà hiện không có consumer — YAGNI. Đề xuất xóa: Collapse Hierarchy, Inline, Change Function Declaration bỏ param thừa, Remove Dead Code. Trùng D3; đếm 1 lần. Không thêm thì PASS.
- [ ] **SM18 Temporary Field** Test field có điều kiện. FAIL nếu field/state chỉ có nghĩa trong một nhánh của lifecycle, còn lại `null`/`undefined` — object có state machine ngầm người đọc phải tự suy ra. Đề xuất Extract Class gom field tạm + logic dùng nó, Introduce Special Case. Không có thì N/A.

## Nhóm 6 · Điều kiện / vòng lặp

- [ ] **SM19 Repeated Switches** Test cùng điều kiện rải nhiều chỗ. FAIL nếu một `switch`/`if` trên cùng type-code lặp ở 2+ chỗ — thêm case phải săn tay, compiler im lặng. Đề xuất Replace Conditional with Polymorphism hoặc lookup table. Trùng F4e; đếm 1 lần. Switch một chỗ thì PASS.
- [ ] **SM20 Loops** Test loop che ý định. FAIL nếu `for`/`forEach` tay làm một biến đổi mà `filter`/`map`/`reduce` nói rõ hơn — mùi nhẹ: chỉ FAIL khi pipeline ngắn hơn và rõ ý định hơn thật, loop có early-exit hay nhiều bước đan nhau có thể PASS. Đề xuất Replace Loop with Pipeline. Không có loop thì N/A.

## Nhóm 7 · Kế thừa & class lạ

- [ ] **SM21 Refused Bequest** Test con thừa kế thứ không cần. FAIL nếu subclass bỏ qua/phá phần lớn surface của cha — hợp đồng is-a không đứng. Đề xuất Push Down Method/Field, Replace Subclass/Superclass with Delegate (has-a thay is-a). Trùng F6a; đếm 1 lần. Không có kế thừa thì N/A.
- [ ] **SM22 Alternative Classes with Different Interfaces** Test hai class cùng việc khác tên. FAIL nếu hai class/component làm cùng một việc nhưng method/prop tên khác nhau → không đổi chỗ được cho nhau. Đề xuất Change Function Declaration thống nhất tên, Move Function, Extract Superclass. Không có thì N/A.
- [ ] **SM23 Data Class** Test class chỉ data không hành vi. FAIL nếu record/object chỉ field mà logic thao tác nó nằm ở module khác — hành vi bị Feature Envy lôi đi. Đề xuất Move Function về module sở hữu record (JS: move vào module chứa type, không cần method), Encapsulate Record, Remove Setting Method. Không có thì N/A.
- [ ] **SM24 Comments** Test comment giải thích code. FAIL nếu comment nói đoạn code *làm gì* — trích được thành tên hàm/biến thì trích, xóa comment. Comment giữ lại chỉ khi chứa thứ code không nói được (ràng buộc ngoài, lý do tồn tại). Chi tiết xử lý theo `rules/comments.md`. Đề xuất Extract Function, Change Function Declaration. Không có comment trong phạm vi thì N/A.

---

## Khi nào chạy

| Việc | Cách dùng |
|---|---|
| Audit/đọc một màn, một module | Đi cả 24; mùi nào true mà không có câu trong report là audit thiếu |
| Trước khi refactor (`playbooks/refactor-ui.md`) | Chạy trên code sẽ đụng — mùi nào refactor không dọn được phải nói rõ vì sao |
| Review diff | Chỉ chấm mùi diff **tạo thêm**, không chấm mùi có sẵn; ghi `SM#` trong câu finding |
| Viết finding | Đặt tên mùi trong câu `smell → refactor → vì sao` để người đọc map thuốc |

## Giới hạn

- Mùi là **gợi ý, không phải luật** — cùng một mùi người này thấy nặng người kia thấy nhẹ; severity tối đa minor, không là blocker.
- Không chấm correctness/security/perf/test — đó là `REVIEW_CHECKLIST.md`.
- Linter đã bắt được thì skip, không lặp finding.
- Một project rule cho phép shape đó thì rule thắng.
- Nhiều mùi đi cặp đối lập (SM10↔SM11, SM13↔SM14, SM16↔SM17): chữa một mùi quá tay sinh mùi ngược — đề xuất ở mức cân bằng, không tuyệt đối.
