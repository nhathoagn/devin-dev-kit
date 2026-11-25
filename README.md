# fe-kit

![version](https://img.shields.io/badge/version-1.22.0-blue)
![hosts](https://img.shields.io/badge/hosts-Claude%20Code%20%7C%20Devin%20%7C%20omp-6e56cf)
![license](https://img.shields.io/badge/license-MIT-green)

**Plugin frontend bắt agent ghi rõ ai sở hữu code và dùng lại hay viết mới — trước khi được sửa một dòng.**

Agent viết UI rất nhanh. Vấn đề không phải tốc độ, mà là những gì nó để lại: business logic
nằm trong page, cùng một block code chép ở ba nơi, một giá trị đã có holder lại được thêm
`useState` thứ hai. Diff đọc vẫn sạch. Nợ chỉ lộ ra sau vài tháng.

fe-kit chèn đúng hai câu hỏi vào chỗ đó. Agent không trả lời được thì không sửa file.
Một plugin, chạy trên Claude Code, Devin CLI và omp.

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
Gate chỉ chặn code sản phẩm: file trong git repo, khớp `scope` của `.fe-kit/config.yaml`
gần file nhất (chưa khai `scope` thì mọi file code), không khớp `exclude`. Monorepo đặt config
riêng trong từng package; glob tính từ thư mục chứa config đó. Gate đọc config và danh sách
file từ commit `HEAD`, không đọc file trên đĩa: sửa `scope`/`exclude` chỉ có hiệu lực sau khi commit.
Đường dẫn được giải qua junction/symlink; một repo con tạo bên trong dự án không tắt được gate,
kể cả khi dự án chưa có config. Bash chỉ thế biến gán ngay trong lệnh; ghi vào `$HOME/…` hay biến
môi trường khác cũng phải khai nhãn. File ngoài mọi git repo
(scratchpad) không bị chặn. Script evidence trong repo không bị chặn khi nằm ngoài `scope`.
Lệnh Bash ghi file code mà gate không biết chắc đường dẫn (glob, regex, subshell, `pushd`,
hai `cd`, `cd $X`), hoặc ghi vào file đích còn biến chưa biết giá trị (`> "$F"`), vẫn bị chặn. Mỗi pattern `scope` phải khớp ít nhất một file git đang track;
nếu không, gate coi config là hỏng và chặn mọi file code.

**Code viết lần thứ hai.** `Decision:` phải là `reuse`, `extend`, `feature-local`,
hoặc `shared`. `shared` chỉ hợp lệ khi có từ hai consumer thật trở lên, nêu tên.
Bug fix còn bị hỏi: giá trị này đã có state hay prop nào giữ chưa?

**Người đọc không debug được.** Trước `git commit`, agent phải viết `.fe-kit/handoff.md`:
Logic, Implementation (từng file và hàm giữ bước nào), Decisions, Debug without AI (lệnh
reproduce, file:line để xem, lỗi nghĩa là gì, cách xác nhận fix, rollback), Risks, Q&A.
Agent hỏi bạn 3–5 câu về state holder, nhánh dễ sót và check chứng minh fix; câu trả lời
được ghi lại. Bạn chạy lệnh approve trong `skills/fe-kit/references/handoff.md`; commit bị
chặn đến lúc đó, và sửa file sau khi approve thì phải approve lại. Repo muốn tắt:
`handoff: "off"` trong `.fe-kit/config.yaml`.

**Chỉ review khi user yêu cầu.** Agent không tự review sau khi edit. Khi được yêu cầu, người viết diff không được review diff đó. Claude Code có
agent `fe-kit:reviewer` read-only; omp dùng một context sạch chỉ nhận diff range và playbook.

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
| Devin | Subagent `fe-kit:reviewer`, tool `read` / `grep` / `glob` / `exec`, không sửa, không commit, không spawn reviewer khác |

Không đưa ghi chú của tác giả. Reviewer thiếu playbook path trong task thì dừng, không tự bịa checklist.
Nó đi hết `references/REVIEW_CHECKLIST.md` rồi F1–F24 trong `references/review-checks.md`, và
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

## Ba host khác nhau ở đâu

| Khả năng | Claude Code | Devin | omp |
|---|---|---|---|
| Rule theo prompt | Hook `UserPromptSubmit` inject | Cùng hook, cộng thêm `trigger: always_on` | Rule always-on; badge `⚡ rules` báo prompt khớp |
| Chặn edit | Hook `PreToolUse` (`Write\|Edit\|MultiEdit\|Bash`) | Hook `PreToolUse` (`edit\|write\|apply_patch\|exec`) | `extensions/fe-gate.ts` trên `tool_call` |
| Kiểm sau khi ghi | Hook `PostToolUse`, exit 2 | Hook `PostToolUse`, exit 2 | Cùng extension, lỗi nằm trong tool result |
| Nhận diện bug / request | Đọc `transcript_path` | `prompt` + `prompt_id` trong payload, state file theo `session_id` | Như Devin |
| Sau compact | `SessionStart` + `PreCompact` nạp lại rule | `PostCompaction` + `SessionStart` trên resume | Không cần, rule vẫn bật |
| Verdict hiển thị | Không | Không | Status line: `✓ ok`, `✎ note`, `⛔ blocked`, `⚡ rules` |

Claude Code và omp dùng chung `scripts/fe-gate.sh` → `scripts/fe-gate.py`. Devin chạy `scripts/devin-gate.sh` →
`scripts/devin_gate.py`, dùng lại `wording.py`, `bash_target.py`, `label_store.py`, `project_config.py` và toàn bộ
`rules/` + skill. Payload Devin đã chứa `prompt` và `prompt_id`, nên gate không đọc transcript: `prompt_id` quay theo
mỗi tin nhắn user và định phạm vi nhãn của request.

---

## Luật riêng của dự án

fe-kit giữ luật chung cho mọi dự án React. Luật riêng của một dự án nằm trong repo của dự án đó.
`scripts/project_config.py` nhận danh sách file thay đổi và in ra file luật nào phải đọc.

File `.fe-kit/config.yaml` **không bắt buộc**. Chỉ viết khi cách tìm mặc định không đủ.

| Dự án | Cần làm | fe-kit đọc |
|---|---|---|
| Không có luật FE riêng | Không làm gì | Chỉ luật của fe-kit |
| Luật ở `AGENTS.md`, `CLAUDE.md`, thư mục `rules/` gần code, hoặc `REVIEW_CHECKLIST.md` ở root | Không làm gì | Tự tìm: root, rồi từng thư mục cha của file thay đổi |
| Cần map luật theo đường dẫn, thư mục spec riêng, lệnh cổng, file loại trừ, phạm vi gate, preset | Viết `.fe-kit/config.yaml` | Đúng file đã khai |

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
exclude: ["web/src/routeTree.gen.ts", "**/package-lock.json"]   # không review, không gate
scope: ["web/src/**", "api/app/**"]   # gate chỉ chặn file khớp; bỏ trống = mọi file code
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

Diff đến 10 file: `scripts/review_lenses.py list --pass 1` chia diff thành chín góc nhìn — tám chấm
checklist (vệ sinh diff, đúng biên và luồng, hợp đồng/caller/spec/test, bảo mật, chất lượng test,
kiến trúc và dùng lại, tên và mở rộng, tải và hiệu năng) cộng `audit` đi `references/audit.md`;
`list --pass 2` in `correctness`, `contract`, `probe`, `invariant` chỉ chạy sau fix tạo mặt contract
mới; mỗi lens
một reviewer chạy song song, mỗi item của checklist thuộc đúng một lens nên không mục nào bị sót hay soi
hai lần. Diff trên 10 file: `scripts/review_packages.py split` chia gói (tối đa 15 file), mỗi gói một
reviewer chạy song song, cộng thêm reviewer `--lens contract` và `--lens audit` trên toàn range cho
caller, spec, test và flow xuyên gói. `review_packages.py merge` gộp report: hai lens thấy cùng một `file:dòng`
gom thành một đoạn ghi cả hai nguồn. Sau khi sửa xong một lượt, một reviewer mới kiểm lại từng finding
ở HEAD; finding còn đúng thì quay lại sửa một lần. Review lại: `scripts/review_record.py save` lưu report
và sha vào `.fe-kit/reviews/<branch>.md`; lần sau `review_record.py last` cho sha đó, reviewer chỉ đọc
phần đổi và kiểm lại lỗi cũ.

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

**Devin CLI**

```bash
devin plugins install nhathoagn/plugin-architecture
devin plugins info fe-kit
```

`devin plugins install --local ./plugin-architecture` link bản trên đĩa (cần quyền symlink; trên Windows
thiếu quyền thì cài qua GitHub như trên). Subagent `fe-kit:reviewer` chỉ chạy ở CLI/Desktop, không có trong
Devin Cloud session — ở đó hand-off cho một phiên đọc playbook như omp.

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
.claude-plugin/          manifest + marketplace (Claude Code)
.devin-plugin/plugin.json manifest Devin
hooks/hooks.json         hook cho Claude Code
hooks.json               hook cho Devin (tool name thường, event riêng)
scripts/devin_gate.py    gate cho Devin (không đọc transcript)
scripts/devin-gate.sh    wrapper sh cho Devin
scripts/fe-gate.sh|py    gate dùng chung hai host
scripts/wording.py       lexer JS/TS/JSX + token diff cho wording/style
scripts/project_config.py  file thay đổi → luật dự án cần đọc (.fe-kit/config.yaml hoặc tự tìm)
scripts/review_check.py  kiểm report review-diff trước khi gửi
scripts/review_packages.py  chia diff lớn thành gói, gộp report các gói
scripts/review_record.py lưu review theo nhánh, đọc lại cho lần sau
scripts/review_lenses.py  chia review thành 13 góc nhìn theo pass (pass 1: 8 lens checklist + audit; pass 2: correctness, contract, probe, invariant; invariants: coverage, regression), một reviewer mỗi lens
scripts/yaml_subset.py   đọc tập con YAML, không cần pyyaml
presets/                 luật theo loại dự án (legacy-rewrite)
extensions/fe-gate.ts    adapter omp
fixtures/                input cố tình lỗi để kiểm review tool (review-seed.ts + fixed/)
skills/fe-kit/           SKILL.md, 9 playbook, references, evals
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
| [`skills/fe-kit/references/`](skills/fe-kit/references/) | Ownership, reuse, performance, audit, checklist F1–F24 |
| [`skills/refactor-depth-options/SKILL.md`](skills/refactor-depth-options/SKILL.md) | Ladder độ sâu refactor + khi nào phải hỏi |
| [`rules/`](rules/) | 5 rule luôn bật, kèm ví dụ |
| [`CODEMAP.md`](CODEMAP.md) | Bản đồ kiến trúc plugin, ai gọi ai |
| [`skills/fe-kit/CHANGELOG.md`](skills/fe-kit/CHANGELOG.md) | Vì sao mỗi rule tồn tại — kèm sự cố thật |

## Sách nền cho người đọc code

Checklist trong skill sinh ra từ các cuốn này — intern/fresher đọc để hiểu vì sao reviewer flag, không chỉ nghe verdict.

| Mức | Sách | Skill dùng ở đâu |
|---|---|---|
| Fresher | *The Art of Readable Code* — Boswell & Foucher | `references/readability.md`: Time to Understand, trace test, naming §5 |
| Fresher | *Clean Code* — Robert C. Martin | N1–N5, SM1–SM3: tên, hàm nhỏ, DRY |
| Fresher | *Code Complete* (2nd ed) — Steve McConnell | construction nói chung; nền trước khi đọc hai cuốn trên |
| Junior/Mid | *Refactoring* (2nd ed) — Martin Fowler | `references/fowler-checklist.md` + `references/smells-checklist.md` — toàn bộ |
| Junior/Mid | *A Philosophy of Software Design* — John Ousterhout | `references/posd-checklist.md`: module depth, pull complexity down |
| Junior/Mid | *Tidy First?* — Kent Beck | `references/tidy-checklist.md`: tidy tách khỏi behavior |
| Mid | *The Pragmatic Programmer* (20th anniv.) — Hunt & Thomas | orthogonality (D4), tracer bullets; đọc để có khung, checklist không đếm lại |
| Mid | *Unit Testing* — Vladimir Khorikov | `references/test-checklist.md`: resistance to refactoring |
| Mid | *SQL Antipatterns* — Bill Karwin | nền cho `references/performance-logic.md` §1; depth thuộc skill `database-optimizer` |

## License

MIT
