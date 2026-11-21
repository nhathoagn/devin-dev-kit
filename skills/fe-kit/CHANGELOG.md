# Changelog

## 1.35.0

omp has no hook to spawn a reviewer subagent after an edit the way Claude Code wires one, so the "reviewer runs after each diff" behavior never fired on omp — the skill could only tell the agent to do it, nothing enforced it.

- New `extensions/auto-review.ts`: on every `edit`/`write`/`ast_edit` `tool_result`, appends an `[auto-review]` note instructing the agent to run the fe-kit reviewer (or `skill://fe-kit/playbooks/review-diff.md`) on the changed files; `before_agent_start` attaches the collected file list so the review names its targets; `session_start` clears the set. It is an injected instruction, not a spawned subagent — omp extensions cannot start tasks from handlers.
- `package.json` `omp.extensions` registers it next to `fe-gate.ts`; `README.md` and `CODEMAP.md` list it.
- Version 1.35.0 in `.devin-plugin/plugin.json`, `.claude-plugin/plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.34.0

A silent depth choice on an ambiguous "improve" request wasted rounds: a nested-if file went flatten → over-corrected loop → revert → find+table because the option set was never shown. The user had to name the depth ("still too much if") before the right level appeared.

- New `skills/refactor-depth-options/SKILL.md`: when an improve/refactor/clean-up request omits depth, enumerate the ladder — keep shape, change pattern (table/rule list, `find` + `??`), restructure — with a one-line tradeoff each, recommend one with a reason tied to the code's shape, then ask or proceed while naming the alternatives not taken. Skip conditions: a single viable level or a request that already names the depth. Vietnamese triggers included.
- `README.md` gains the "Độ sâu refactor" section, a structure line, and a Đọc tiếp row; `CODEMAP.md` lists the new skill folder.
- Version 1.34.0 in `.devin-plugin/plugin.json`, `.claude-plugin/plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.33.0

The Fowler catalog covers intra-class moves, but a frontend refactor hits moves the catalog cannot name: a prop drilled through two levels, an effect that exists only to sync state with state, a serial `await` pair that is not a real dependency, a `useEffect` fetch reimplemented per screen. Each was fixed ad hoc because no file named the move or its guard.

- New `references/frontend-moves.md`: 15 FE-shaped moves (FM1–FM15) in Fowler's move format — signal, mechanics, and a "Đừng khi" guard. Four groups: state placement (lift state up, colocate state down, prop drilling → composition/context, effect → derived state), component split axes (split by change axis not by code kind, extract custom hook, extract list item, effect → event handler), async and fetch (then-chains → async/await, serial → parallel where the dependency is not real, fetch-in-effect → the repo's data layer, unstable deps → stable), and data/render (repeated JSX → typed record + map, abort/cleanup for async effects, code-split at route boundaries). Each move says when NOT to apply it — the guard is the point.
- `playbooks/refactor-ui.md` step 7 sends FE-shaped cures to the new catalog alongside `patterns.md`.
- `references/fowler-checklist.md` points at the new file.
- Version 1.33.0 in `.devin-plugin/plugin.json`, `.claude-plugin/plugin.json`, `package.json`, and both places in `marketplace.json`.
- `scripts/devin_gate.py` ports the pre-commit handoff gate: `git commit` over exec is blocked until `.fe-kit/handoff.md` is written, Q&A'd in chat, and approved by the user, matching the Claude gate since upstream 1.29.0.

## 1.32.0

Five checklists name and score problems, but when a FAIL's cure is bigger than a tidying there was no map to the named solutions. A refactor fixing repeated switches had to reinvent what is called a State pattern, and there was no guard checking whether the pattern was even needed — an unneeded pattern is Speculative Generality, not a cure.

- New `references/patterns.md`: a forward lookup `tín hiệu → pattern → áp khi / đừng áp khi` from *Head First Design Patterns*, written for JS. Four groups — variant behavior (Strategy, State, Template Method, param injection), object creation (Factory Method, Abstract Factory, Singleton), object relations (Observer, Decorator, Adapter, Facade, Command, Proxy, Composite), and the patterns JS already absorbed (Iterator, Observer, Singleton, MVC). Every row has a "Đừng áp khi" column: the guard is the point — a pattern applied where the problem does not exist yet is SM17/O7.
- `playbooks/refactor-ui.md` step 7 sends cures bigger than a tidying to `references/patterns.md` before proposing them.
- `references/fowler-checklist.md` points at the new file.
- Version 1.32.0 in `plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.31.0

Four checklists score production code, and `REVIEW_CHECKLIST.md`'s T group checks that tests exist — but nothing scored the tests themselves. A suite could exist, be deterministic, go red when behavior breaks, and still pin every assertion to implementation details: a refactor that keeps behavior would break it everywhere, teaching the team to ignore red tests. That is Khorikov's resistance-to-refactoring failure, the costliest test failure mode there is.

- New `references/test-checklist.md`: 16 items (U1–U16) from *Unit Testing: Principles, Practices, and Patterns*. U1–U4 are the four pillars as FAIL tests; U5–U7 are mock hygiene (mock only unmanaged/out-of-process dependencies, never assert on stubs, verify at the system boundary); U8–U12 are the anti-patterns (private-method testing, test-only code in production, tautological expectations, hidden time/randomness); U13–U16 are the integration and DB rules (real databases over in-memory, never mock repositories, independent fixtures, no coverage-chasing asserts). Each item cross-references its twin in `REVIEW_CHECKLIST.md` or the other checklists so a finding counts once.
- `playbooks/refactor-ui.md` step 7 reads it when the work adds or changes tests — the other four score the production code, this one scores the suite.
- `references/fowler-checklist.md` points at the new file.
- Version 1.31.0 in `plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.30.0

Three checklists score the code a refactor produces, but none governs how the work is done. A diff could land every FAIL it touched and still mix tidy commits with behavior changes, tidy code about to be deleted, or edit inside a tangle it could not read — the failure modes Kent Beck's *Tidy First?* exists for.

- New `references/tidy-checklist.md`: T1–T15 are the fifteen tidyings (guard clauses, explaining variables/constants, one pile, new-interface-old-implementation, chunk statements, …) written as FAIL tests; T16–T21 are the managing rules — separate tidy commits from behavior commits, timebox tidying chains, batch against review cost, tidy at natural pauses, get untangled by tidying first instead of editing inside the tangle, and the book's titular question: tidy only where the next change will pass. Each item cross-references its twin in the other checklists so a finding counts once.
- `playbooks/refactor-ui.md` step 7 reads it after the other three: the first three score the code, this one governs how the tidying lands.
- `references/fowler-checklist.md` points at the new file.
- Version 1.30.0 in `plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.29.0

AI writes code faster than the person who has to maintain it can follow. A change could pass every gate and still leave the user unable to explain the logic or debug it without the AI. The last step before a commit was missing.

- New `references/handoff.md`: `.fe-kit/handoff.md` with six sections a person reads — Logic, Implementation, Decisions, Debug without AI, Risks, Q&A. The implementation section names every changed file and the function that owns each step. The debug section gives the reproduce command, the file:line to watch, what each failure means, how to verify a fix, and the rollback. The Q&A is 3–5 questions about the state holder, the easy-to-miss branch, and the check that proves a fix; the user's answers are recorded.
- New `scripts/handoff.py`: `check` reports a missing section, an unnamed staged file, a missing approval, or an approval older than a staged file; `approve` stamps `Confirmed-by`/`Confirmed-at` and refuses an incomplete handoff. The agent does not approve its own handoff.
- `scripts/fe-gate.py`: a `git commit` (including `-a` and `-C`) is denied until the handoff covers every staged source file and the user approved it. A docs-only commit passes. An edit after approval invalidates it.
- `scripts/project_config.py`: new `handoff` key (`required` | `off`), including the YAML boolean an unquoted `off` produces.
- `rules/fe-implementation.md`, `skills/fe-kit/SKILL.md`: the pre-commit handoff and the user's approval are part of the workflow.
- Tests: new `test_handoff.py` 10 cases; `test_fe_gate.py` 223 cases, including the commit gate (no handoff, no approval, approved, stale, off).
- Version 1.29.0 in `plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.28.0

Two Fowler checklists can name and score smells, but neither asks Ousterhout's question: whether a module is deep — whether its interface costs less than the complexity it hides. A refactor could remove every named smell and still ship a shallow module, an interface that pushes work up to callers, or an error case a simpler contract would have defined away.

