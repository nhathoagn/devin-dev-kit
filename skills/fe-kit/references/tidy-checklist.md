# tidy-checklist.md

Checklist theo *Tidy First?* (Kent Beck) — 15 tidying (T1–T15) + 6 nguyên tắc managing (T16–T21). Mỗi mục trả **PASS** / **FAIL** / **N/A**.

Tidying là tập con nhỏ nhất của refactor: động tác vài phút, không đổi hành vi, làm thay đổi sắp tới dễ hơn. Ba checklist SM/F/O chấm **trạng thái code**; file này chấm thêm **cách thực hiện** — dọn đúng chỗ, đúng lúc, và giữ commit tidy tách khỏi commit behavior.

Finding viết theo cấu trúc `tidying → động tác → vì sao`:

> `T16 Separate Tidying`: PR này vừa rename `calc` → `orderTotal` vừa đổi công thức giảm giá — hai thay đổi cần hai kiểu review, tách commit.

---

## Nhóm 1 · Làm code đọc được

- [ ] **T1 Guard Clauses** Test nhánh đặc biệt. FAIL nếu trường hợp đặc biệt chôn trong else sâu thay vì return sớm — thân chính phải là đường bình thường, nằm phẳng. Tidying: đưa guard lên đầu, `return`/`continue` sớm. Trùng F4a; đếm 1 lần. Không có nested conditional thì N/A.
- [ ] **T2 Dead Code** Test code không ai gọi. FAIL nếu hàm/branch/export trong phạm vi không có caller và không phải entry point — "phòng khi" là chi phí đọc mỗi ngày, git giữ lại nếu cần. Tidying: xóa. Trùng SM17; đếm 1 lần. Không có thì PASS.
- [ ] **T3 Normalize Symmetries** Test một việc nhiều kiểu viết. FAIL nếu cùng một thao tác viết 2+ cách khác nhau trong phạm vi (`a.price`, `b['price']`, `getPrice(c)`) — reader phải học lại pattern mỗi chỗ. Tidying: chọn một kiểu, đổi phần còn lại cho giống. Không có thì PASS.
- [ ] **T4 Reading Order** Test thứ tự phần tử trong file. FAIL nếu người đọc buộc nhảy lên xuống để hiểu một flow — helper đặt trước hàm chính gọi nó, hằng số dùng ở dòng 10 khai báo dòng 200. Tidying: xếp theo thứ tự reader cần gặp. Không đổi file layout thì N/A.
- [ ] **T5 Cohesion Order** Test phần tử đổi cùng nhau có ở cạnh nhau. FAIL nếu hai hàm/field luôn sửa cùng lúc nằm cách xa nhau trong file — thay đổi sau phải săn. Tidying: kéo về gần nhau; đây cũng là bước chuẩn bị cho Extract. Trùng tinh thần SM5; đếm 1 lần.
- [ ] **T6 Chunk Statements** Test cấu trúc đoạn trong hàm. FAIL nếu hàm dài một khối không ngắt — đoạn văn nào cũng dính nhau. Tidying rẻ nhất: dòng trắng ngăn các "đoạn văn" khác việc; thường là bước đầu cho T11. Không có hàm nhiều đoạn thì N/A.

## Nhóm 2 · Giải thích ý định

- [ ] **T7 Declaration & Initialization Together** Test biến khai báo xa chỗ dùng. FAIL nếu `let x` ở đầu hàm rồi hàng chục dòng sau mới gán — reader phải nhớ chỗ trống. Tidying: khai báo ngay chỗ khởi tạo; trở thành `const` luôn tốt hơn. Không có thì N/A.
- [ ] **T8 Explaining Variables** Test biểu thức đọc khó. FAIL nếu điều kiện/biểu thức cần giải thích bằng lời mới hiểu — tên biến trích ra là tài liệu sống. Tidying: Extract Variable đặt tên theo ý định. Ngược với F1b: biến tạm chỉ tốt khi tên nó **thêm** ý nghĩa; không thêm thì F1b inline ngược. Không có thì N/A.
- [ ] **T9 Explaining Constants** Test literal có nghĩa. FAIL nếu literal cứng mang nghĩa nghiệp vụ (`status === 2`) — reader phải tra mapping. Tidying: named constant. Trùng F3b; đếm 1 lần. Không có thì N/A.
- [ ] **T10 Explicit Parameters** Test dependency ngầm. FAIL nếu hàm đọc state ngoài signature (global, field của object khác, module singleton) — dependency ẩn không ai thấy. Tidying: truyền vào thành tham số tường minh; làm coupling lộ ra trước khi dọn nó. Trùng tinh thần SM6/O6; đếm 1 lần.

## Nhóm 3 · Cấu trúc nhỏ

- [ ] **T11 Extract Helper** Test đoạn code có mục đích riêng trong hàm. FAIL nếu một cụm statement làm một việc riêng rõ mà nằm chung thân hàm. Tidying: extract thành hàm con, tên theo *mục đích* không phải cơ chế. Trùng SM3/F1a; đếm 1 lần.
- [ ] **T12 One Pile** Test phân mảnh quá mức — tidying ngược chiều. FAIL nếu code bị chia nhỏ tới mức không đọc được một flow (chuỗi hàm 2 dòng gọi lẫn nhau, nhảy 10 chỗ mới hiểu một việc). Tidying: **gom về một đống** để thấy toàn cảnh, rồi mới tách lại đúng chỗ — đường đến cấu trúc tốt đôi khi đi qua "vỡ hơn trước". Đây là nước đi riêng của Beck, không có trong SM/F/O. Không có over-fragmentation thì N/A.
- [ ] **T13 New Interface, Old Implementation** Test đổi API. FAIL nếu signature đổi bằng cách sửa tại chỗ rồi săn mọi caller trong một commit. Tidying an toàn hơn: viết interface mới delegate sang impl cũ → chuyển dần caller → đổi impl sau. Đây là migration mechanics của Fowler nâng thành động tác độc lập. Không đổi API thì N/A.

