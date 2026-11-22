# Review a diff that must keep its invariants

Use this when the diff adds or changes **tested behaviour**: a module with a test suite already exists, or the diff rewrites logic that replaces an older implementation. The diff report in `playbooks/review-diff.md` answers "what is wrong with this code". This playbook answers two finite questions instead:

1. Which invariant has no test that would fail if it broke?
2. Which invariant did the older version hold that this one no longer holds?

Use `playbooks/review-diff.md` when the diff carries no suite and adds no lasting behaviour — a one-off fix, a copy change, a config flip. Do not run both on one diff.

You are not the author. Do not fix, do not edit source, do not commit, do not spawn another reviewer.

## Why this mode exists

The findings mode measures the reviewer, not the code. Two passes over the same bytes report different counts and flip verdicts, because severity is a judgement. A test suite is an oracle: it answers the same way every run. In the findings mode each fix opens new surface and the next pass finds it, so the loop never closes. Here every defect becomes a test, and the loop closes when the questions have no open answer.

## Lenses

Two, not eight:

- `coverage` — `python3 ../../scripts/review_lenses.py brief coverage`
- `regression` — `python3 ../../scripts/review_lenses.py brief regression`

Spawn one reviewer per lens when the diff is large enough that one reader loses the thread; otherwise run both questions yourself in one pass, in that order. The coverage answer changes what the regression answer can claim, so coverage comes first.

## Chuẩn bị cho module (một lần, trước mọi rewrite)

- **`SPEC.md` cạnh module.** Bất biến đánh số `INV-01…`, threat model (input nào trong/ngoài phạm vi), danh tính đơn (field nào vào digest), rubric severity. Reviewer chấm theo file này, không theo cảm nhận. Thiếu `SPEC.md` thì dừng và báo — đây là điểm chặn, không phải gợi ý.
- **Characterization test trước khi thay implementation.** Trước mọi rewrite, chốt hành vi bản cũ bằng test vào/ra trên các ca đại diện. Không có nó, "bản mới mất hành vi" (F-094: 12 điểm, 6 phải khôi phục) chỉ lộ sau khi đã đổi xong.
- **Code trong git, mỗi fix một commit.** Không có diff thì không review được: một module untracked làm mọi finding thành "không có dữ liệu".

## Steps

1. Get the diff and the suite. The task names the range (`BASE..HEAD`, or `BASE` alone) and the test command. The project rules command prints `read:` lines for rule files and `file:` lines for review artifacts; read the `read:` files and the test files that cover the changed module, and ignore the artifacts.
2. Run the suite and the type check. Quote both results with their exit codes in the report. A suite you did not run cannot back a claim.
   When the module has **no suite** (a fixture, a reference implementation kept for comparison), the gate columns read `N/A — no suite` and the verdict is `CHƯA HỘI TỤ` by construction, because no invariant has a test. Say that in one line and spend the pass on the regression question instead.
3. **Coverage.** Enumerate the invariants the module must hold. Write each as one sentence that can be false: "stock never goes below zero", "one settled payload deducts once", "a rejected order moves no money", "same input yields the same key", "a different payload on the same id is a conflict", "money stays an integer and the parts add up". For each invariant, name the test that would fail if it broke. When no test exists, write `NO TEST` and give the smallest input that breaks the invariant — then run that input and quote what happened. Every row is either a named test or `NO TEST`; there is no third state. A test that exists but whose generator cannot reach the class that would break the invariant does not count: report `NO TEST` for that class and say which bound in the generator hides it.
4. **Regression.** Compare the diff with the version it replaces. Khi không có diff (file untracked), dùng **implementation tham chiếu được chỉ định trong task** làm bản cũ và ghi rõ đường dẫn đó; không tự chọn. For every invariant the older version held and this one does not, give one input and the observed result on both sides. Do not list the old defects the diff fixes: the question is what was lost. A behaviour that was tightened on purpose is listed under accepted losses, with the caller cost named.
5. **Verdict.** `HỘI TỤ` only when every invariant row names a test that would fail if it broke, no invariant fails on an input you ran, every lost behaviour is either restored or listed as an accepted loss, mutation score ≥ 80 **cho module có trong `mutate` của `stryker.config.json`**, and this pass produced no new fingerprint in the blocker class. Module nằm ngoài `mutate` không bao giờ đạt điều kiện này: ghi rõ và coi là chưa hội tụ. A row that reads `NO TEST` blocks the verdict, even when no input you tried breaks it: an untested invariant is an unproven one. Anything else is `CHƯA HỘI TỤ` plus the shortest list of what is missing. Do not answer "0 blocker" — that phrase is from the findings mode and means nothing here.
6. Write the report, then stop. One pass may answer both lenses: when it does, write `Lens: coverage+regression` on the first line and keep both tables in that file.

