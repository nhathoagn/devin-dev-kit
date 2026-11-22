# Handoff — record-count test states + pure-refactor rules (1.38.1)

## 1. Logic

Three new checks enter the kit, all about list/table screens and refactor discipline:

- **U17** (`test-checklist.md`): tests for a screen with a list/table must cover
  0 / 1 / few / many records, one test per level. FAIL when only one level runs.
- **T11** (`REVIEW_CHECKLIST.md`): diff-level twin of U17 — a diff that adds or edits
  tests for such a screen but tests only one record-count level fails. Cross-referenced
  with U17, counted once.
- **F25** (`review-checks.md`, lens `correctness`): a table/list whose container forces
  a height (`height`/`min-height`/`overflow`) fails when few rows still show a scrollbar
  or leave a dead band. Wired into `scripts/review_lenses.py` so the fan-out reads it.
- `audit.md` Operational flow names the same states for the authoring side.
- `ut-report/SKILL.md` mandatory case 9 wires the same four levels into the manual UT
  template; Layout and Nghiệp vụ groups point at it.
- `refactor-ui.md` pins the pure-refactor contract (behavior-preserving only; bugs found
  go to a separate change) and gains step 9: typecheck/lint/test/build + exit codes +
  before/after screen compare.
- `code-quality.md` header states the goal: lower complexity so code reads as the spec.

## 2. Implementation

Files changed by this session:

- `skills/fe-kit/references/test-checklist.md` — U17 item, Osherove citation, TDD note
- `skills/fe-kit/references/REVIEW_CHECKLIST.md` — T11 item after T10
- `skills/fe-kit/references/review-checks.md` — F25 row after F24
- `scripts/review_lenses.py` — F25 appended to correctness lens items
- `skills/fe-kit/references/audit.md` — record-count bullet in Operational flow
- `skills/fe-kit/references/fowler-checklist.md` — U1–U16 → U1–U17
- `skills/fe-kit/references/code-quality.md` — goal sentence in header
- `skills/fe-kit/playbooks/refactor-ui.md` — scope contract paragraph + step 9 Verify
- `skills/ut-report/SKILL.md` — description, Layout group, Nghiệp vụ group, case 9
- `skills/fe-kit/CHANGELOG.md` — 1.38.1 entry
- `package.json`, `.claude-plugin/plugin.json`, `.devin-plugin/plugin.json`,
  `.claude-plugin/marketplace.json` — version 1.38.1

## 3. Decisions

- T11 is not assigned to a lens: the whole T group (T1–T10) is outside the lens split;
  T11 stays consistent with that. F25 needed a lens or the fan-out would never read it.
- The scroll bug lives in three places on purpose: F25 for diff review, the audit bullet
  for authoring, ut-report case 9 for manual UT — three different consumers.
- "Ít record mà còn thừa khoảng trống dưới table và table hiển thị scroll là bug" is
  encoded as container-forced-height; a pagination rule is intentionally NOT added.

## 4. Debug without AI

- U17 fires on `*.test.*`/`*.spec.*` content; T11 fires on the diff's test files.
- F25 grep seed: `height|min-height|overflow` inside a list/table container in the diff.
- If a review report never mentions F25, check `scripts/review_lenses.py` lens
  `correctness` — missing from `items` means no reviewer reads it.
- `python3 scripts/test_versions.py` validates the version bump (6 cases, 0 failures).

## 5. Risks

- F25 can false-positive on intentionally fixed-height virtualized tables; the item
  says "few rows still show a scrollbar" — a virtualized list with fixed viewport is
  the correct shape when rows exceed it, N/A otherwise.
- T11 can be N/A-heavy on non-UI diffs; that is by design.

## 6. Q&A

User cancelled the Q&A round and asked to commit directly. Proposed default answers are recorded
unconfirmed:

