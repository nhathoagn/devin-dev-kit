# Readability for the Next Reader

The target reader is an intern or fresher: someone who knows the language but not the project. The goal is flat, boring code they can maintain: logic visible where the action happens, no layers added "for later", no construct that needs a second read. The authoring rules for that shape live in `references/code-quality.md` §"Flat by default"; this file is the review-side verification — it measures whether the written code actually reads flat. Boswell & Foucher's *The Art of Readable Code* names the metric as Time to Understand: every minute a reader spends decoding is a minute not spent changing code. When a line below matches a check in the Fowler/POSD/Beck checklists, count it once there; this file governs what those files do not ask.

A rule that makes code shorter but forces the reader to simulate it in their head is a finding, not a cure. When the explicit version and the clever version disagree on readability, the explicit version wins.

## 1. The Trace Test

Pick one primary action in scope (a submit, a save, a load). Trace it from the UI entry point to the data edge (a query, an API call, a write). Count every file hop.

- A hop is **legible** when the reader finds the next file by a static import whose name says the target's responsibility, or by searching the callee's name verbatim.
- A hop is **hidden** when it passes through runtime registration, dynamic dispatch, a stringly-typed route or event name, a callback injected from far away, or knowledge only the team has.
- Finding: the trace has two or more hidden hops, or four or more hops where at least one forwards without adding validation, transformation, naming, or a boundary contract.
- Write the trace in the report as `entry → … → edge`, one hop per file, naming the hidden ones. A finding without the written trace is not checkable.

## 2. Grepability

A fresher navigates by search, not by memory. Anything that blocks search blocks them.

- A dynamic import with a variable path, or a module name built from strings, hides its target. When registration is deliberate (a plugin host), the registry needs one readable index file that names every registration — that file is the hop.
- Dispatching by a computed string (`handlers[type]`, `emit("order:" + kind)`) means searching the event name finds nothing. Prefer a direct call, or keep the string constant in one place both sides import.
- Re-export chains (`index.ts` → `index.ts` → real file) add hops that carry no information. Import from the file that owns the symbol. (Also a bundle-size rule in `references/performance.md`; count once.)

- Rename-for-style without behavior change is fine; renaming a searchable term of the domain into a project-private synonym is a finding.

## 3. Layer Depth and Nesting

- Every layer between the entry and the logic must earn its hop: validation, transformation, a boundary contract, or a name that adds information. A layer that only forwards props or arguments is a zero-information hop (cross-reference: pass-through in `posd-checklist.md` O5/O6, middle man in `fowler-checklist.md` F2d — count once).
- A JSX chain `Screen → Wrapper → Inner` where the intermediates add no behavior forces the reader to open N files to reconstruct what renders. Prefer flattening or naming what each intermediate adds.
- Conditional rendering nested deeper than two levels in JSX hides which branch the user sees. Extract the branch into a named component whose name is the condition.
- Deep modules are good when their interface is small and documented at the boundary; depth is a problem only when the reader must open the inside to use the outside.

## 4. Explicitness over Cleverness

Flag code a fresher cannot read aloud correctly on the first pass:

- A `reduce` with a multi-field accumulator where a plain loop states the same steps in order.
- Ternaries nested deeper than one level; a boolean expression longer than three terms without a named intermediate variable.
- A regex with no example input beside it.
- Bit tricks, numeric encoding (`status === 2`), or ordering dependencies ("must run before X") that exist only in the author's head. Give the value a name, or state the dependency in the type or the call order.
- Implicit behavior triggered by shape: a `null` that means "reset", an empty string that means "delete", a missing key that means "default". One sentinel meaning one thing, named at its owner.
- A long `if`/`else if` chain over one value where a lookup table (`Record<key, value>`) states the same mapping in one glance — table-driven beats branching when every branch is one assignment.


## 5. Vocabulary

- Names use the domain's terms — the ones a newcomer finds in docs, tickets, or the glossary — not synonyms invented per file. One concept, one name across the files in scope. (The glossary check itself is F21 in `references/review-checks.md`; count once.)
Naming detail from *The Art of Readable Code* (count once with N1/SM1/O14; this file adds the falsifiable shapes, not the verdict):

- Attach units and qualifiers to the name when the bare word loses them: `timeoutSecs`, `sizeMb`, `maxWidthPx`, `htmlEscaped` — never encode them in a comment beside a bare name.
- Prefer the specific verb: `fetchPage`, `downloadFile` over `get`; `get` is fine only for a cheap local read.
- Name length follows scope size: a three-line loop body tolerates `i`; a module-level constant does not.
- Packing multiple ideas into one name (`inputCopyWithDefaults`) signals a statement doing several things at once — split the statement before renaming.
- A name a fresher would misread (`data`, `handle`, `process`, `items` for one kind of item) is a naming finding, already covered by N1/SM1/O14 — do not double-count; this section governs *domain* vocabulary only.
- Copy strings the user sees belong in one place per feature, so a wording change does not require knowing which of several hard-coded copies renders.

## Concrete Anti-Patterns to Reject

- A trace with two hidden hops or a forwarding hop that adds nothing.
- A module name or event name constructed at runtime with no readable registry.
- A re-export chain between the importer and the owner.
- Nested ternaries, a multi-field `reduce` where a loop reads plainly, or a bare regex.
- `null`/`""`/missing-key carrying a silent second meaning.
- The same domain concept under two names in one scope.
- A layer or JSX wrapper that exists only because the structure "might need it later".

## Rules

- Write the trace before judging depth. Never cite hop count without the written trace.
- The fresher test applies to the primary action in scope, not every path in the repo.
- Do not flatten a layer that earns its hop. Do not add abstraction to look senior.
- When a hidden hop is deliberate architecture (plugin host, event bus), the fix is one readable registry or index file at the boundary, not ripping out the pattern.
- Report remaining readability risk: name the hop a fresher will still need help with, and say why that cost is acceptable for this change.
