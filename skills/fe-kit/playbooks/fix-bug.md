# Fix a bug

Use this when the task reports wrong behavior: a wrong value, a broken flow, a blank screen, lost input, or a symptom with no verb (`Tổng sai khi có discount` is a bug fix).

Do not patch the symptom. Follow these steps in order.

1. Reproduce first. Write three lines, each with a value, before any edit: `Trigger:`, `Expected:`, `Actual:`. Add the evidence: a failing test, a command, or a screen state you saw. If you cannot reproduce it, say the fix is unverified and name what is missing. Do not guess a patch.
2. Find the root cause at its owner. Trace the wrong value or rule from where it is produced to where it is shown. Read `references/ownership.md`. Record the five ownership fields: the fix lands where the wrong value or rule is produced, not in a consumer that only displays it, unless that consumer is the owner.
3. Read `references/external.md`. If the bug will not reproduce or one trace does not find the root cause, open `diagnosing-bugs` there and run its loop inside steps 1 and 2. If the user asked to fix test-first, open `tdd` there and run its loop inside step 7. Record the outcome in the sections above; do not emit that skill's own report.
4. Read `references/reuse.md` and `rules/reuse-duplication.md`. Before any new state, prop, variable, validator, or handler, name the one that already holds that value or does that job, and the search you ran. Fix the existing holder.
5. Make the smallest fix that removes the root cause. Only the lines the root cause needs. No refactor, cleanup, rename, new behavior, or new flag in the same change: name those and leave them for a separate change. No fallback, guard, or default that turns the wrong case into a silent pass. No second holder, second validation path, or copy of a nearby block.

A fix that adds or widens a guard, validator, or `parse`/`check` function has one more step before the test. Enumerate every field or value the code path behind that guard reads — every throw, every dereference, every arithmetic use — before writing the guard. The guard covers that set, not only the field the report named. A guard that accepts `tier: "platinum"` while the consumer throws `RangeError` on it has the contract backwards: the boundary now promises validity it does not check. Then write one property-style check for the invariant — for every input the guard accepts, the path behind it does not throw. Include that check in step 7's test.
6. Check the impact of the fix. A fix can give a field a value it never held before: a blank, `0`, `null`, a default that is now gone, or a default that is now added. Another flow can depend on the old value and break. A fix that gives no field a new value skips this step. Say that in one line. Otherwise:
   - Name each field that can now hold a new value, and the new value.
   - Search every writer and reader of that field: `setValue('x')`, `getValues('x')`, `useWatch`, `watch`, the field's schema rule, the submit payload, and any effect or handler that reads it. Name the search and each hit with `file:line`.
   - For a rewrite of an old screen, also read every old-system event that reads or fills that field, not only the event of the bug. Name each one with `file:line`. When the old system fills the new value in an event the new code does not cover, that gap is part of this fix.
   - Write an `Impact:` list in the reply: one line for each flow, with the field, the new value, the expected result, and the source.

   Example. The bug: one 製番 with a stored NULL tax showed the default tax. The fix: the 製番 load leaves the tax blank, as the old system does. The new value: a blank tax after the 製番 load. The search finds the 納入先, 需要家, and 送り先 lookups. The old system fills a blank tax on every postback, and those lookups are postbacks. The new lookups do not fill it. Without this step, that second bug goes out with the fix.
7. Write the unit test in the file the project already uses for that owner. If that owner has no test file, add one beside it, named and imported the same way as the nearest test in the repo. Do not add a test folder, a runner, or a screen snapshot for one bug.

The test calls the owner, not a copy of the logic. It asserts the result the user sees: the value, the message, or the error. A test that only checks a mock was called does not count. Include the `Actual:` case that failed before the fix and the `Expected:` case that must pass. For a text check, also include `undefined`, `null`, `""`, a leading space, and a trailing space. The `Actual:` case must fail on the old code. If you cannot show that, the test does not lock the bug.

Skip the file only when the repo has no test runner. Say that, and re-run the reproduction instead. "No time" is not a reason.
8. Verify. Run the project's type-check, lint, each `gate:` command from `scripts/project_config.py`, and the new or updated test. Report each command and its exit code. Re-run the reproduction from step 1 and state the result. Then run each flow in the `Impact:` list from step 6 and state its result. A fix with no re-run reproduction is not done. A fix with an `Impact:` flow that was not run is not done: name each flow that was not run and the reason.

Edit gate: declare `Runtime owner:`, `Decision:`, `Trigger:`, `Expected:`, and `Actual:` before the first edit of a source file the gate covers, as `rules/fe-implementation.md` says — not only `.tsx`; the gate also covers `.ts`, `.jsx`, `.js`, `.mjs`, `.cjs`, `.vue`, `.svelte`, `.astro`, `.mdx`, and the other source languages. Editing an existing file is not exempt.