- New `references/posd-checklist.md`: 16 items (O1–O16) from *A Philosophy of Software Design* — the red flags plus the principles that check out in a diff. Covers items the Fowler lists do not name: temporal decomposition (a module split that mirrors execution order leaks the shared knowledge through every interface), pass-through variables, overexposed interfaces, pull-complexity-down, define-errors-out-of-existence, implementation details contaminating an interface, and hard-to-describe units. Each item cross-references its Fowler twin so a finding counts once.
- `playbooks/refactor-ui.md` step 7 reads `posd-checklist.md` after the two Fowler checklists, for the depth questions those two do not ask.
- `references/fowler-checklist.md` points at the new file.
- Version 1.28.0 in `plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.27.0

A reviewer could score structure yet had no index to name what it found. `fowler-checklist.md` orders items by refactoring family (F1–F6), so mapping a symptom to a Fowler smell name and its cure meant knowing the catalog by heart — and `playbooks/refactor-ui.md` only scored code after the edits, so a refactor plan did not name the smells it was removing.

- New `references/smells-checklist.md`: the 24 chapter-3 smells (SM1–SM24) as a detection index. Each item names the symptom, the FAIL test, the cure refactor, and the equivalent item in `fowler-checklist.md` or `REVIEW_CHECKLIST.md` so a finding counts once. Written for the `smell → refactor → vì sao` finding format.
- `playbooks/refactor-ui.md` step 7 reads `smells-checklist.md` then `fowler-checklist.md`: the first names smells on the code the refactor will touch, before the first edit; the second scores what it touched.
- `references/fowler-checklist.md` points at the new index.
- Version 1.27.0 in `plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.26.1

Devin runs plugin hooks without `CLAUDE_PLUGIN_ROOT` in the environment, so every `hooks/hooks.json` command resolved to `/scripts/fe-gate.sh` and failed with `Command exited with code 127` on each prompt and tool call. The Devin host injects `DEVIN_PLUGIN_ROOT` for plugin hooks (with `PLUGIN_ROOT` as a further fallback).

- `hooks/hooks.json`: each command is now `sh -c 'R="${DEVIN_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}}"; [ -f "$R/scripts/fe-gate.sh" ] || R=$(cygpath -u "$R" 2>/dev/null || printf %s "$R"); [ -f "$R/scripts/fe-gate.sh" ] || exit 0; exec sh "$R/scripts/fe-gate.sh"'`. The first env var that exists wins, `cygpath` still normalizes the root on Git Bash for Claude Code on Windows, and a root that yields no script exits 0 instead of surfacing a 127 hook failure.
- Version 1.26.1 in `.devin-plugin/plugin.json`, `.claude-plugin/plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.26.0

- Devin CLI host: `.devin-plugin/plugin.json`, root `hooks.json`, `scripts/devin-gate.sh`, and `scripts/devin_gate.py`. The Devin payload carries the prompt and `prompt_id`, so the gate keys labels by request without reading a transcript. Block uses `{"decision": "block"}`; `PreCompact` has no Devin equivalent, so `PostCompaction` and `SessionStart` on resume re-inject the pointer. Rules ship `trigger: always_on`; the reviewer agent declares `allowed-tools` for Devin next to `tools`/`model` for Claude Code.
- `rules/review-diff.md`, `skills/fe-kit/SKILL.md`, and `agents/reviewer.md` name the Devin reviewer path (`fe-kit:reviewer` subagent).
- `scripts/test_versions.py` also checks `.devin-plugin/plugin.json`.

## 1.26.0

The 1.25.2 fallback still missed the case it was written for: `request_scope()` follows physical line order, so when the host appended the prompt line after the echo entry, the echo fell outside the request, and the state key (a hash of the request text) named a different request. The same text in a later prompt reopened an old declaration, and a half-written transcript line or an echo whose `tool_result` failed counted as a declaration.

- Request identity comes from the host, not the text. `payload_prompt_id()` reads `prompt_id` (present on every Claude Code hook call of a turn); the state is keyed by it, falling back to the entry `promptId`/`uuid`, then the text for hosts without either. A later prompt with the same text is a new request.
- Transcript declarations are matched by prompt id and count only after a non-error `tool_result`, so an echo the host denied or never ran is not a declaration, and a prompt flushed after the echo still matches. Entries without ids keep the physical request scope.
- `parse_transcript()` skips a line that is not complete JSON; a torn assistant line no longer becomes authored text.
- `label_store.declared_lines()` reconstructs what echo/printf prints: unquoted labels, a `cd ... &&` prefix, assignments, and `2>/dev/null` count. `printf` binds `%s` in order. Backticks, substitutions, pipes, other redirects, and unresolved `printf` specs are rejected with a reason instead of silently; the Bash hook emits that reason when a label-looking command is not a declaration.
- Owner placeholders are checked after stripping brackets: `(none)`, `see below`, `TBD2`, `%s`, `$VAR` do not count. A pipe skips only a real table row, so `Runtime owner: OrderForm|useOrder` counts, while a menu of decision words still does not.
- `CONTINUATION_RE` accepts `ok nhé`, `oki`, `cứ tiếp tục`, `làm tiếp đi`, `tiếp nhé`, `được nhé`. Host notices (`<bash-input>`, `<total_tokens>`, …) are searched after reminders are stripped and no longer start a request; a slash command's `<command-args>` is the person text; an image-only message does start a request.
- `label_store.save()` takes a lock and replaces the file atomically, so two parallel echoes do not lose each other.
- A workflow subagent transcript under `subagents/workflows/<run>/agent-<id>.jsonl` is found. `parse_transcript()` caches by mtime and size, and the flush retry re-parses only when the file changed.
- `PostToolUse` now covers `Bash`, so a file written through Bash gets the conflict-marker and repo-rule checks. `run_repo_rules()` runs `.claude/rules.sh` through `sh` on Windows. `load_rule()` returns empty text on a missing or unreadable rule file instead of exiting 1. `fe-gate.sh` probes `python3` before `exec`, so a Windows Store alias or the Xcode shim cannot disable the hook silently.
- `scripts/bash_target.py`: the runner boundary no longer matches `py`/`tsx` inside a path (`git add a.py b.py` is not a script run); redirects, tee, and write calls are read outside quotes; `sed -i`, `perl -i`, `cp`, and `mv` are parsed by token, so `s|a|b|`, scripts with `;`, directory destinations, and `-t` work; a test script's fixture writes are not gated.
- `scripts/wording.py`: a literal under a code-named property or assignment is code even inside a copy call (`setError("email", …)`, `showToast("success", …)`, `const error = …`); `${count} items` and `intl.formatMessage`/`defaultMessage` are copy.
- Tests: `test_fe_gate.py` 218 cases, including a prompt flushed after the echo, the same text under a new prompt id, a torn line, a denied echo, unquoted/cd/redirect/backtick declarations, placeholders, a pipe in a value, continuation variants, host notices, image-only messages, and a workflow subagent echo. New `test_bash_target.py` 18 cases. `test_wording.py` 85 cases.
- Version 1.26.0 in `plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.25.2

An `echo` declaration could be lost even though the agent ran it. The declaration was saved under a hash of the latest user text read when the echo hook ran. When the host had not flushed the current user message to the transcript yet, that hash named the previous request, so the edit hook looked up a different entry and denied the edit with the Reuse Decision message.

- `scripts/fe-gate.py`: `authored_entries()` also reads declaration `echo` commands from the assistant's Bash `tool_use` blocks (`entry_bash_commands`), so `request_scope()` and `scoped_entries()` see a declaration the agent already ran at gate time, even when the state entry was keyed by an unflushed request. A declaration before the latest user message still does not count, and a main-agent edit still does not see a subagent's declaration.
- `scripts/test_fe_gate.py`: 3 new cases; 2 fail on 1.25.1 (an echo that exists only in the transcript, and an echo in the same assistant message as the edit). The third, an echo before a newer request, already denied and is a guard for scope trimming.
- Version 1.25.2 in `plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.25.1

Devin runs plugin hooks without `CLAUDE_PLUGIN_ROOT` in the environment, so every `hooks/hooks.json` command resolved to `/scripts/fe-gate.sh` and failed with `Command exited with code 127` on each prompt and tool call. The Devin host injects `DEVIN_PLUGIN_ROOT` for plugin hooks (with `PLUGIN_ROOT` as a further fallback).

- `hooks/hooks.json`: each command is now `sh -c 'R="${DEVIN_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}}"; [ -f "$R/scripts/fe-gate.sh" ] || R=$(cygpath -u "$R" 2>/dev/null || printf %s "$R"); [ -f "$R/scripts/fe-gate.sh" ] || exit 0; exec sh "$R/scripts/fe-gate.sh"'`. The first env var that exists wins, `cygpath` still normalizes the root on Git Bash for Claude Code on Windows, and a root that yields no script exits 0 instead of surfacing a 127 hook failure.
- Version 1.25.1 in `plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.25.0

On Windows, every `hooks.json` command failed with `bash: -c: line 1: unexpected EOF while looking for matching '"'` and the runtime blocked each prompt and tool call. A hook runner spawns `sh -c '<command>'` through Git Bash (MSYS2). MSYS2 converts a `-c` argument that looks like a Windows or POSIX path, and the conversion drops the closing double quote, so bash sees an unterminated string. `MSYS2_ARG_CONV_EXCL` cannot repair it from inside the string: it only fixes the quote, then `fe-gate.sh` passes its `/c/...` script directory to a native `python.exe` that cannot open it.

