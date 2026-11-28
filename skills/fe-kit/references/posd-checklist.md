# posd-checklist.md

Checklist theo *A Philosophy of Software Design* (John Ousterhout) — các red flag và nguyên tắc chống complexity mà hai file Fowler không gọi tên. Mỗi mục trả **PASS** / **FAIL** / **N/A**. 16 items, O1–O16, theo 5 nhóm.

Thước đo của sách là **độ sâu module**: interface tốt đơn giản hơn nhiều so với implementation nó giấu. Fowler hỏi "code này khó sửa ở đâu"; file này hỏi thêm "module này giấu được bao nhiêu cho cái giá interface của nó". Item nào trùng `smells-checklist.md` hoặc `fowler-checklist.md` ghi ngay ở mục đó — đếm một lần, không nhân đôi finding.

Finding viết theo cấu trúc `red flag → nguyên tắc → vì sao`:

> `O8 Pull Complexity Down`: `search(q, opts)` bắt caller tự normalize chuỗi trước khi gọi — module tự normalize được, interface nên để `search(q)`.

---

## Nhóm 1 · Độ sâu module (ch.4)

- [ ] **O1 Shallow Module** Test tỷ lệ interface/implementation. FAIL nếu interface (signature + thứ caller phải biết) phức tạp gần bằng thứ module giấu — getter/setter trần, wrapper bọc một call, class chỉ để đặt tên một hàm. Interface đắt mà implementation mỏng = trả giá không được lợi. Đề xuất gộp/Inline, hoặc làm implementation đáng với interface. Trùng SM16/SM23; đếm 1 lần.
- [ ] **O2 Overexposure** Test API lộ thứ hiếm dùng. FAIL nếu interface buộc caller học feature ít khi cần — param chỉ phục vụ edge case, config bắt buộc cho common case. Đề xuất expose defaults: trường hợp thường chạy đúng không cần config, trường hợp hiếm là API riêng. Trùng SM4; đếm 1 lần. Không có interface mới/đổi thì N/A.

## Nhóm 2 · Tri thức rò rỉ giữa module (ch.5, 7)

- [ ] **O3 Information Leakage** Test một quyết định thiết kế cần ở 2+ module. FAIL nếu hiểu hoặc sửa một tri thức (format data, policy, thứ tự bước) buộc đọc/sửa nhiều file — module nào cũng biết chuyện nhau. Đề xuất gom tri thức về một module duy nhất. Trùng SM11; đếm 1 lần. Không có thì N/A.
- [ ] **O4 Temporal Decomposition** Test module tách theo thứ tự chạy. FAIL nếu cấu trúc mirror đúng flow execution (đọc → parse → xử lý → ghi) mà các phần chia sẻ cùng một tri thức (format, schema) — tri thức đó rò qua mọi interface thay vì nằm trong một module deep. Đề xuất tổ chức theo tri thức mỗi module giấu, không theo thứ tự thao tác. Trùng SM10/SM11; đếm 1 lần.
- [ ] **O5 Pass-Through Method** Test method chỉ chuyển tiếp. FAIL nếu method chỉ forward args sang method khác signature gần giống — interface tăng mà chức năng không tăng. Ngoại lệ theo sách: dispatcher chọn giữa nhiều implementation thì hợp lệ. Đề xuất Remove Middle Man. Trùng SM14/F2d; đếm 1 lần.
- [ ] **O6 Pass-Through Variable** Test biến đi xuyên tầng. FAIL nếu một biến được truyền qua nhiều lớp chỉ để đến chỗ dùng cuối — mỗi tầng phải biết nó tồn tại dù không dùng. Đề xuất mang theo object state hoặc context có tên rõ và phạm vi hẹp; cảnh báo theo sách: context dễ thành grab-bag, chỉ chứa thứ đi cùng nhau. Trùng SM13; đếm 1 lần.

## Nhóm 3 · Tổng quát & vị trí complexity (ch.6, 8)

- [ ] **O7 Special-General Mixture** Test cơ chế general chứa code special. FAIL nếu interface general-purpose mang param/branch phục vụ một trường hợp cụ thể hiện tại — phần special đổi theo feature, phần general nên đứng yên. Đề xuất tách phần special lên layer trên. Trùng SM17/SM10; đếm 1 lần.
- [ ] **O8 Pull Complexity Down** Test ai chịu khổ. FAIL nếu interface đẩy lên caller việc module tự hấp thụ được — caller phải chuẩn bị, normalize, validate, hoặc quyết định thứ module tự tính được (config bắt buộc thay cho mặc định hợp lý). Ngoại lệ theo sách: tri thức chỉ caller có — quyết định nghiệp vụ khi lỗi — thì đẩy lên đúng. Đề xuất tính trong module, default hợp lý thay config. Không có interface mới/đổi thì N/A.

## Nhóm 4 · Cohesion & lỗi (ch.9, 10)

