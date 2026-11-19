# New UI

Use this when the task adds a component, page, form, or hook.

1. Read `references/ownership.md`. Record the five ownership fields in the output template in `SKILL.md`.
2. Read `references/reuse.md`. Record the reuse decision in that same template. A different job goes in a new file, per `rules/modules.md`.
3. Read `references/performance.md` only if the new UI fetches, lists, or streams. Otherwise write `n/a` in the performance section and say why.
4. Read `references/code-quality.md`. Record the Code Quality section before you name files, helpers, and types. After the last edit, fill the sweep table for each file you created or edited. Follow the fix rule in Sweep.
5. Read `references/audit.md` when the new UI owns data or an action. Fill the Operational flow, Error handling, and Extension rows before you write the code, and every row after the last edit. Otherwise write `n/a` for the Audit section and say why.
6. Read `references/feature-isolation.md` when the new UI adds behavior to an existing screen, feature, or shared component. Fill its table before you write code. Otherwise (a brand-new standalone screen) write `n/a` for Feature Isolation and say why; guarantee 3 (separation) still applies.
7. Read `references/external.md`. For a match, read the installed skill file, or fetch it per that file. If none match, write `n/a` under Departures / Notes and name the skip.

Do not create or edit a `.tsx`, `.jsx`, `.vue`, or `.svelte` file until the reply contains `Runtime owner:` with a named owner and a Reuse Decision with one decision. Declare them before the edit call with one Bash command, as in `echo "Runtime owner: OrderForm" "Decision: reuse"`. Also write them in the reply for the reader. The hook does not read the reply text, thinking, or a table row. Only a behaviorless wording or style change (see `rules/fe-implementation.md`) is exempt.