- `hooks/hooks.json`: each command is now `"$(cygpath -u '${CLAUDE_PLUGIN_ROOT}' 2>/dev/null || printf %s '${CLAUDE_PLUGIN_ROOT}')/scripts/fe-gate.sh"`. On Git Bash, `cygpath -u` converts the substituted path to `/c/...` inside the shell, so the `-c` argument never contains a bare quoted path for MSYS2 to mangle. On macOS and Linux, `cygpath` does not exist, the `printf %s` fallback emits the already-POSIX path, and the hook runs unchanged.
- Reproduced with `subprocess.run([sh, "-c", '"C:\\…\\fe-gate.sh"'])` (no MSYS parent): exit 2 with the EOF error; the same spawn with the `cygpath` wrapper exits 0 and `fe-gate.py` emits `hookSpecificOutput.additionalContext`. Verified `cygpath` exists under `sh -l` on Git for Windows, and the fallback branch exits 0 with a POSIX root.
- Version 1.25.0 in `plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.24.0

A refactor finished while the smells it touched were still standing, because no file owned that check. The diff reviewer deliberately scores no structural smells (`playbooks/review-diff.md` excludes them), and `references/audit.md`'s judgement list was advisory severity `low` only — nothing made a touched smell block completion.

- New `references/fowler-checklist.md`: 28 items across Fowler's six refactor groups (F1a–F6c), PASS / FAIL / N/A format matching `REVIEW_CHECKLIST.md`. Covers items no other checklist names: shared mutable constants (`locks = ALL_LOCKS` by-ref vs spreads), non-exhaustive else-if (a red class in mode '1' falls through with stale locks and a negative qty), over-consolidated `||` predicates, confusable adjacent params (`mode`/`displayMode`), shadow `*_keep` fields, `let` temps reassigned across branches, and silent spread-override in return objects.
- `playbooks/refactor-ui.md` step 7: a refactor that finishes while a Fowler smell it touched still stands is incomplete, not PASS.
- `references/audit.md`: the judgement-call list narrows to three React-only bullets (`a.b().c()` or `a.b.c` walks, forwarders, ignored-extends). On a refactor task, Fowler scores the touched code and those three bullets still run on untouched audit-scope files (imported hooks/services/schemas). The diff reviewer keeps not scoring them.
- Borderline verdicts are `FAIL` with "borderline" in the reason — no fourth verdict.
- Two rounds of 10-agent lens review on `applyShipClassChange` produced the item set; gaps named by the lenses (middle man, refused bequest, record-type move target) are covered.
- Version 1.24.0 in `plugin.json`, `package.json`, and both places in `marketplace.json`.

## 1.23.0

The reviewer read project rules only from a root `REVIEW_CHECKLIST.md`. The JTEK repo keeps its FE rules in `tvmk_admin/rules/` and maps them by path in `workflow/lenses/paths.yaml`, so the reviewer read none of them. The spec search looked only in `docs/`, `specs/`, and `.scratch/`, and the repo keeps approved designs in `works/design/`. The reviewer also had no step to search callers outside the diff, no step to drop a wrong finding, and no check of its report. `marketplace.json` stayed at 1.19.0 through 1.22.0, so `/plugin install` could keep an old build.

- New `scripts/project_config.py`: changed files → the project rule files to read, the spec folders, the gate commands, and the excluded files. The repo file `.fe-kit/config.yaml` is optional. With no config, the script searches `AGENTS.md`, `CLAUDE.md`, and `rules/` folders from the repo root to each file's folder, and a root `REVIEW_CHECKLIST.md` on a review. A broken config exits 2 with the line number.
- New `scripts/yaml_subset.py`: reads the YAML subset of the config with the standard library only, because the hooks must run without PyYAML. Syntax outside the subset raises an error with the line number, and is never read in a wrong way.
- New `presets/legacy-rewrite/`: `design.md` (questions before code) and `review.md` (a behavior that matches the old system, with no change request, is not a finding). A config lists presets by name, or by a `./` path in the repo.
- New `scripts/review_check.py`: exit 1 when the verdict sentence is missing, the verdict does not match the finding levels, a `file:line` does not exist, or `Nguồn và độ phủ` misses a file of the diff. A reference outside the diff is a `!` warning.
- `playbooks/review-diff.md`: runs the project rules command in step 1, takes the spec folders from it, applies the project rules in step 4, searches callers outside the diff in step 5, checks each finding again in step 7, and runs `review_check.py` in step 9. The reviewer writes the gate result it was given and does not run the gate.
- `references/review-output.md`: new section `Nguồn và độ phủ` with `Luật đã đọc:`, `Cổng:`, and `Độ phủ:`.
- `SKILL.md`: the author runs the project rules command before the first edit. The hand-off holds the gate result and an approved design file, and still no author notes.
- `scripts/fe-gate.py`: the review context carries the full project rules command. A repo with `.fe-kit/config.yaml` also gets the author command on a frontend prompt and after compact.
- `references/review-checks.md` F23: a component declared inside another component. `references/audit.md` Operational flow: two tabs on one record, and Enter on a search form. `REVIEW_CHECKLIST.md` C8 covers callers outside the diff.
- `agents/reviewer.md`: `model: opus`. Bash runs only the two scripts and reads.
- `fix-bug.md` step 8 runs each `gate:` command.
- New `scripts/review_packages.py`: `split` cuts a diff of more than 10 files into packages of at most 15, one folder per package when it fits, one reviewer per package. `merge` joins the package reports without judgement: the worst verdict, every finding, summed counts, the union of rules read. On JTEK commit `7d23c85f6`, 24 files gave 2 packages (14 and 10).
- New `scripts/review_record.py`: `save` keeps the report and the reviewed sha in `.fe-kit/reviews/<branch>.md`. `last` prints that sha and each old finding, so the next review reads `<sha>..HEAD` and checks each old finding again. `review-diff.md` step 4 reports an old finding that still holds.
- `review_check.py`: `sections()` and `label_value()` are public, because `review_packages.py` and `review_record.py` call them.
- One copy per rule. `SKILL.md` lost the Hard Rule and the Common Mistakes row that repeated `rules/review-diff.md`, and its edit-gate paragraph that repeated `rules/fe-implementation.md`. The four authoring playbooks replace their gate paragraph with one line that names the labels and points at `rules/fe-implementation.md`. New `scripts/test_rule_copies.py` fails when a sentence of 8 or more words from `rules/*.md` appears in a skill file, or one from `SKILL.md` appears in a playbook. `CHANGELOG.md` and `evals/` are not checked, because they quote old rules as history.
- `scripts/bash_target.py` is unchanged. Running a test suite (`node --test extensions/fe-gate.test.ts`, `python3 scripts/test_fe_gate.py`) is still gated as a frontend write, because the gate reads script text and cannot tell test data from a real write. Three fixes that read script text more closely each let a real write through, as three independent reviews showed. The fix that measures the change instead (which frontend files a Bash command changed) is planned for 1.24.0. Until then, declare the labels with one `echo` before a test run.
- `scripts/yaml_subset.py`: an error for an unquoted value names the quoted value to write, as in `write "**/x.ts"`.
- Version 1.23.0 in `plugin.json`, `package.json`, and both places in `marketplace.json`. New `scripts/test_versions.py` fails when one differs, or when the first CHANGELOG heading differs.
- An independent review before commit found 12 defects in the new scripts; each fix has a test that fails on the code before it:
  - `project_config.py` refused `--files` with `--diff`, so a package reviewer dropped every project rule. The three CLIs now share `add_source_arguments()` and `files_from_args()`; `--files` with `--diff` keeps one package of the range;
  - `project_config.py` lists paths with `git -c core.quotepath=off` and `diff --relative`, so a non-ASCII name and a sub-folder root match their globs; a path on another drive exits 2 with a message; `.fe-kit/reviews/**` is never a file to review;
  - `review_record.py save` recorded the parent of the reviewed work. It now refuses while files are not committed (`--allow-dirty` to force). Branch names are percent-encoded, so `feat/x` and `feat-x` keep separate records; a detached HEAD asks for `--branch`;
  - `review_check.py` crashed on a line of a deleted file (now a `!` warning), warned on old-system and CR quotes (`legacy.source` and the `legacy.cr` folder are now known roots), and let one bare file name cover two diff files;
  - `review_packages.py split --max 0` looped forever;
  - `yaml_subset.py` read `tRUE`, `NuLL`, `0777`, and `[src/{x,y}/**]` differently from PyYAML, and its tab check never ran;
  - `review-diff.md` step 1 now reads untracked files too, and passes the package `--files` to the project rules command.
- A second independent review found 7 more defects, fixed with tests:
  - a re-review after `save` used `<sha>..HEAD`, which misses uncommitted work. `--diff <sha>` with no `..` now compares that sha with the working tree, new files included, and SKILL.md passes it;
  - `review_check.py` rejected a citation of a built-in preset rule (`presets/legacy-rewrite/review.md:8`). A cited path now also resolves against each `read:` file;
  - `project_config.py` printed no file list, so the reviewer could not see untracked files. Each file to review now has a `file:` line;
  - `legacy.source: dev` or `./dev/` was not a known folder; config folders are normalized;
  - `review_record.py save` on a sub-folder root counted its own record and files outside the root as uncommitted;
  - the `yaml_subset.py` docstring claimed full agreement with PyYAML; it now names the types that differ (floats, dates, hex);
  - SKILL.md now says to pass `--branch` on a detached HEAD.