## Cổng vận hành (bắt buộc, sai một cái là lượt đó không dùng được)

**Khoá dụng cụ.** Ghi ở đầu report: model reviewer, playbook + version, lệnh test, commit hash. Đổi bất kỳ cái nào so với lượt trước thì lượt này **không so sánh** với lượt trước — chỉ dùng để tìm finding mới.

**Hash hai đầu.** Chạy `git rev-parse HEAD` (hoặc md5 file nếu chưa commit) lúc bắt đầu và lúc kết thúc. Lệch nghĩa là code đổi giữa lượt: **huỷ lượt**, không viết report.

**Một đường ra cho mỗi lượt.** Report ghi vào `<out>/review-<run-id>-<lens>.md`. Nếu file đã tồn tại thì dừng và báo — hai reviewer ghi cùng một path sẽ xoá finding của nhau.

**Repro phải nằm trong repo.** Không chấp nhận script `/tmp`. Mỗi finding cần một test trong `extensions/<module>/__review__/<run-id>.repro.test.ts` chạy được bằng lệnh test của module, và phải **đỏ** trước khi sửa. Test không đỏ = không có finding.
Ngoại lệ duy nhất: **lượt bảo trì playbook** (chạy trên fixture đối chứng, không được sửa source). Khi đó probe inline được phép, nhưng mỗi finding phải ghi `no-repro (probe)` và **không được xếp trên `major`** — thiếu test thì thiếu bằng chứng tái lập.

**Loại tự động, không cần bàn.** Một finding bị loại khi: (a) không có repro test trong repo; (b) severity không khớp rubric trong `SPEC.md`; (c) cần input ngoài threat model mà gán trên `minor`; (d) trùng fingerprint với mục đã đóng.

**Fingerprint.** Trước khi cấp id mới, so `.scratch/findings-index.md` theo `invariant|file|root-cause`. Trùng fingerprint thì cập nhật dòng cũ, không tạo id mới. Đếm finding theo fingerprint, không theo dòng report.

**Threat model quyết định severity.** Input ngoài threat model (Proxy, getter ném, object nội bộ) tối đa `minor`. Input trong threat model mà sai tiền/kho = `blocker`. Không có ngoại lệ.

**Lens chặn merge:** correctness, invariant, coverage, regression, probe. **Lens không chặn:** hygiene, naming, structure, performance, contract — gom thành danh sách cải tiến, xử lý theo lô.

**Ngân sách.** Tối đa 3 lượt review sau lượt đầu. Hết ngân sách mà vẫn có fingerprint mới ở nhóm chặn merge → dừng và báo người: vấn đề ở spec hoặc thiết kế, không phải code.

**Luật hai lần.** Cùng một cơ chế bị sửa lần thứ hai mà vẫn sinh finding cùng nhóm → dừng vá, viết ghi chú thiết kế ≤ 1 trang, thiết kế lại. Đây là luật đã thiếu trong vòng lặp 16 pass của module checkout.

## Việc của người sửa (không phải của reviewer)

- Chuyển mỗi repro test sang test chính thức, đặt tên theo hành vi, ghi id finding trong tên hoặc comment. Chạy thấy **đỏ** trước, sửa code, rồi chạy lại cổng.
- **Không sửa** trong cùng PR fix: `*.test.ts` đã có, `SPEC.md`, `schema.ts`. Cần đổi một trong số đó → dừng, ghi lý do, chờ người duyệt. Đổi schema là đổi hợp đồng.
- **Khác model với reviewer.** Cùng model thì "review" chỉ là tự xác nhận.
- **Mỗi finding một commit**: `fix(<module>): <F-xxx> <tóm tắt>`.
- Gom finding cùng `root_cause`, sửa một lần ở gốc. Cơ chế bị sửa lần thứ hai mà vẫn sai → dừng vá, viết ghi chú thiết kế lại.

## Sau khi merge

Nhóm lỗi lặp từ 2 lần trở lên phải biến thành **cơ chế chặn**: một ESLint rule, một ràng buộc trong schema, hoặc một dòng trong `AGENTS.md`. Seed fast-check tìm ra lỗi thì thêm chính input đó vào `examples` của property. Một finding đã sửa mà không để lại hàng rào là finding sẽ quay lại.

## Bảo trì playbook

Mỗi lần sửa file này hoặc `scripts/review_lenses.py`: chạy lại trên một module đối chứng có lỗi **biết trước** (file cố tình chứa các lớp lỗi G1–G6, để ngoài thư mục code sản phẩm) và xác nhận playbook vẫn tìm ra chúng. Một playbook không tự bắt được lỗi đã biết thì không dùng để kết luận được.

