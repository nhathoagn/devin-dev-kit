# fe-kit

![version](https://img.shields.io/badge/version-1.22.0-blue)
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
⛔ blocked — Blocked. Run this Bash command with each <...> replaced by a real value,
then retry the same edit: echo "Runtime owner: <the component or hook that runs
order-detail.tsx>" "Decision: <reuse|extend|feature-local|shared|n/a>" "Trigger: <steps>" ...
```

Agent chạy lệnh đó với giá trị thật:

```bash
echo "Runtime owner: OrderForm" "Decision: reuse"   "Trigger: đơn tạo lúc 23:30 hiện ngày hôm sau"   "Expected: hiện đúng ngày tạo theo giờ máy"   "Actual: lệch một ngày với đơn tạo sau 17:00 UTC"
```

Gate đọc nhãn từ chính lệnh Bash đó và lưu theo session và request. Sửa lần này đi qua.
Gate không đọc nhãn trong reply text hay thinking, vì hook có thể đọc transcript trước khi host ghi xong.
Nhãn người dùng gõ trong yêu cầu vẫn được tính. Payload không có session id thì nhãn trong reply text vẫn được tính.

---

## Nó chặn bốn thứ

**Kiến trúc không có chủ.** Mỗi lần sửa file nguồn phải ghi `Runtime owner:` — component,
hook, hay module nào thật sự giữ state và business rule. Không có nhãn, không có edit.

**Code viết lần thứ hai.** `Decision:` phải là `reuse`, `extend`, `feature-local`,
hoặc `shared`. `shared` chỉ hợp lệ khi có từ hai consumer thật trở lên, nêu tên.
Bug fix còn bị hỏi: giá trị này đã có state hay prop nào giữ chưa?

**Tác giả tự chấm bài mình.** Người viết diff không được review diff đó. Claude Code có
agent `fe-kit:reviewer` read-only; omp dùng một context sạch chỉ nhận diff range và playbook.

**Người đọc không debug được.** Trước `git commit`, agent phải viết `.fe-kit/handoff.md`:
Logic, Implementation (từng file và hàm giữ bước nào), Decisions, Debug without AI (lệnh
reproduce, file:line để xem, lỗi nghĩa là gì, cách xác nhận fix, rollback), Risks, Q&A.
Agent hỏi bạn 3–5 câu về state holder, nhánh dễ sót và check chứng minh fix; câu trả lời
được ghi lại. Bạn chạy lệnh approve trong `skills/fe-kit/references/handoff.md`; commit bị
chặn đến lúc đó, và sửa file sau khi approve thì phải approve lại. Repo muốn tắt:
`handoff: "off"` trong `.fe-kit/config.yaml`.

---

## Sáu field phải điền trước khi code

Skill `fe-kit` đi theo đúng thứ tự này. Mỗi playbook nói field nào bắt buộc.

| # | Field | Ghi gì |
|---|---|---|
| 1 | Architecture Ownership | Runtime owner, first-fix owner, canonical owner, các owner cạnh tranh là sai, hướng dọn |
| 2 | Reuse-first | Responsibility, exemplar và lý do khớp, quyết định `reuse` / `extend` / `feature-local` / `shared`, khoảng trống, vì sao chọn shape đó |
| 3 | Performance | Waterfall, bundle, data fetching, re-render, loading / error / empty, rủi ro còn lại. Kiểm đúng thứ tự này |
| 4 | Code Quality | Bảng sweep từ Names tới Design and behavior. Dòng `clean` mà không có search thì chưa xong |
| 5 | Senior Audit | Sáu lăng kính: reuse, kiến trúc, luồng vận hành, xử lý lỗi, tải, khả năng mở rộng. Mỗi finding có `file:line`, mức `high` / `medium` / `low`, và cái mất nếu để nguyên |
| 6 | Feature Isolation | Hành vi mới trên màn đã có: chỗ đặt, file mới, một call ở file cũ |

## Review diff

Người viết diff không được chấm diff đó.

| Host | Ai review |
|---|---|
| Claude Code | Agent `fe-kit:reviewer`, tool `Read` / `Grep` / `Glob` / `Bash`, không sửa, không commit, không spawn reviewer khác |
| omp | Một context mới, nhiệm vụ duy nhất là diff range + `skill://fe-kit/playbooks/review-diff.md` |

Không đưa ghi chú của tác giả. Reviewer thiếu playbook path trong task thì dừng, không tự bịa checklist.
Nó đi hết `references/REVIEW_CHECKLIST.md` rồi F1–F22 trong `references/review-checks.md`, và
tìm file spec của task trước khi chấm scope.

Report theo `references/review-output.md`: kết luận đứng đầu (một hoặc hai câu, có đưa lên được không),
sau đó mỗi finding một đoạn — tên đúng trong code, `file:dòng` đếm thật, và sửa thế nào.
Không ghi PASS / FAIL / blocker / major / minor, không kể file đã mở mà không có việc.

---

## So một ảnh với code

Skill `ui-image-check`. Đầu vào: một ảnh (`.svg`, `.png`, `.jpg`, hoặc dán trong chat),
tuỳ chọn mã màn. Nhiều hơn một màn khớp tiêu đề → hỏi, không đoán.

Ra báo cáo chênh lệch: từng item trong ảnh, có hay thiếu trong code, chữ / thứ tự / trạng thái /
kích thước có khớp không, kèm `file:line`. Rồi đối chiếu runtime bằng ảnh chụp màn đang chạy.
Skill này **không sửa code**.

## Báo cáo UT

Skill `ut-report`. Đầu vào: mã màn `{SID}`, link MR (Branch), link Redmine.
Đầu ra: một file `.xlsx` đúng template team, một sheet cho màn, sheet riêng cho batch con.

| Cột | Nội dung |
|---|---|
| `#`, `Nhóm` | Số và tên nhóm, gộp ô |
| `Trường hợp` | `{nhóm}.{số}` + điều kiện / thao tác, script tự thêm mã |
| `Hệ cũ`, `Hệ mới` | Hành vi thật của từng hệ. Màn không có hệ cũ: `-` và hành vi theo spec |
| `Kết quả` | `OK` / `NG` / `NA` / `NT` / `NG -> OK` |
| `Note/Lý do` | Lý do khác hệ cũ, lý do `NA`/`NG`, link CR, nguồn `file:line` |

Mười nhóm theo thứ tự: Layout (case đầu là `Theo figma`) → Quyền truy cập → Mở màn →
nhóm riêng của màn → Validation → Nghiệp vụ theo từng nút → cập nhật đồng thời →
Xử lý Database → Message / Dialog → CR.

Luật cứng: mọi case phải chạy thật trên UI, không kết luận theo code; đọc code thôi thì `NT`
kèm `Theo code (chưa chạy)`. Sinh file bằng `skills/ut-report/scripts/build_report.py`
(cần `pyyaml`, `openpyxl`). Tính năng mới không có hệ cũ: xem §0.5 trong `SKILL.md`.

## Độ sâu refactor

Skill `refactor-depth-options`. Trigger khi được bảo "improve", "refactor", "tối ưu",
"sửa cho gọn" mà không nói sâu cỡ nào. Trước khi sửa, skill bắt liệt kê các mức khả
thi — giữ shape (bỏ nesting/đổi tên) → đổi pattern (bảng lookup, `find` + `??`, rule
list) → restructure (kiểu mới, đổi signature) — kèm trade-off một dòng mỗi mức,
recommend một mức, rồi mới sửa hoặc hỏi khi các mức khác nhau về cách maintain.
Request đã chỉ rõ depth ("just flatten", "giữ cấu trúc") thì không bắt liệt kê.

---

## Sáu rule luôn bật

| Rule | Chặn cái gì |
|---|---|
| `fe-implementation.md` | Định nghĩa wording/style theo hành vi; thứ tự search trước khi viết hàm mới |
| `reuse-duplication.md` | Cùng statements viết hai lần; bug fix thêm holder thứ hai cho giá trị đã có |
| `modules.md` | Hai job trong một file; folder theo loại file thay vì theo feature |
| `comments.md` | Comment lặp code, banner, giải thích workaround, suppression che lỗi correctness/safety; ép encode ràng buộc bằng type/check/test/lint |
| `conflict-fix.md` | Resolve conflict bằng hai block dán cạnh nhau, hoặc mất một phía |
| `review-diff.md` | Tác giả chấm diff của chính mình |

## Hai host khác nhau ở đâu

| Khả năng | Claude Code | omp |
|---|---|---|
| Rule theo prompt | Hook `UserPromptSubmit` inject | Rule always-on; badge `⚡ rules` báo prompt khớp |
| Chặn edit | Hook `PreToolUse` | `extensions/fe-gate.ts` trên `tool_call` |
| Kiểm sau khi ghi | Hook `PostToolUse`, exit 2 | Cùng extension, lỗi nằm trong tool result |
| Sau compact | `SessionStart` + `PreCompact` nạp lại rule | Không cần, rule vẫn bật |
| Verdict hiển thị | Không | Status line: `✓ ok`, `✎ note`, `⛔ blocked`, `⚡ rules` |

Cả hai dùng chung `scripts/fe-gate.sh` → `scripts/fe-gate.py`. Một chỗ sửa, hai host cùng đổi.

---

## Luật riêng của dự án

fe-kit giữ luật chung cho mọi dự án React. Luật riêng của một dự án nằm trong repo của dự án đó.
`scripts/project_config.py` nhận danh sách file thay đổi và in ra file luật nào phải đọc.

File `.fe-kit/config.yaml` **không bắt buộc**. Chỉ viết khi cách tìm mặc định không đủ.

| Dự án | Cần làm | fe-kit đọc |
|---|---|---|
| Không có luật FE riêng | Không làm gì | Chỉ luật của fe-kit |
| Luật ở `AGENTS.md`, `CLAUDE.md`, thư mục `rules/` gần code, hoặc `REVIEW_CHECKLIST.md` ở root | Không làm gì | Tự tìm: root, rồi từng thư mục cha của file thay đổi |
| Cần map luật theo đường dẫn, thư mục spec riêng, lệnh cổng, file loại trừ, preset | Viết `.fe-kit/config.yaml` | Đúng file đã khai |

Config tối thiểu:

```yaml
rules:
  - glob: "src/**"
    read: [docs/frontend-rules.md]
gate: ["pnpm typecheck", "pnpm lint"]
```

Config đầy đủ:

```yaml
version: 1
presets: [legacy-rewrite]          # hoặc ./tools/fe-preset (thư mục trong repo)
always_read: [web/rules/CARD.md]
rules:                             # mọi glob khớp đều cộng file
  - glob: "web/src/{pages,routes}/**"
    read: [web/rules/forms.md, web/rules/layout.md]
spec_dirs: [works/design]          # mặc định: docs specs .scratch
gate: ["npm --prefix web run typecheck"]
exclude: ["web/src/routeTree.gen.ts", "**/package-lock.json"]
legacy:                            # preset legacy-rewrite đọc
  source: dev/
  cr: "works/screens/{SID}.yaml"
```

Thử: `python3 scripts/project_config.py --root <repo> --files src/a.tsx` (hoặc `--diff BASE..HEAD`, `--staged`).

YAML được đọc bằng `scripts/yaml_subset.py`, chỉ thư viện chuẩn: mapping, list, list trên một dòng `[a, b]`,
chuỗi có nháy, `#` comment. Giá trị bắt đầu bằng `*`, `&`, `{`, `|`, `>` phải đặt trong nháy, như YAML thật:
glob `**/x` viết là `"**/x"`. Cú pháp ngoài tập con này báo lỗi kèm số dòng, exit 2.

Preset là thư mục có `design.md` (đọc trước khi viết code) và `review.md` (đọc khi review).
Có sẵn `presets/legacy-rewrite/` cho dự án viết lại hệ cũ: giống hệ cũ và không có CR thì không phải lỗi.

Sau review, `scripts/review_check.py` kiểm report: câu verdict, mức của từng lỗi, `file:dòng` có thật,
và mục `Nguồn và độ phủ` nêu đủ file trong diff.

Diff trên 10 file: `scripts/review_packages.py split` chia gói (tối đa 15 file), mỗi gói một reviewer chạy song song,
rồi `review_packages.py merge` gộp report. Review lại: `scripts/review_record.py save` lưu report và sha vào
`.fe-kit/reviews/<branch>.md`; lần sau `review_record.py last` cho sha đó, reviewer chỉ đọc phần đổi và kiểm lại lỗi cũ.

---

## Cài

**Claude Code**

```text
/plugin marketplace add nhathoagn/plugin-architecture
/plugin install fe-kit@fe-kit
```

`/plugin install` mở panel chọn scope — chưa chọn thì chưa cài. Từ shell:
`claude plugin marketplace add nhathoagn/plugin-architecture && claude plugin install fe-kit@fe-kit`

**omp**

```bash
omp plugin marketplace add nhathoagn/plugin-architecture
omp plugin install fe-kit@fe-kit
```

Trong TUI: `/marketplace add …` rồi `/marketplace install fe-kit@fe-kit`.

**Bản đang sửa trên đĩa**

```bash
claude --plugin-dir .
omp plugin link .
```

## Yêu cầu

- `sh` POSIX và `python3`. Windows cần Git Bash.
- Thiếu `python3` thì hook im lặng, plugin vẫn load — gate không chạy.
- `ut-report` cần `pyyaml` và `openpyxl`.

## Cấu trúc

```text
.claude-plugin/          manifest + marketplace
hooks/hooks.json         hook cho Claude Code
scripts/fe-gate.sh|py    gate dùng chung hai host
scripts/wording.py       lexer JS/TS/JSX + token diff cho wording/style
scripts/project_config.py  file thay đổi → luật dự án cần đọc (.fe-kit/config.yaml hoặc tự tìm)
scripts/review_check.py  kiểm report review-diff trước khi gửi
scripts/review_packages.py  chia diff lớn thành gói, gộp report các gói
scripts/review_record.py lưu review theo nhánh, đọc lại cho lần sau
scripts/yaml_subset.py   đọc tập con YAML, không cần pyyaml
presets/                 luật theo loại dự án (legacy-rewrite)
extensions/fe-gate.ts    adapter omp + test
skills/fe-kit/           SKILL.md, 6 playbook, references, evals
skills/ui-image-check/   so ảnh với code
skills/ut-report/        báo cáo UT + build_report.py
skills/refactor-depth-options/  liệt kê độ sâu refactor trước khi sửa
agents/reviewer.md       reviewer đọc diff
package.json             metadata + omp.extensions
README.md                trang này
CODEMAP.md               bản đồ code: module nào gọi module nào
```

## Đọc tiếp

| Tài liệu | Nội dung |
|---|---|
| [`skills/fe-kit/SKILL.md`](skills/fe-kit/SKILL.md) | Workflow, 6 field, hard rule |
| [`skills/fe-kit/playbooks/`](skills/fe-kit/playbooks/) | Từng loại việc một file |
| [`skills/fe-kit/references/`](skills/fe-kit/references/) | Ownership, reuse, performance, audit, checklist F1–F23 |
| [`skills/refactor-depth-options/SKILL.md`](skills/refactor-depth-options/SKILL.md) | Ladder độ sâu refactor + khi nào phải hỏi |
| [`rules/`](rules/) | 5 rule luôn bật, kèm ví dụ |
| [`CODEMAP.md`](CODEMAP.md) | Bản đồ kiến trúc plugin, ai gọi ai |
| [`skills/fe-kit/CHANGELOG.md`](skills/fe-kit/CHANGELOG.md) | Vì sao mỗi rule tồn tại — kèm sự cố thật |

## License

MIT