- A third independent review found 3 more, fixed with tests:
  - `review_check.py` split a covered file name at a space, so `sp ace.ts` could never be covered; names are now matched whole, so `OrderForm.ts` also no longer covers `OrderForm.tsx`;
  - a renamed file was listed only under its new name, so a citation of the old name failed. `git diff --no-renames` lists both; a name with no file on disk is not required in `Độ phủ`;
  - SKILL.md said the next review reads only commits; it reads the working tree too.
- Tests: `scripts/test_fe_gate.py` runs 191 cases (4 new). New `test_yaml_subset.py` (52, compared with PyYAML when installed), `test_project_config.py` (53), `test_review_check.py` (25), `test_review_packages.py` (19), `test_review_record.py` (15), `test_rule_copies.py`, `test_versions.py` (5). Each new suite failed on a negative control. `evals.json` has 3 new evals (21–23).
- JTEK pilot: a `.fe-kit/config.yaml` that mirrors the FE part of `workflow/lenses/paths.yaml`. On commits `7d23c85f6`, `14bc719f7`, and `c9e8b60be`, `project_config.py` printed the same FE files, rule files, and lenses as `bin/ai/review-scope <sha> --side fe`, plus `CARD.md`. A `fe-kit:reviewer` run on `14bc719f7` with the new playbook read 14 rule files, preset included, and reported two findings that quote `tvmk_admin/rules/6-forms.md:20` and `:32`. The 1.22.0 reviewer reads neither file. Its first `review_check.py` run gave 2 `!` warnings, and the second run exited 0 after it removed those references.

## 1.22.0

The gate read labels from two sources: the `echo` declaration and the reply text in the transcript. The host can write the reply text after the PreToolUse hook reads the transcript, so the same labels could pass or fail. The deny message also gave two paths: it started with the `echo` command, then asked for reply-text lines in ten more sentences.

- `scripts/fe-gate.py`: new `declared_only()`. When the payload has `session_id`, labels that Claude writes count only from an `echo` declaration. Text the user typed and a compact summary still count. A payload with no `session_id` keeps the reply-text path.
- With `session_id`, a deny does not wait for a late transcript write.
- `decisions_found()` reads the declared labels also when the payload has no `transcript_path`.
- The deny message has one path: the `echo` command, the missing labels, and one sentence that says the reply text does not count.
- `rules/fe-implementation.md`, `skills/fe-kit/SKILL.md`, the playbooks, `README.md`, and `CODEMAP.md` say that the gate does not read reply-text labels.
- Tests: `scripts/test_fe_gate.py` runs 187 cases (9 new, 7 of them fail on 1.21.1). `extensions/fe-gate.test.ts` runs 30 cases (1 new).

## 1.21.1

The gate read every user entry as a new request, also the entries the host writes: a `<task-notification>` when a background task or a subagent ends, and `/export` with its `<local-command-stdout>`. Each one dropped the labels of the current request. In a DA1020 session the reviewer notification came in while the agent worked, and the edit after it was denied.

- `scripts/fe-gate.py`: `typed_by_person()` skips a user entry whose `origin.kind` is not `human`, or whose text starts with `<task-notification>`, `<command-name>`, `<command-message>`, `<command-args>`, `<local-command-stdout>`, or `<local-command-stderr>`. Such an entry does not start a request, and labels inside it do not count. This also keeps an echo declaration of 1.21.0 valid after a notification.
- Replay of that session: the transcript cut after the notification is denied at 1.21.0 and allowed now.
- Tests: `scripts/test_fe_gate.py` runs 178 cases (6 new).

## 1.21.0

In 105 gate denials across the JTEK sessions, 82 were repeats inside one request, and 68 of those had no new reply text before the retry. The agent wrote its labels in a thinking block, which the transcript keeps empty, or not at all. In 4 to 5 cases the labels were in the reply text but the transcript did not have them yet when the hook read it. The rules that the hook injects did not name the label format, so every request got at least one denial.

- New `scripts/label_store.py`: one plain `echo` or `printf` Bash command with `Runtime owner:`, `Decision:`, `Trigger:`, `Expected:`, or `Actual:` is a declaration. A pipe, a redirect, a chain, or a substitution is not. The labels are saved under the session id, or the transcript path when the host sends no id, plus the agent id and the latest request.
- `scripts/fe-gate.py` allows a declaration and saves it, then reads the saved labels next to the transcript. Labels of an earlier request do not count. A subagent also sees the main agent's labels. A value that starts with `<` is a placeholder and does not count.
- The deny message starts with the `echo` command to run, with the file name filled in. Reply-text labels still count.
- `extensions/fe-gate.ts` sends `session_id` from `ctx.sessionManager.getSessionId()`, because it writes a new transcript file on every call.
- `rules/fe-implementation.md` and `skills/fe-kit/SKILL.md` name the label format and the declaration command.
- Tests: `scripts/test_fe_gate.py` runs 172 cases (20 new). `extensions/fe-gate.test.ts` runs 29 cases (1 new).

## 1.20.0

A new request ("đổi đi và liệt kê…") dropped the labels of the earlier request. The agent then named the owner only in prose and in a thinking summary, so the gate denied two Edit calls. The agent wrote the file with `git show … | sed … > file.tsx` instead, and Bash was not gated.

- `hooks/hooks.json`: the PreToolUse matcher adds `Bash`.
- New `scripts/bash_target.py`: `write_target()` finds a frontend file that a Bash command writes: a `>`/`>>` redirect, `tee`, `cp`/`mv` onto the file, `sed -i`/`perl -i`, or the path argument of `writeFileSync`, `writeFile(`, `appendFileSync`, `write_text(`, or `open(…, 'w')`. A script that reads `src/A.tsx` and writes `out.json` is not a target.
  - A variable set in the same command is expanded, as in `F=src/A.tsx; echo x > "$F"`.
  - A script file the command runs (`node "$S"`, `python x.py`) is read from disk and checked the same way.
  - A write to a path built at run time (`writeFileSync(f, …)`, `sed -i … "$f"`) counts when the text names a frontend extension, as in `endsWith('.tsx')`.
  - A relative path resolves against the last `cd` before it. A target under `tmp`, `temp`, or `scratchpad` stays open, so `cd "$SP"; sed -i … check.js` is not gated.
- `scripts/fe-gate.py` gates that command like `Write` on the file. A Bash command that writes no frontend file exits at once and injects nothing.
- The deny message now says that prose and a thinking summary do not count, that the label, a colon, and the value go on one line, and that labels written before the latest user message do not count. A Bash deny adds that Bash is gated like Edit.
- `extensions/fe-gate.ts`: on Windows the extension spawned `fe-gate.sh` directly, which failed, so the gate always passed (9 of 25 tests failed on Windows). It now runs `sh` with a forward-slash path, because `fe-gate.sh` finds its folder with `${0%/*}`. The omp `bash` tool call is gated through the same `Bash` payload. An allowed bash call leaves the status line as it is.
- Replay of a real 165-command session: 8 commands denied, each one a write to a repo frontend file. No scratchpad script was denied.
- Tests: `scripts/test_fe_gate.py` runs 152 cases (28 new). `extensions/fe-gate.test.ts` runs 28 cases (3 new) and passes on Windows.

## 1.19.0

The wording exemption was line based, so it blocked pure copy on a JSX text line and let behavior changes through after an apostrophe, an import path, or a string constant.

- New `scripts/wording.py`: a stdlib JS/TS/JSX lexer and token diff. An edit is exempt only when every changed token is JSX text, a whitelisted text attribute, a copy call/property/constant, a class/style sink, or a comment. An import source, endpoint, enum value, route, storage key, config constant, condition, or call is code and stays gated. Multi-line copy and `MultiEdit` are exempt; `Write` and a path-only `ast_edit` stay gated.
- `scripts/fe-gate.py` deletes `behaviorless_one_line()`, `code_skeleton()`, `string_tail_skeleton()`, `class_list_line()`, `RISKY_RE`, `JSX_TEXT_RE`, `OPEN_STRING_RE`, and the other line regexes. `wording_exempt()` reads the file, applies the edit in memory, and calls the token diff. `FE_GATE_WORDING=off` is a kill switch. Conflict resolution keeps `conflict_lines_only()` and a token-subset merge check.
- The gate now covers `.js`, `.mjs`, `.cjs`, `.astro`, and `.mdx` in addition to `.tsx`, `.jsx`, `.vue`, and `.svelte`. Phase 1 gates `.vue`, `.svelte`, `.astro`, and `.mdx` without a wording exemption. `.ts` stays out.
- `Decision:` must carry the decision word immediately after the colon. `Decision: do not reuse` and `Decision: no shared` no longer count. `Runtime owner:` rejects `TBD`, `TODO`, `N/A`, `-`, and similar placeholders. A table row is skipped before both checks.
- Request scope: any user message that is not a continuation (`ok`, `làm đi`, `tiếp tục`, an interrupt) starts a new task, so labels for an earlier task cannot open a later one.
- Bug mode: a wording prompt (`text`, `copy`, `label`, `chính tả`) or a meta prompt (`fe-kit`, `plugin`) no longer asks for repro fields unless a strong symptom is present. The same wording words stop the reuse bundle from loading on `sửa text` and `sửa copy`.
- `extensions/fe-gate.ts` accepts the edit key names omp and other hosts use: `old_string`/`new_string`, `oldText`/`newText`, `oldString`/`newString`, `old_str`/`new_str`, `old`/`new`, and `search`/`replace`. An `edits` array maps to `MultiEdit`; `ast_edit` uses the same pairs instead of always mapping to a path-only `MultiEdit`; `write` forwards `content`. The gate timeout rises from 10 s to 15 s to cover the token diff on a large file.
- Tests: `scripts/test_wording.py` runs 78 lexer/diff cases. `scripts/test_fe_gate.py` runs 124 cases and takes about 4 s with `FE_GATE_NO_FLUSH=1`. `extensions/fe-gate.test.ts` runs 25 cases. The black-box repro suite covers 22 cases, including the old false allows.

## 1.18.0

A bug fix left a field blank where it used to hold a default. Another flow filled that field only when it was blank, and the new code had no such fill. The fix re-ran only its own reproduction, so the second bug shipped with it.

- `playbooks/fix-bug.md` adds step 6, "Check the impact of the fix". When a fix gives a field a new value (a blank, `0`, `null`, a removed or an added default), name the field and the value. Search every writer and reader of the field, and for a rewrite every old-system event that reads or fills it. Write an `Impact:` list with one line for each flow. A fix that gives no field a new value says so in one line.
- The unit-test step is now step 7, and Verify is step 8. Verify also runs each `Impact:` flow, and a flow that was not run is named with its reason. Step 3 points `tdd` at step 7.
- `skills/ut-report/SKILL.md` adds required case 8, "Giá trị mới do bản fix tạo ra": for each fixed bug, each flow that writes or reads the field with the new value gets a case.

## 1.17.1

A prompt that named fe-kit got no rule injection and no badge, because the intent regex only knew frontend words and the "review diff" phrasing.

- `scripts/fe-gate.py` `prompt_hit` also matches `fe-kit`, `fe kit`, and `skill://fe-kit`. A prompt that names the plugin now injects the rules, and the status badge shows `⚡ rules` on omp.
- `scripts/test_fe_gate.py` adds two cases: a Vietnamese prompt naming fe-kit, and one naming `skill://fe-kit`.

## 1.17.0

The gate answered every edit, but the session showed nothing, so a blocked edit scrolled away and left no trace.

- `extensions/fe-gate.ts` writes the last verdict to the omp status line: `✓ ok`, `⛔ blocked`, `✎ note`, and `⚡ rules` when the prompt matches an intent the gate knows. `session_start` resets the badge.
- `before_agent_start` runs the gate's `UserPromptSubmit` branch for its reply only. The rules are always-on on omp, so nothing new is injected; the badge is the signal that a review, reuse, or conflict prompt matched.
- A theme lookup that throws, or a missing `setStatus`, never fails a prompt or an edit.
- `extensions/fe-gate.test.ts` runs 14 cases: six verdict cases, the two prompt cases, and the eight edit and post-edit cases from 1.16.0.

## 1.16.0

omp loaded the rules but not the gate, so an edit without an owner went through. The gate now runs on both hosts from one script.

- New `extensions/fe-gate.ts`, declared in `package.json` under `omp.extensions`. On `tool_call` for `edit`, `write`, or `ast_edit` it maps the call to the Claude hook payload, runs `scripts/fe-gate.sh`, and blocks with the gate's own reason when `Runtime owner:` or `Decision:` (and the bug labels on a bug fix) are missing. Nested tool calls and other tools are untouched.
- On `tool_result` the same extension runs the post-edit checks: conflict markers left in the file and a failing `<repo>/.claude/rules.sh` become an error in the tool result, and a bug edit gets the unit-test instruction as extra context.
- The transcript it hands the gate is the omp session mapped to the shape `scripts/fe-gate.py` reads. A gate that errors, times out after 10s, or prints nothing fails open, as the hooks do.
- `extensions/fe-gate.test.ts` runs eight cases against the real script with `node --test`.
- Checked on a real omp session: two denies, the agent writes `Runtime owner:` and `Decision:` in the reply text, the third edit passes, and the file changes only then.

## 1.13.0

The rules placed code at the right layer and told the agent not to add a file for a small difference, so a second job went into a file that already had one. Nothing ever said to split by job.

- New `rules/modules.md`, always applied. A file and a folder do one job. A different job is a new file in the owning feature with one call left in the old file. Folders follow the feature or the domain, not the kind of file. Export only what a caller uses. A file outside a folder imports one file in the folder, and no `index.ts` re-exports the folder. A bug fix does not split files, and file length alone does not split one: past 200 lines, name the job and look for a second one.
- `rules/reuse-duplication.md` narrows its blocking sentence: a small difference in the same job is not a new file, and a different job is, per `rules/modules.md`.
- `scripts/fe-gate.py` injects `rules/modules.md` with the reuse rule on a code prompt, on an edit of a source file, after compact, and `PreCompact` tells the summary to keep it.
- `references/review-checks.md` F22 and `references/REVIEW_CHECKLIST.md` D9 fail a diff that writes a second job into an edited file, enters a folder through a second entry, splits a file only because it is long, or splits while fixing a bug.
- `references/audit.md` Architecture names two jobs in one file as `rules/modules.md` and keeps a long single-job file whole.
- `playbooks/new-ui.md` and `playbooks/refactor-ui.md` point at the rule. `SKILL.md` gains the matching Hard Rule.

## 1.12.0

Matt Pocock's skills run inside fe-kit instead of beside it.

- `references/external.md` gains Matt Pocock rows: `diagnosing-bugs` for a bug that will not reproduce, `tdd` for test-first work, `codebase-design` and `improve-codebase-architecture` for the Architecture and Audit lenses, `domain-modeling` for a term or rule named two ways, `grill-with-docs` when the Architecture or Reuse Decision cannot be filled, `prototype` for a state or layout question, and `research` for a fact from primary sources. Fetch is `npx skills add mattpocock/skills --skill <name>` from a temp dir.
- A matched skill is a subroutine of the playbook step: its result folds into this skill's template or report. It does not emit its own report, handoff, or ticket flow, and `setup-matt-pocock-skills` never runs.
- `code-review`, `implement`, `implement-spec`, `to-spec`, `to-tickets`, `triage`, and `wayfinder` are never opened from this plugin. The fresh reviewer owns a diff, and issue-tracker orchestration stays outside a frontend task.
- `playbooks/review-diff.md` finds a local spec file before it grades scope. The order is a path or issue number in a commit message that names a file under `docs/`, `specs/`, or `.scratch/`, then a path the task names, then a file there whose name matches the branch or the feature. F20 writes a missing, extra, or wrong requirement into `references/review-output.md`. No second report. No issue-tracker fetch.
- F21 compares a new name with `GLOSSARY.md`, `CONTEXT.md`, or the file `GLOSSARY-MAP.md` names. No glossary file is not a finding. The Architecture lens in `references/audit.md` adds judgement-only smells for a screen review. A diff review does not score them. A review does not write a glossary, an ADR, or an HTML file.
- `playbooks/fix-bug.md` step 3 reads `references/external.md`: `diagnosing-bugs` runs inside the reproduce and root-cause steps, and `tdd` runs inside the unit-test step.

## 1.11.0

Two skills that lived as personal skills join the plugin, so every install gets them.

- `skills/ui-image-check`: compare one UI image with the code, item by item, with `file:line`, then with a screenshot of the running screen. It does not edit code.
- `skills/ut-report`: write the developer UT report of one screen (old system against new system) to `.xlsx`. `scripts/build_report.py` builds the file from YAML. The script output is the same as the personal copy: a compare of every cell on a real case file found no difference.
- Project names, internal links, a tester name, and screen IDs in the examples are now placeholders, because the repository is public.
- The UT script path is now `scripts/build_report.py` in the skill directory, not a path under `~/.claude/skills`.
- `ut-report` gains "Case bắt buộc từ lỗi đã lọt qua UT": seven case kinds taken from defects that UT missed and integration test found. They are load defaults with their condition, the text of a code label, a check on raw typed text, a derived field when its input is cleared, a switch of scope or record, the form of a message (alert or inline), and an old branch that tells data shapes apart. A bug the tester reported is a case too, with `NG -> OK` after a re-run.

## 1.10.5

A rewritten screen ported an old check: `length === 2 ? lookup : show as stored`. The old field held a code or its label, so the check told them apart. The new field holds only the code, so the check had nothing to tell apart. Review did not catch it, because the comment named the old line but not why the old system needs it. A run of both systems showed the same status text with and without the check.

Integration test of the same rewritten screen found seven more defects. Each one is a rule the authoring steps did not state:

- A check on the first typed character never failed, because the shared field rule trimmed the text first. The old screen tested the raw value.
- Two boxes stayed blank after the first save, because two load defaults of the old screen were not ported. The first fix set them on every load. A second fix added the old condition.
- A status showed its name only. The old master loader builds code, separator, and name.
- A derived checkbox stayed on after the user cleared its input. The rule returned `null` for a blank input, and the caller skipped the update. The CR named only the filled cases.
- Leaving the all-records view for one record kept the all-records defaults. A guard compared only the record key.
- A one-time completion alert became a block that stayed on screen, because the project rule sends every result to that block.

Changes:

- `code-quality.md` Design and behavior: port the behavior of the old screen, not the way it stored data. Write why the old system needs a branch before you port it. Port each load default with its condition. Take a code label from the old loader. Run a check on the raw typed text before any normalizer. Keep a one-time alert as a dialog, and name a conflict with a project rule.
- `code-quality.md` Field updates: a derived field updates for a cleared input too. A switch of record or scope resets the values and defaults of the old scope, and a "same key" guard also compares the mode.
- `review-checks.md` F18 covers behavior ported from the old system. F19 covers a derived field and a switch of record or scope. `README.md` and `evals.json` now say F1 through F19.

## 1.10.4

The gate denied an edit after the agent wrote `Runtime owner:` and `Decision:` in the reply text, just before the edit call. The same text passed 31 seconds later with no new line. Claude Code can write the current reply text to the transcript after the PreToolUse hook reads it.

- Before a deny, the gate reads the transcript again, up to 10 times, 0.3 seconds apart. An allowed edit has no wait. A deny takes about 3 seconds more.
- A label can be bold or italic with the colon outside, as in `**Decision**: extend` or `_Runtime owner_: OrderForm`. Before, only `**Decision:**` counted.
- Labels and decision words ignore case: `Runtime Owner:`, `Reuse decision:`, `Decision: N/A`, `Decision: Extend`, and `actual:` count. The template lines in SKILL.md (an empty value, or decisions joined by `|`) still do not count.

A second session denied 8 edits during a `git stash apply` conflict. The agent wrote its plan only in thinking, which the terminal shows as a summary line, so it believed it had replied. The user wrote `đang lỗi`, so the gate also asked for `Trigger:`, `Expected:`, and `Actual:`.

- An Edit whose old text has conflict markers is exempt when every non-blank line of the new text is already in the conflict block (indentation ignored) and the new text has no marker. Such an edit only keeps, drops, or reorders lines. A line that is not in the block, such as a new wrapper call, is still gated.
- An Edit whose old text has conflict markers does not need `Trigger:`, `Expected:`, and `Actual:`. A merge is not a bug fix.
- The gate also reads the thinking text that the transcript keeps. The 1.10.3 note said the transcript keeps no thinking text. That is wrong: it keeps the summary the user sees. Empty or redacted thinking still does not count, so the playbooks still say to write the lines in the reply text.
- A conflict Edit that writes one line not copied from either side is exempt only when every word and every risky token in that line is already in the conflict block. A merged class string passes. A new call such as `toHalf(2)`, or a new `??`, is gated.
- A one-line Edit outside a conflict is exempt only when the code outside strings, JSX text, and comments does not change. A class or wording change passes. A new call, a new handler, or a changed value such as `limit={10}` to `limit={20}` is gated. Also exempt: an import or export list, a comment line, and a line inside a class string that spans lines (`h-14.5 min-h-14.5`, `px-3 text-primary">`). An object key with a flag or number (`open: true,`) is not a class line and stays gated.
- Labels count from the latest request on. A request is a user message that asks for new work or reports a bug. `ok`, `làm đi`, and an interrupt do not start a new request, so labels written before them still count. Before, labels written once opened every later edit in the session.
- A compact summary is not a request and does not turn on bug mode. The text before the summary stays in the same transcript, so labels written before `/compact` still count.
- Inside a subagent, the hook payload names the main transcript. A test showed that a subagent edit passed on labels written only in the main session. When the payload has `agent_id` or `agent_transcript_path`, the gate also reads `<session>/subagents/agent-<id>.jsonl`, so labels the subagent writes count. Whether the payload has `agent_id` is not verified.
- Under a `Reuse Decision` heading, any label can carry the decision, as in `- FE side: **reuse**`. An agent wrote its owner and decision that way and was denied 7 times. A decision word under another heading, or the template line with `|`, still does not count.
- The deny message names what is missing after the latest request, for example `` `Decision:` with reuse, extend, feature-local, shared, or n/a ``. It also says that reply text written earlier in the turn counts, and that the agent should write the lines and retry in the same turn. An agent believed that text written mid-turn is not saved, ended the turn, and asked the user to type "tiếp tục".
- `scripts/test_fe_gate.py` runs 94 cases: label formats, bug mode, request scope, compact, one-line edits, conflicts, file types, a subagent, a late transcript write, and a Vietnamese prompt. Run `python scripts/test_fe_gate.py`. The exit code is the number of failures.
- A replay of 1,338 view-file edits from local transcripts compared this gate with 1.10.2. 138 edits that 1.10.2 denied now pass: 124 had real labels in a format 1.10.2 missed, and 14 are conflict resolutions. 60 edits that 1.10.2 passed as one-line now need labels. 58 of them change a call, a condition, a prop, or a value. 2 are class-only lines that the check cannot read: a class list cut after `hover:`, and `marker:content-['…']` with quotes inside the class.
- `tổng sai`, `tính sai`, `hiển thị sai`, and `bị sai` now mark a bug report. `sai` alone does not, so `sai chính tả` stays a wording fix.
- On Windows, Python read the hook payload as cp1252, so a Vietnamese prompt such as `đang lỗi màn hình trắng` or `thêm cột` matched no rule and injected nothing. The gate now decodes stdin as UTF-8.
- A conflict resolution that replaces a marker block (`<<<<<<<`, `=======`, `>>>>>>>`, `|||||||`) with one line counts as a one-line edit. It is exempt when the new line adds no risky token (`??`, `||`, `&&`, `if (`, `=>`, a hook, `await`, `fetch`, `catch`) that the two sides did not already have. Marker lines do not count as code in that check. A resolution with two or more lines, or a line that keeps a marker, is still gated.

## 1.10.3

An agent retried a blocked edit ten times. It wrote `Runtime owner:` and `Decision:` only in thinking. The transcript keeps no thinking text, so the gate never saw the lines.

- The deny message says where to write the lines: in the reply text, one line each, before the edit call. It says that thinking and a table row do not count.
- The playbooks and SKILL.md say the same.
- A value can start with a backquote after a space, as in `` Runtime owner: `OrderForm` ``. `` Decision: `extend` `` and `Decision: **extend**` also count. A backquote right after the colon is still prose that names the field.
- `Decision:` counts when one decision word is anywhere on the line, as in `Decision: mở rộng (extend)`. A line with `|` still does not count.
- The full-width colon `：` counts the same as `:`.
- In text the user typed, a value can be on the next line, as in `Actual:` and then the value below it. `Step:` counts as `Trigger:`. `Expected` with no colon at the end of a line also counts. The agent still writes each value on the same line.
- The latest request decides bug mode. A message such as `làm đi` keeps an earlier bug report. A request for new work (`add`, `thêm`, `viết`) ends it. Before, one bug word anywhere in the session gated every later edit.

## 1.10.2

The 1.10.1 gate read text that no person wrote.

- Every session counted as a bug fix. The bug check read tool output, `<system-reminder>` text such as a global CLAUDE.md with `bug cause`, and the hook's own deny message. The check now reads only text the user typed.
- Reading `playbooks/fix-bug.md` filled the gate. Prose such as `` `Trigger:`, `Expected:` `` and the deny message `Trigger:, Expected:` matched as a value. The gate now reads only text the user typed or the agent wrote, without the deny message. A value cannot start with `,` or `` ` ``.
- The owner and decision lines follow the same source rule.

## 1.10.1

Bug-fix work that landed after 1.10.0. 1.10.0 already used F13–F15, so the new review rows are F16 and F17.

- `playbooks/fix-bug.md`: reproduce with `Trigger:`, `Expected:`, and `Actual:` before an edit. Fix at the owner. Write the unit test in the owner's existing test file. A text check includes `undefined`, `null`, `""`, a leading space, and a trailing space. The failing case must fail on the old code.
- `review-checks.md` F16: a new check that lets `undefined`, `null`, `""`, or `"ABC "` through fails. F17: a bug fix with no unit test for that case fails.
- The hook denies a view edit until owner, decision, and the three reproduce lines are filled. After the edit it names the unit test and the reviewer handoff. `trung tâm` and a typo prompt do not inject the reuse rule.

## 1.10.0

Lessons from a reviewer's plan to restructure a large form screen without a change in behavior.

- `code-quality.md` Names: a behavior hook starts with a verb. Do not rename a name that is not wrong. Rename a name a reader can confuse with an existing export.
- `code-quality.md` Helpers: search the shared lib for a function with no business term. Move it there only with a second consumer or a project rule. `helpers/` holds pure functions only. A grab-bag `*-format.ts` and a dead parameter are findings.
- `code-quality.md` Files: one kind of code per sub-folder, search params in `schemas/`, tiny constant files merged, relative imports inside a screen, new conventions written to the project rule file.
- `code-quality.md` gains a `Form screens` heading: split by visible block with `-panel`, `-section`, `-operation-panel`; each block owns its fields, popup, and dependent updates; the parent form only composes; one lookup hook per master that does not open UI and guards a late response; no `setValue` in JSX.
- `code-quality.md` Verify: walk every lookup button on a production build. Record React Profiler before and after a render claim.
- `performance.md`: state and `useWatch` in the smallest block, catalog hooks in the block that read the prefetched cache, `useCallback` on a hook function used as an effect dependency.
- `review-checks.md`: F13 large form, F14 `setValue` and layers, F15 renames and hook names.
- SKILL.md gains the `Form screens` row, and matching Hard Rules and Common Mistakes rows.
- `reuse.md` no longer says PascalCase files and `useXxx.ts`. File names follow the project rule, else kebab-case, as in `code-quality.md`. A shared `types.ts` needs two consumers.

## 1.9.9

A bug fix could finish with no unit test. Step 5 said to leave a regression check, and allowed skipping it.

- `playbooks/fix-bug.md` now says where the test file goes, what it must call, and which cases it must include. A text check includes `undefined`, `null`, `""`, a leading space, and a trailing space. The failing case must fail on the old code. Skip the file only when the repo has no test runner.
- `review-checks.md` gains the bug-fix unit test row (F17 after 1.10.0). A bug fix with no such test fails review.
- After a bug-fix edit, the hook names that test instead of only saying to re-run the reproduction.

## 1.9.8

Five holes left after the bug-fix playbook. A notification prompt injected the reuse rule, a typo prompt did too, a filled decision skipped reproduction, and the hook said nothing after the edit.

- `trung` no longer matches `trung tâm`. A wording prompt (`typo`, chính tả, button label) does not inject the reuse rule.
- A bug-fix edit of a view file is denied until the transcript has `Trigger:`, `Expected:`, and `Actual:`, each with a value, plus the existing owner and decision lines.
- After that edit, the hook says to re-run the reproduction and hand the diff to the reviewer. It does not run the project's tests.
- D8 and F7 point at `rules/reuse-duplication.md` instead of restating a second holder rule.

## 1.9.7

A bug fix had no playbook, and the hook gate only stopped a new `.tsx` or `.vue` file. A fix could edit an existing component, patch the symptom where the value is shown, add a fallback that hides the cause, and finish with no reproduction and no test. Empty `Runtime owner:` and `Reuse Decision` headings also opened the gate, and a missing transcript passed it.

- New `playbooks/fix-bug.md`, routed from `SKILL.md`: reproduce first, root cause at its owner, smallest fix with no mixed refactor and no silent fallback, a regression check, and a reported verify run. A symptom report with no fix verb (`Tổng sai khi có discount`) is a bug fix.
- `rules/fe-implementation.md` defines one-line by behavior: a change that alters runtime behavior is never one-line, however few lines it touches. `rules/reuse-duplication.md` and `rules/review-diff.md` point at that one definition.
- The second-holder rule now lives only in `rules/reuse-duplication.md`. The copies in `SKILL.md` and `references/code-quality.md` are gone or point at it. Naming the holder checked is not enough: name the literal or behavior searched.
- `scripts/fe-gate.py`: creating or editing a `.tsx`, `.jsx`, `.vue`, or `.svelte` file is denied until the transcript names a `Runtime owner:` value and a `Decision:` of `reuse`, `extend`, `feature-local`, `shared`, or `n/a`. Empty headings and the template line do not count. A missing or unreadable transcript denies. A symptom prompt with no fix verb injects the implementation and reuse rules. Only a behaviorless one-line Edit is exempt.

## 1.9.6

A review of the helper ran and wrote that it could ship. The checklist had the case, but the review never applied `undefined`, `null`, or `""` to the check. Walking items in your head is not applying them.

- `playbooks/review-diff.md`: a new or changed check must be applied to `undefined`, `null`, `""`, `" ABC"`, and `"ABC "` before the verdict. A value with no error is a finding. "Đưa được" is not allowed if those inputs were not applied.
- `review-checks.md` gains the check row (F16 after 1.10.0), on the short table the reviewer walks, not only in the long checklist.
- The reader report cannot say "Đưa được" without the result of `undefined`, `null`, and `""`.

## 1.9.5

The original helper `(values[field] ?? '').startsWith(' ')` still passed review. TY7 only failed a case the message already named, and TY8 was N/A when no schema existed. `""` and `undefined` produced no error.

- That helper is a finding even with no schema and even when the message only names a leading space. `undefined`, `null`, and `""` become `''`, and `''.startsWith(' ')` is false.
- TY7 now names `undefined` and `null`. TY9 fails the helper when those three values produce no error. It does not wait for a schema or for the message to mention empty.

## 1.9.4

A bug fix could add `useState`, a prop, or a variable for a value that already existed. The reuse rule only searched before a new function, hook, type, constant, validation, fetch, or handler.

- `rules/reuse-duplication.md` now includes state, props, and variables. A bug fix that adds one must name the holder that already has that value and read it or write into it. A second holder is a finding. A one-line wording fix still skips the search.
- `REVIEW_CHECKLIST.md` gains D8. `review-checks.md` F7 covers a new state or variable, not only a repeated prop.
- The Claude hook injects the reuse rule when the prompt says fix, sửa, or bug.

## 1.9.3

A screen that already had a validator still grew a helper that reimplemented the check.

- Use the validator the project already has: the schema, the resolver, or the shared field rule. Do not add a function that filters fields, calls `safeParse`, or wraps `min`, `trim`, or `startsWith`.
- If no validator exists, keep one table or one schema at the owner. Do not add a helper beside it. Do not require a new library.
- `REVIEW_CHECKLIST.md` gains TY8. A helper next to an existing validator fails. No existing tool is N/A.

## 1.9.2

1.9.1 said not to demand a schema. A check could still pass a case its message rejects, and the review had nothing to fail.

- `code-quality.md`: judge the cases, not the library. Do not require a schema. `startsWith(' ')` is not the rule "no empty, no space at either end", because `""` and `"ABC "` pass. The message and the predicate must name the same cases. A library type error is not the empty message.
- `REVIEW_CHECKLIST.md` TY6 no longer reads as a pass for every typed form check. TY7 fails a check that lets a forbidden case through. It does not name a library.
- SKILL.md: the hard rule and one Common Mistakes row match.

## 1.9.1

A diff review had no rule for a hand-written validation check, so it could only guess whether the change needed a schema.

- `code-quality.md` Types and schemas: a `[field, code]` check table is the one list, and a schema over it is a second list every new field must join. A schema is for parsing untrusted input: the parsed value, the inferred type, the shape guarantee. A check over values the form already typed needs none of the three.
- `(values[field] ?? '')` turns an absent required field into a pass with no message: fail on absence instead.
- One code per field is the table's limit, and `filter` then `map` reports the first rule only.
- Narrow to a string before `startsWith`, `trim`, or `toUpperCase`; type the field slot against `keyof Values` and the code slot against the message-key union.
- `REVIEW_CHECKLIST.md` gains TY6: a hand-written check that repeats a rule the schema already holds, or that counts a missing required field as valid, fails. A check on typed values that only builds form messages passes, and the reviewer does not ask for a schema.
- SKILL.md gains the matching Hard Rule and two Common Mistakes rows.
- One eval case asks the zod question about a real `[field, code]` helper.

## 1.9.0

Rules were prose, so a long refactor forgot them after compact, and the author graded the diff just written.

- `rules/review-diff.md` is always applied. The author does not grade a frontend diff. Claude Code hands it to agent `fe-kit:reviewer`. omp uses a fresh context and `skill://fe-kit/playbooks/review-diff.md`.
- `playbooks/review-diff.md` and `references/review-checks.md` are that review. Each item is `PASS`, `FAIL`, or `N/A`. A `FAIL` has `path:line`. The author does not write the verdict.
- A screen review still uses `playbooks/review-ui.md`. A diff written in this session does not.
- After compact, the Claude hook re-injects `rules/fe-implementation.md` and the review rule when the transcript shows frontend work. `PreCompact` tells the summary to keep those rules.
- After an edit, the hook exits 2 when conflict markers remain, and when the repo's executable `.claude/rules.sh` fails. A repo with no `rules.sh` is unchanged.
- `scripts/fe-gate.sh` no longer needs `dirname`, and it finds `python3` in `/opt/homebrew/bin`, `/usr/local/bin`, or `/usr/bin` when the PATH is minimal. With no `python3` it exits 0 and writes nothing.
- A consumer `REVIEW_CHECKLIST.md` with filled "Lỗi riêng của repo" rows is walked by the diff reviewer. Empty template rows are not items.
- `references/REVIEW_CHECKLIST.md` is in the skill. A diff review walks every S, C, D, N, E, SEC, P, T, TY, R, and DOC item there. It is not a link to an outside repo, and it is not optional.
- Checklist vẫn đi từng mã khi review, nhưng mã chỉ ở trong đầu. Bản người đọc không copy mã ra.
- Báo cáo người đọc theo `references/review-output.md`: kết luận trước, mỗi lỗi hai câu có `file:dòng` và người dùng mất gì, không có mã checklist.

## 1.8.0

Lessons from a real merge request review where working code was rejected.

