# Refactor UI

Use this when the task splits, moves, or restructures UI that already exists.

1. Read `references/ownership.md`. Record the five ownership fields in the output template in `SKILL.md`.
2. Read `references/reuse.md`. Record the reuse decision. Prefer `reuse` or `extend` over a new shared file. A different job goes in a new file, per `rules/modules.md`; file length alone does not split a file.
3. Do not read `references/performance.md` unless the refactor is about render or fetch cost. Otherwise write `n/a` and say why.
4. Read `references/code-quality.md`. Fill the sweep table. Capture the screen before the first edit so you can compare it after the last one. Follow the fix rule in Sweep.
5. Read `references/audit.md`. Fill the Audit table for the code you move or restructure. A refactor that adds a second path for one rule is not done.
6. Do not read `references/feature-isolation.md` for a pure refactor: no behavior changes, so no flag. Write `n/a` and say why. Read it only if the refactor also adds new behavior or changes a shared component's behavior for existing callers; then that new behavior follows it, and the refactor itself stays unflagged.
7. Read `references/smells-checklist.md`, `references/fowler-checklist.md`, then `references/posd-checklist.md`. The first names smells on the code the refactor will touch — run it before the first edit so the plan knows what it is removing. The second scores the code it touched: moved methods, changed signatures, split classes. The third asks what the first two do not: is each touched module deep, does a new interface push complexity up to its callers, could an error case be defined away. Every FAIL becomes a candidate the refactor should have removed — a refactor that finishes while a smell or red flag it touched still stands is incomplete, not PASS. Record FAILs under Sweep or a Fowler line in the output.
8. Read `references/external.md`. For a match, read the installed skill file, or fetch it per that file. If none match, write `n/a` under Departures / Notes and name the skip.

Edit gate: declare `Runtime owner:` and `Decision:` before the first `.tsx`, `.jsx`, `.vue`, or `.svelte` edit, as `rules/fe-implementation.md` says.