- [ ] **O9 Conjoined Methods** Test hai method buộc hiểu cùng nhau. FAIL nếu hiểu method A bắt buộc hiểu method B, hoặc caller phải gọi đúng thứ tự mà không contract nào nói — tri thức ẩn nằm giữa cặp. Đề xuất gộp một method bao trọn flow. Trùng SM15; đếm 1 lần.
- [ ] **O10 Define Errors Out of Existence** Test error path mới. FAIL nếu API thêm throw/error-code cho trường hợp định nghĩa lại được thành hợp lệ — xóa thứ không tồn tại, slice quá biên, lookup trả empty. Mỗi error case là một chỗ caller phải xử lý. Đề xuất định nghĩa lỗi thành no-op/clamp/empty result, aggregate exception ở boundary, hoặc crash sớm cho unrecoverable — giảm số *chỗ* xử lý lỗi. Không có error path mới thì N/A.
- [ ] **O11 Repetition** Test cụm statement lặp. FAIL nếu cùng đoạn code xuất hiện lại — mỗi bản là một dependency phải nhớ sửa. Đề xuất Extract Function. Trùng SM2/D2; đếm 1 lần. Không có thì PASS.

## Nhóm 5 · Comment, tên, rõ ràng (ch.12–18)

- [ ] **O12 Comment Repeats Code** Test comment cùng level với code. FAIL nếu comment diễn lại *what* mà code đã nói (`i++ // tăng i`). Comment chỉ có giá trị ở level khác: why, ràng buộc, contract — đủ để dùng module mà không đọc body. Trùng SM24 và `rules/comments.md`; đếm 1 lần.
- [ ] **O13 Implementation Contaminates Interface** Test interface lộ ruột. FAIL nếu signature hoặc interface comment lộ chi tiết bên trong caller không cần — tên field nội bộ, format storage, thuật toán. Đề xuất interface nói what + contract; chi tiết implementation nằm trong body.
- [ ] **O14 Vague Name / Hard to Pick Name** Test tên nói được gì. FAIL nếu tên mơ hồ (`data`, `info`, `result`, `handle`) hoặc không đặt được tên — không đặt tên được thường là thiết kế mờ, extract trước rồi mới đặt. Đề xuất Rename; scope rộng đòi tên chính xác hơn scope hẹp. Trùng SM1/F5d; đếm 1 lần.
- [ ] **O15 Hard to Describe** Test "mô tả một câu". FAIL nếu cần một đoạn dài để nói module/hàm làm gì — đang gộp nhiều việc hoặc shallow. Đề xuất tách theo việc mô tả được bằng một câu. Trùng tinh thần SM5/F2b; đếm 1 lần.
- [ ] **O16 Nonobvious Code** Test đọc hiểu lần đầu. FAIL nếu phải trace nhiều chỗ mới hiểu hành vi — event chain khó theo, container mất type, khai báo khác nghĩa dùng. Đây là ô che phủ: chỗ nào gọi tên được bằng item khác thì ghi item đó, O16 cho phần "đọc không hiểu ngay" không đặt tên được.

---

## Khi nào chạy

| Việc | Cách dùng |
|---|---|
| New UI (`playbooks/new-ui.md`) | O1, O2, O7, O8, O10, O13 trước khi viết implementation — interface thiết kế ở đây, không phát hiện trong diff. Mỗi interface một hàng trong bảng Interface Depth của output template |
| Fix bug (`playbooks/fix-bug.md`) | Chỉ khi fix đổi interface hoặc thêm error path: chấm O7, O8, O10 trên phần widen — error mới có định nghĩa away được không, việc có bị đẩy lên caller không |
| Refactor/cleanup (`playbooks/refactor-ui.md`, `cleanup.md`) | Sau `smells-checklist.md` + `fowler-checklist.md`: file này hỏi các câu hai kia không hỏi — module có deep không, complexity bị đẩy lên caller không, error case có định nghĩa được không. Ghi bảng Interface Depth cho interface refactor tạo hoặc đổi |
| Review diff | 14 items O1–O10, O13–O16 nằm trong `REVIEW_CHECKLIST.md` và được lens `structure` (O1, O3–O6, O9, O15, O16), `contract` (O2, O7, O8, O10, O13), `naming` (O14) chấm — reviewer không cần đọc file này. O11 nằm ở D2 cho helper viết lại và ở F4 cho cụm statement lặp; O12 ở N4. Chỉ chấm red flag diff **tạo thêm**, không chấm cái có sẵn |
| Viết finding | Đặt tên red flag trong câu `red flag → nguyên tắc → vì sao` |

## Giới hạn

- Red flag chấm trong refactor/cleanup/new-ui/fix-bug là **gợi ý, không phải luật** — severity tối đa minor, không là blocker. Cap này không áp cho review diff: trong `REVIEW_CHECKLIST.md` một item O trên interface mới chấm theo thang chung, vì caller nhân lên sau merge thì không gỡ được nữa.
- Không chấm correctness/security/perf/test — đó là `REVIEW_CHECKLIST.md`.
- Linter đã bắt được thì skip, không lặp finding.
- Một project rule cho phép shape đó thì rule thắng.
- Các item O1–O16 chấm trạng thái tĩnh của code; nguyên tắc process của sách (design it twice, write comments first, strategic vs tactical) không chấm được bằng diff — không có item tương ứng.
