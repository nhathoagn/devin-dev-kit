# test-checklist.md

Checklist theo *Unit Testing: Principles, Practices, and Patterns* (Vladimir Khorikov) và *The Art of Unit Testing* (Roy Osherove). Mỗi mục trả **PASS** / **FAIL** / **N/A**. 17 items, U1–U17.

Bốn checklist trước chấm **production code**; file này chấm **test code**. `REVIEW_CHECKLIST.md` nhóm T (T1–T10) chấm test *có tồn tại không* và các lỗi cơ bản (deterministic, skip, xanh-giả) — item nào trùng ghi ngay ở mục đó, đếm một lần.

Luật trung tâm của sách: **chỉ kiểm chứng observable behavior, không kiểm chứng implementation detail**. Test pin vào implementation = false positive chờ xảy ra: refactor giữ nguyên hành vi mà test vẫn đỏ — và test đỏ-giả dạy team bỏ qua mọi test đỏ.

Finding viết theo cấu trúc `item → nguyên tắc → vì sao`:

> `U5 mock in-process`: `expect(pricingHelper.calculate).toHaveBeenCalled()` — collaborator trong cùng process là implementation detail; verify nó nghĩa là refactor sang `compute()` sẽ làm test đỏ dù behavior đúng.

---

## Nhóm 1 · Bốn trụ cột (ch.4)

- [ ] **U1 Resistance to refactoring** Test test có pin vào implementation không — **trụ cột then chốt, gần như nhị phân**. FAIL nếu test kiểm chứng thứ caller bên ngoài không quan sát được: private internals, thứ tự/cách gọi giữa các collaborator trong domain, spy lên helper in-process. Test chỉ được assert output, state quan sát được, và side effect ra ngoài hệ thống. Trùng T3 ở phần "chỉ assert mock được gọi"; U1 phạm rộng hơn — mọi impl-detail leak. Không có test mới/sửa thì N/A.
- [ ] **U2 Protection against regressions** Test test có chạy đủ code thật không. FAIL nếu test mới chỉ đi qua trivial path (getter, constant) hoặc mock tới mức không dòng code thật nào chạy — mock xong verify lên chính mock là test tự ăn. Trùng T9 ở phần "đỏ khi code hỏng". Không có test thì N/A.
- [ ] **U3 Fast feedback** Test test đụng thứ ngoài process. FAIL nếu unit test đụng DB thật, filesystem, network, đồng hồ thật, `sleep` — đó là integration test đội lốt unit, và test chậm làm cả suite mất giá trị fast feedback. Trùng T4 ở phần time/network; đếm 1 lần.
- [ ] **U4 Cấu trúc đọc được** Test AAA và một-behavior-một-test. FAIL nếu test có `if`/loop (hai kịch bản trộn một), Arrange rối tới mức không thấy SUT, hoặc tên không kể được behavior (`test1`, `it works`). Đề xuất Arrange–Act–Assert rõ ràng, tên là câu miêu tả fact: `delivery_with_past_date_is_invalid`. Không có thì N/A.

## Nhóm 2 · Mock hygiene (ch.5, 9)

- [ ] **U5 Chỉ mock unmanaged dependency** Test mock đứng chỗ. FAIL nếu mock collaborator **in-process** (helper, calculator, domain object có logic) — trong process là implementation detail, mock nó là pin vào cấu trúc. Mock chỉ cho **unmanaged/out-of-process**: DB, filesystem, SMTP, message bus, time provider. Không có mock thì N/A.
- [ ] **U6 Không assert trên stub** Test verify lên thứ cung cấp input. FAIL nếu `toHaveBeenCalled` lên thứ chỉ trả data cho SUT (`repo.find`, `api.getUser`) — over-specification: đổi cách lấy data là test vỡ dù kết quả đúng. Assert chỉ lên **outgoing** interaction (send, publish, save, write). Trùng T3; đếm 1 lần.
- [ ] **U7 Verify ở rìa hệ thống** Test vị trí mock. FAIL nếu mock/verify đặt sâu trong domain — đúng chỗ là **boundary** nơi app nói với out-of-process (controller/handler gọi dependency), không phải ruột domain model. Không có mock thì N/A.

## Nhóm 3 · Kiểu test & anti-pattern (ch.6, 11)