## Nhóm 4 · Comments

- [ ] **T14 Explaining Comments** Test insight bị bỏ lại. FAIL nếu reviewer phải đào code khó để hiểu một điều mà tác giả diff *đã biết* — why, ràng buộc, bất ngờ. Tidying: ghi insight đó thành comment ngay khi đang hiểu, để người sau khỏi đào lại. Trùng keep-list của `rules/comments.md` và phần dương của O12; đếm 1 lần.
- [ ] **T15 Delete Redundant Comments** Test comment lặp code. FAIL nếu comment diễn lại đúng thứ code nói ở cùng level (`i++ // tăng i`). Tidying: xóa ngay — không thêm thông tin mà vẫn tốn chi phí đọc. Trùng SM24/O12; đếm 1 lần.

## Nhóm 5 · Managing — dọn đúng lúc, đúng cách

- [ ] **T16 Separate Tidying** Test diff trộn hai loại thay đổi. FAIL nếu một commit/PR vừa tidy (rename, move, format, extract giữ-nguyên-hành-vi) vừa đổi behavior — tidy chỉ cần skim "giữ nguyên?", behavior cần đọc sâu; trộn làm cả hai review thiếu sót và giấu bug trong format. Đề xuất tách: commit tidy trước, commit behavior sau. Trùng S2 trong `REVIEW_CHECKLIST.md`; đếm 1 lần. Không có diff thì N/A.
- [ ] **T17 Chaining** Test dây chuyền dọn không đáy. FAIL nếu một tidying kéo tidying tiếp theo mà phạm vi phình ra vô hạn — hoặc timebox nó, hoặc đó là dấu hiệu cần refactor thật chứ không phải tidy. Dây chuyền tốt khi mỗi mắt làm việc sau dễ hơn. Process item: chỉ đánh giá được trong cách tác giả trình bày work.
- [ ] **T18 Batching** Test kích thước mẻ dọn. FAIL nếu batch tidy lớn tới mức review không nổi (format cả file lẫn vài dòng thật) hoặc nhỏ tới mức chi phí PR lấn giá trị — điểm ngọt tùy chi phí review của repo. Trùng tinh thần S6; đếm 1 lần.
- [ ] **T19 Rhythm** Test thời điểm dọn. FAIL nếu tidy chen giữa lúc đang hiểu một bug dở — đổi context là mất tiền. Đúng: dọn ở nhịp nghỉ tự nhiên (sau test xanh, trước thay đổi tiếp). Process item, không thấy trong diff.
- [ ] **T20 Getting Untangled** Test sửa trên nền rối. FAIL nếu diff chèn logic mới vào đoạn code mà chính diff phải vật lộn mới đọc được — rẻ hơn là tidy trước (hoặc vứt bản viết, tidy rồi viết lại) thay vì sửa trong đống rối. Dấu hiệu: hunk phải thêm comment/format phụ mới "vừa chỗ để thở". Không có nền rối thì N/A.
- [ ] **T21 First Things** Test dọn đúng chỗ. FAIL nếu diff dọn code sắp xóa, chỗ lạnh không ai đi qua, hoặc tidy đắt hơn thay đổi nó phục vụ — giá trị tidying theo power law: dọn nơi thay đổi sẽ đến, không dọn đều khắp. Ngược lại cũng FAIL: bỏ qua tidy 5 phút làm thay đổi ngay sau đó dễ hẳn. Đây là câu trả lời của sách cho "tidy first?" — tùy, và item này chấm cái "tùy" đó.

---

## Khi nào chạy

| Việc | Cách dùng |
|---|---|
| Trước một behavior change ở code khó đọc | T21 quyết có tidy trước không → nếu có, chọn T1–T15 vừa đủ để thay đổi dễ, không hơn |
| Refactor (`playbooks/refactor-ui.md`) | T1–T15 là menu động tác nhỏ an toàn; T16–T21 quyết cách gom commit |
| Review diff | T16/T18/T20 chấm trực tiếp trên diff; T1–T15 chỉ chấm tidy diff tạo thêm |
| Viết finding | `T# → động tác → vì sao` |

## Giới hạn

- Tidying **không đổi hành vi** — item nào phát hiện behavior sai thì đó là correctness, qua `REVIEW_CHECKLIST.md` nhóm C.
- T17–T19 là process: chỉ FAIL khi có bằng chứng trong diff hoặc cách work được trình bày; không có bằng chứng thì N/A, không suy diễn.
- Severity tối đa minor — tidy không là blocker; một project rule cho phép shape đó thì rule thắng.
- Không chấm "nên tidy thêm" cho chỗ diff không đụng — T21 phạm cả hai chiều: dọn sai chỗ lẫn bỏ quên chỗ đúng, nhưng chỉ trong phạm vi thay đổi sắp tới.
