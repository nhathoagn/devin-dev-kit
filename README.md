# fe-kit

![version](https://img.shields.io/badge/version-1.17.1-blue)
![hosts](https://img.shields.io/badge/hosts-Claude%20Code%20%7C%20omp-6e56cf)
![license](https://img.shields.io/badge/license-MIT-green)

**Plugin frontend bắt agent ghi rõ ai sở hữu code và dùng lại hay viết mới — trước khi được sửa một dòng.**

Agent viết UI rất nhanh. Vấn đề không phải tốc độ, mà là những gì nó để lại: business logic
nằm trong page, cùng một block code chép ở ba nơi, một giá trị đã có holder lại được thêm
`useState` thứ hai. Diff đọc vẫn sạch. Nợ chỉ lộ ra sau vài tháng.

fe-kit chèn đúng hai câu hỏi vào chỗ đó. Agent không trả lời được thì không sửa file.
Một plugin, chạy trên Claude Code và omp.

---

## 20 giây để thấy nó làm gì

Người dùng:

```text
Sửa màn chi tiết đơn hàng: đổi trạng thái giờ hiện sai múi giờ.
```

Agent định sửa file. Gate chặn:

```text
⛔ blocked — Fill Runtime owner and a Reuse Decision (reuse, extend, feature-local,
shared, or n/a with a reason) from skill fe-kit before editing this file.
```

Agent phải trả lời trước, bằng chữ, trong reply:

```text
Runtime owner: OrderDetail — page chỉ compose, form runtime ở OrderForm.
Decision: reuse — đã có formatDateTime trong lib/format; không viết lại.
Trigger: đơn tạo lúc 23:30 hiện ngày hôm sau.
Expected: hiện đúng ngày tạo theo giờ máy.
Actual: lệch một ngày với đơn tạo sau 17:00 UTC.
```

Sửa lần này đi qua. Agent không "nghĩ thầm" được — nhãn phải nằm trong câu trả lời.
Lý do: một phiên trước đó agent ghi plan trong thinking, gate không đọc thấy, và nó chặn
đúng 8 lần liên tiếp vì lý do chính đáng.

---

## Nó chặn ba thứ

**Kiến trúc không có chủ.** Mỗi lần sửa file nguồn phải ghi `Runtime owner:` — component,
hook, hay module nào thật sự giữ state và business rule. Không có nhãn, không có edit.
Playbook `references/ownership.md` còn đòi phân biệt first-fix owner và canonical owner,
và nêu tên các owner cạnh tranh là sai.

**Code viết lần thứ hai.** `Decision:` phải là `reuse`, `extend`, `feature-local`,
hoặc `shared`. `shared` chỉ hợp lệ khi có từ hai consumer thật trở lên, nêu tên.
Bug fix còn bị hỏi: giá trị này đã có state hay prop nào giữ chưa?

**Tác giả tự chấm bài mình.** Người viết diff không được review diff đó. Claude Code có
agent `fe-kit:reviewer` read-only; omp dùng một context sạch chỉ nhận diff range và
playbook. Không đưa ghi chú của tác giả, không đưa kết luận.

---

## Bên trong có gì

| | |
|---|---|
| **Skill `fe-kit`** | Entry cho mọi việc FE không nhỏ. Chọn 1 trong 6 playbook: `new-ui`, `fix-bug`, `refactor-ui`, `perf-ui`, `review-ui`, `review-diff` |
| **Cổng edit** | Chặn `Write` / `Edit` / `MultiEdit` thiếu nhãn; kiểm conflict marker và `rules.sh` sau khi ghi |
| **Skill `ui-image-check`** | Một ảnh mockup vào, một báo cáo chênh lệch ra: item có / thiếu / lệch, mỗi item `file:line` |
| **Skill `ut-report`** | Một màn ra file `.xlsx` đúng template team: Hệ cũ ↔ Hệ mới, `OK` / `NG` / `NG -> OK` |
| **5 rule always-on** | `fe-implementation`, `reuse-duplication`, `modules`, `conflict-fix`, `review-diff` |

Đằng sau mỗi playbook là bộ reference ép agent trả lời theo đúng thứ tự:
Architecture Ownership → Reuse-first → Performance Check → Code Quality → Senior Audit
(reuse, kiến trúc, luồng vận hành, xử lý lỗi, tải, khả năng mở rộng) → Feature Isolation.

## Cài

**Claude Code**

```text
/plugin marketplace add nhathoagn/plugin-architecture
/plugin install fe-kit@fe-kit
```

`/plugin install` mở panel chọn scope — chưa chọn thì chưa cài.
Từ shell: `claude plugin marketplace add nhathoagn/plugin-architecture && claude plugin install fe-kit@fe-kit`

**omp**

```bash
omp plugin marketplace add nhathoagn/plugin-architecture
omp plugin install fe-kit@fe-kit
```

Cần `sh` và `python3` (Windows: Git Bash). Thiếu `python3` thì hook im lặng, plugin vẫn load.

## Dùng

```text
/fe-kit:fe-kit        # Claude Code
/skill:fe-kit         # omp
```

Rồi mô tả việc như bình thường. Hai việc hay dùng nhất:

- **Review trước commit** — diff đi qua reviewer mới, không phải bản agent vừa viết.
- **So ảnh với code** — đưa mockup, nhận danh sách lệch kèm `file:line`.

Trên omp, status line hiện verdict gần nhất: `✓ ok`, `✎ note`, `⛔ blocked`,
`⚡ rules` (prompt khớp intent). Một edit bị chặn còn hiện ở đó sau khi tool result cuộn qua.

## Nó không làm gì

- Không sinh code mẫu, không tạo scaffolding, không commit hộ.
- Không sửa code trong hai skill kiểm tra (`ui-image-check`, `ut-report`).
- Không đi qua issue tracker, không viết glossary hay ADR hộ bạn.
- Gate lỗi, quá 10 giây, hoặc không in gì thì **fail open** — không chặn oan vì lỗi hạ tầng.

## Đọc tiếp

| Tài liệu | Nội dung |
|---|---|
| [`skills/fe-kit/SKILL.md`](skills/fe-kit/SKILL.md) | Workflow, 6 field, hard rule |
| [`skills/fe-kit/playbooks/`](skills/fe-kit/playbooks/) | Từng loại việc một file |
| [`skills/fe-kit/references/`](skills/fe-kit/references/) | Ownership, reuse, performance, audit, checklist F1–F22 |
| [`rules/`](rules/) | 5 rule luôn bật, kèm ví dụ |
| [`CODEMAP.md`](CODEMAP.md) | Bản đồ kiến trúc plugin, ai gọi ai |
| [`skills/fe-kit/CHANGELOG.md`](skills/fe-kit/CHANGELOG.md) | Vì sao mỗi rule tồn tại — kèm sự cố thật |

## License

MIT