- [ ] **U8 Ưu tiên output/state-based** Test kiểu kiểm chứng. FAIL nếu test toàn communication-based (verify calls) trong khi output hoặc state quan sát được — đổi sang `expect(result)`/`expect(sut.state)`. Communication-based chỉ cho unmanaged dependency (U5–U7). Gần U1 nhưng nhìn style; đếm 1 lần.
- [ ] **U9 Không test private method** Test đường vào private. FAIL nếu test đụng member private (`obj._m`, `obj['m']`, prototype hack) — logic đáng test mà private là abstraction còn thiếu. Đề xuất Extract thành module/class riêng có API riêng; không expose vì test, không test gián tiếp qua hack.
- [ ] **U10 Không test-only code trong prod** Test diff thêm API phục vụ test. FAIL nếu production code có param/flag/method chỉ test dùng (`isTest`, test-only constructor, widen visibility). Đề xuất factory/builder/fixture ở phía test — prod API chỉ tồn tại vì caller thật.
- [ ] **U11 Không tautology** Test expected tự tính lại. FAIL nếu test tái hiện thuật toán production để tính giá trị kỳ vọng (map/reduce y hệt logic test) — test luôn xanh bất kể bug vì nó kiểm chứng chính nó. Đề xuất hard-code expected values. Trùng T9 một phần; đếm 1 lần.
- [ ] **U12 Time & randomness tường minh** Test nguồn không kiểm soát. FAIL nếu business logic đọc `Date.now()`/`Math.random()` trực tiếp khi test cần kiểm soát giá trị — inject provider/fixed clock qua tham số. Trùng T4; đếm 1 lần.

## Nhóm 4 · Integration & DB (ch.8–10)

- [ ] **U13 Ranh giới unit/integration** Test test gọi tên đúng loại. FAIL nếu test tự xưng unit mà chạm shared state ngoài process — hoặc test DB chạy in-memory database (SQLite) thay DB thật: dialect khác nghĩa là test xanh mà prod đỏ. Đề xuất test DB chạy DB thật. Không có test đụng out-of-process thì N/A.
- [ ] **U14 Không mock repository** Test mock tầng data. FAIL nếu mock repository/ORM để test DB interaction — đây là unmanaged dependency, phải integration test chạy DB thật; mock repo chỉ che được lỗi SQL/mapping đến khi lên prod. Trùng U5 tại điểm repo là interface in-process — ghi rõ ngoại lệ này trong finding.
- [ ] **U15 Test data độc lập** Test isolation của fixture. FAIL nếu test DB dựa vào execution order, seed data ngoài test, hoặc fixture bẩn của test trước — mỗi test tự arrange data nó cần, chạy sequential không parallel. Trùng T4/T7; đếm 1 lần.
- [ ] **U16 Không test vì con số** Test test có assert gì thật không. FAIL nếu test thêm vào chỉ để đẩy coverage: snapshot rỗng, assert tồn tại (`toBeTruthy` lên mọi thứ), expect không gắn với behavior nào. Coverage là negative indicator — thấp nghĩa thiếu test, cao không nghĩa test tốt. Trùng T3/T9; đếm 1 lần.
- [ ] **U17 Đủ trạng thái theo số bản ghi** Test test của list/table có đi hết các mức dữ liệu không. FAIL nếu màn có list/table mà test chỉ chạy một mức — bắt buộc đủ: **0 record** (empty state), **1 record**, **ít record** (vài dòng), **nhiều record** (vượt vùng hiển thị, có scroll/phân trang). Mỗi mức một test riêng; một test duyệt nhiều mức bằng loop là U4 FAIL. Không có list/table thì N/A.

---

## Khi nào chạy

| Việc | Cách dùng |
|---|---|
| Diff thêm/sửa test | Đi cả 16; U1 là gate — test pin vào implementation thì các trụ cột khác không cứu được |
| Refactor đụng test (`playbooks/refactor-ui.md`) | Test vỡ vì behavior đổi là đúng; test vỡ vì nó pin vào implementation là U1 FAIL của test đó, ghi vào finding |
| Viết test mới | Chọn style output/state-based khi được; mock chỉ ở boundary cho unmanaged dep |
| Review suite cũ | U1, U5, U6, U11 bắt phần lớn fragile tests |

## Giới hạn

- File này chấm **chất lượng test**, không chấm test có tồn tại hay đủ coverage — đó là `REVIEW_CHECKLIST.md` T1/T9.
- Không chấm correctness của production code — test PASS hết mà prod sai là chuyện nhóm C.
- Severity tối đa minor; linter đã bắt được thì skip; project rule cho phép thì rule thắng.
- Nguyên tắc process (mutation testing, coverage target) không chấm được bằng diff — không có item tương ứng. Test trước code sau (TDD) là workflow của người viết; khi người dùng yêu cầu test-first, chạy loop `tdd` theo `references/external.md` — diff không chứng minh được test có được viết trước không.