## Hai prompt dùng trực tiếp

**Reviewer**

```text
Bạn là reviewer cho commit <hash> (base <base>). Chạy `git rev-parse HEAD`; khác <hash> thì dừng và báo.
Đọc: SPEC.md cạnh module, kết quả cổng tự động (`bunx tsc --noEmit -p tsconfig.json`,
`bunx eslint <module> --max-warnings 0`, `bun test <module>`, `bunx stryker run`), và `git diff <base>..<hash>`.
Không đọc cả repo.
Nhiệm vụ: tìm vi phạm INV-xx trong SPEC.md với input TRONG threat model.
Mỗi nghi vấn: viết test vào <module>/__review__/<run-id>.repro.test.ts và CHẠY nó. Test không đỏ = không có finding.
Severity theo rubric trong SPEC.md; input ngoài threat model tối đa minor.
Lỗi ngoài spec không phải finding: ghi vào mục "Đề xuất sửa SPEC".
Trước khi cấp id mới, so fingerprint `INV|file|root-cause` với .scratch/findings-index.md; trùng thì cập nhật.
Ghi `.scratch/review-<run-id>-<lens>.md`; file đã tồn tại thì dừng và báo. Kiểm hash lần nữa trước khi kết thúc.
```

**Fixer**

```text
Sửa các finding sau: <ids>. Gom theo root_cause, sửa một lần ở gốc.
Mỗi finding: chuyển repro test sang test chính thức (tên theo hành vi, ghi id), chạy thấy đỏ, sửa, rồi chạy lại
toàn bộ cổng (tsc, eslint, test, stryker) và báo lệnh + exit code.
KHÔNG sửa: *.test.ts đã có, SPEC.md, schema.ts. Cần đổi thì dừng và ghi lý do.
Nếu đây là lần sửa thứ hai của cùng cơ chế: không vá, viết ghi chú thiết kế lại và dừng.
Mỗi finding một commit: fix(<module>): <F-xxx> <tóm tắt>.
```

## Report

Write it in Vietnamese, to a file the task names (`.scratch/review-invariants-<lens>.md` by default). First line `Lens: <name>`.

```markdown
Lens: <coverage|regression|coverage+regression>

# Kết quả review bất biến

## Kết luận

HỘI TỤ | CHƯA HỘI TỤ — <một câu nêu lý do>. Bộ test: <N> pass / <M> fail, exit <code>. Type check: exit <code>.

## Bảng bất biến

| # | Bất biến | Test chặn nó | Kết quả |
|---|----------|--------------|---------|
| 1 | <câu có thể sai> | `<tên test>` | xanh |

Một dòng `NO TEST` phải kèm input nhỏ nhất phá được và kết quả chạy thật:

| 2 | <bất biến> | NO TEST | đỏ với input `<input>` → `<kết quả>` |

## Mất mát so với bản cũ

| Hành vi | Input | Bản cũ | Bản mới | Xử lý |
|---------|-------|--------|---------|-------|
| <hành vi> | `<input>` | <kết quả> | <kết quả> | khôi phục / chấp nhận, giá phải trả: <cái gì> |

## Việc cần làm

Chỉ những bất biến đỏ hoặc `NO TEST`, mỗi mục một câu: bất biến nào, input nào phá, test nào cần viết.

## Nguồn và độ phủ

Luật đã đọc: <các file luật>
Bộ test: <lệnh> → <N> pass / <M> fail
Type check: <lệnh> → exit <code>
Độ phủ: <file> ✔
```

## Rules of evidence

- A claim needs a named test or a quoted run. An invariant you cannot break still needs its test: say which inputs you tried, and if none of them broke it, name the test that would catch a later break. An invariant with no such test stays `NO TEST`.
- One invariant, one row. Two invariants sharing a root cause stay two rows if a different input proves each.
- Report the smallest input that breaks an invariant, not the largest that fails. When the property tool shrinks a counterexample, report the shrunken one.
- A suite that passes proves only the inputs it runs. Name the classes of input nobody generates — bounds, empty collections, extreme magnitudes, reordered or duplicated entries — and treat the invariants that depend on them as `NO TEST` even when a hand-written case exists. A property test whose generator cannot reach a class is worth nothing for that class.
- Do not count a test that asserts the implementation's current behaviour instead of the invariant. A test whose expectation you had to change to make it pass is not evidence.
- Do not report a finding that belongs to the findings mode's checklist, unless it breaks an invariant you listed. This report is not a defect list.