- `code-quality.md`: a new prop must do what no existing prop does; overlapping props, unread props, and if/else props are findings; do not rewrite working shared code for one screen. Two helpers for one job, a screen hook that wraps a shared hook, a normalizer outside the field rule, and a second cleanup after the preformatter are findings.
- `code-quality.md` Types and schemas: strict types, shared schemas for dates and options, one name set for response and form, no field declared twice, each label once, required checks as a table, fields in screen order, sibling section order.
- `code-quality.md` Files: page sub-folders follow the page rule, export only what is imported, rules files grouped by data, dead rules and message keys deleted, empty comments deleted. Design and behavior: events in `onChange`, not in effects; no dependence on child order.
- `audit.md`: compare with the exemplar screen; a layout rebuilt in the page; lock and session queries not reused from cache; one error classifier; the form block title is not hidden; each hand-kept field list is an Extension finding.
- `review-ui.md`: the cost sentence says what the user loses, and names the exemplar screen or rule file.
- SKILL.md gains matching Hard Rules and Common Mistakes rows.

## 1.7.7

- The plugin and the skill are named `fe-kit`. Read `skill://fe-kit`. The skill folder is `skills/fe-kit/`.

## 1.7.6

- Review findings are spoken Vietnamese: what is wrong, where, what to do, and what it costs if it stays. Priority is said in words. The report does not end a line with `Mức vừa`, and it does not use `reuse` or `field list` in the sentence the reader sees.

## 1.7.5

- A review report leads with Kết luận, then one sentence per finding. Duplicated statements and data-only repetition keep their own sections. Other findings go under Việc nên làm. Empty sections are omitted. The English sweep table and Audit table are not part of a review.

## 1.7.4

- The review template has Cách viết. Each finding is one short Vietnamese sentence, names `file:dòng` and the code's own name, and says the next step: reuse, collapse the data, or leave it.

## 1.7.3

- A review ends with the Vietnamese template in `playbooks/review-ui.md`: phạm vi, dùng lại, code viết hai lần, chỉ khác dữ liệu, chất lượng, kiểm tra, không đụng tới, kết luận. That template is the review output. Filling it ends the pass.

## 1.7.2

- `rules/reuse-duplication.md` is one check again. Reuse an existing implementation, do not write the same statements twice, and when repeated calls differ only by data keep one implementation over a typed field list. The address form is that idea. It is not a sample pasted into the rule. `fe-implementation.md` and `conflict-fix.md` stay as they are.

## 1.7.1

- The same component rendered three or more times, differing only by data, is repeated code. `rules/reuse-duplication.md` proposes one typed field list and a single `.map`. A review proposes it and waits. Adding or changing that parent writes the shape. Two calls, or a call with a different component or handler, stay as they are.

## 1.7.0

- New `rules/reuse-duplication.md`. It is always applied. Before adding a function, component, hook, type, constant, validation, fetch, or handler, search for an existing implementation and open one caller. Reuse or extend when the contract matches. After the edit, compare the new lines with existing code and remove a block that is written twice. A repeated value or a repeated request is not this check. A one-line wording fix or a pure style tweak skips the search.
- The Claude hook injects that rule when the prompt adds or changes code, or names reuse or duplicated code, and when an edit touches source. omp loads the rule file and does not run the hook.
- `tests/test_fe_gate.py` checks that injection, and that the rule treats duplicated code as the same lines written again.

## 1.6.2

- The hook injects the conflict rule only when a line starts with a git conflict marker. A doc that mentions the marker text does not inject it.
- `rules/conflict-fix.md` keeps a one-sided rename and applies the other side's edit on the new path. Two different rename targets stop and ask.

## 1.6.1

- `rules/conflict-fix.md` reads base, ours, and theirs. A deletion the other side did not edit stays deleted. Combine fields only when they do not overlap. Regenerate a lockfile, a generated file, or a snapshot. Do not merge those files by hand. After the merge, check every previously unmerged file, then run the project checks.
- The Claude hook injects that rule when the prompt names a conflict or a marker, and when the edited file contains `<<<<<<<`. A rebase onto another branch does not inject the rule unless the prompt also names a conflict or a marker.

## 1.6.0

- New `rules/conflict-fix.md`. It is always applied. When the task resolves a merge conflict, keep each unique change from both sides once. Do not take one side and delete the other. Do not paste both blocks into one list.
- The Claude hook injects that rule when the prompt names a conflict. omp loads the rule file and does not run the hook.
- New `references/feature-isolation.md`: new behavior added to existing UI must be (1) behind one flag whose default is the old behavior, read once at the entry owner, reusing the project's flag system; (2) non-invasive — flag off means no new fetch, render, payload, or validation change, and no hook called conditionally on the flag; (3) separated — new logic in its own files under the owning feature, existing files touched only at a listed seam, proven by a deletion test.
- Bug fixes, security fixes, and pure refactors never gain a flag. A brand-new standalone screen records `n/a` and keeps only the separation guarantee.
- `new-ui.md` reads it when adding to existing UI; `refactor-ui.md` and `review-ui.md` read it only when behavior is added; `perf-ui.md` is unchanged. The output template gains a Feature Isolation section. The Architecture lens in `audit.md` greps for scattered flag reads.
- Nothing existing changes for tasks that add no behavior. The gate's deny rule for new `.vue`/`.tsx` files is unchanged.
- `rules/conflict-fix.md` is tighter: read the base (`:1`) as well as ours and theirs; a deletion is a change, so a delete-versus-edit stops and asks; combine only non-overlapping fields of an item both sides changed; regenerate generated files and lockfiles instead of merging them by hand; verify every conflicted file for markers and run the project's checks. The gate also injects the rule when the edited file contains conflict markers or the repo is mid-merge/rebase, and no longer treats a bare `rebase` prompt as a conflict.

## 1.5.0

- New `references/audit.md`: a senior audit with six lenses (Reuse, Architecture, Operational flow, Error handling, Performance and load, Extension). Each finding has `file:line`, a severity, and the cost if it stays.
- `review-ui.md` and `refactor-ui.md` fill the Audit table. `new-ui.md` fills it when the UI owns data or an action. `perf-ui.md` reads the Performance and load lens when the code polls.
- The output template has an Audit section. Hard Rules and Common Mistakes gained the matching lines.
- Names in `code-quality.md` is stricter: file name matches the main export, query hooks are named after their data, no bare `data` or `result`, one boolean style per file, one value one name. The Names row lists the searches to run.

## 1.4.5

- A matching row with no installed file now fetches that allowlisted skill and reads the downloaded copy. Fetch runs outside the consumer repo. A failed fetch is recorded, not retried silently.

## 1.4.4

- A match does not require a new page. The agent reads the installed skill file. It does not fetch a GitHub copy, and it does not install the skill.

## 1.4.3

- Playbooks read `references/external.md` and open a matching skill from vercel-labs/agent-skills or ui-ux-pro-max. Local rules still win. The agent does not install those skills.

## 1.4.2

- A matching file name outside the named folder does not change scope. The pass opens every file in that folder. It does not follow the outside file and stop.

## 1.4.1

- A code-quality pass fills one row per rule, from Names through Design and behavior. A blank row, or a `clean` row with no search, is not done.
- The pass lists every in-scope finding in that same turn. It does not leave the rest for another run.
- Cleanup, and violations written in this turn, are fixed before the agent stops. Other findings are listed and left.

## 1.4.0

- New `references/code-quality.md`: names, single-use helpers, bare positional values, explicit schemas from the server source, one file per responsibility, when to shorten and when to stop, before/after screen comparison.
- New `playbooks/review-ui.md` for checking, reviewing, cleaning up, or shortening existing UI.
- `new-ui.md` and `refactor-ui.md` read `code-quality.md`. `perf-ui.md` reads it only when the fix adds a file, a helper, or a type.
- The output template has a Code Quality section. Hard Rules and Common Mistakes gained the matching lines.

## 1.3.0

- The skill routes to `playbooks/new-ui.md`, `playbooks/refactor-ui.md`, or `playbooks/perf-ui.md`. Each playbook names the references to read.
- `rules/fe-implementation.md` is always applied. It tells the agent to read `skill://fe-arch` before non-trivial frontend code.
- A new `.vue` or `.tsx` file is denied until the transcript contains `Runtime owner:` and `Reuse Decision`. An edit of an existing file is allowed.

## 1.2.0

- The gate no longer runs on every session start. It runs when the prompt names frontend work, or when a write touches `.tsx`, `.jsx`, `.vue`, or `.svelte`.
- `rules/fe-implementation.md` is a pointer to `skills/fe-arch/SKILL.md`. The procedure stays in the skill.

## 1.1.0

- Renamed the plugin and the skill from `fe-architecture-reuse-perf` to `fe-arch`. The workflow is unchanged.

## 1.0.0
- Packaged the rewritten skill as one plugin for Claude Code and omp.
- `SKILL.md` keeps the workflow, the output template, and the hard rules. Detail stays in `references/`.
- Removed the loose root copies (`SKILL (1).md`, `ownership.md`, `reuse.md`, `performance.md`).
- No external doc links. The reference text is the local rewrite.
