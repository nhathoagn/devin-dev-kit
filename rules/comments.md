---
description: Delete comments that narrate or excuse code. Keep only proven external constraints, legal headers, public API docs, and style-only suppressions. Encode in-scope constraints instead of prose.
alwaysApply: true
---

Default to deleting comments rather than keeping or shortening them. Do not write narration, section banners, commented-out code, or workaround justifications. Never polish a weak comment into a shorter alibi.

Only these comments survive, with proof:

- Legal or license headers.
- Non-obvious behavior forced by an external dependency, platform, vendor, or protocol you cannot reshape, proven true today on a live path.
- `prettier-ignore`, or a lint suppression whose rule is faulty, pedantic, or style-only.
- A doc comment that defines a public API contract, sitting on the symbol it describes.
- An issue or RFC link that explains a constraint code cannot express.

When you are not sure a keep-list exception applies, delete the comment.

A comment explaining a surprise or workaround in our own code is a defect in the code, not a reason to keep the comment. Fix the smallest root cause in scope — rename, extract, narrow the type, drop a dead path or parameter, or use the real API — so the behavior is obvious without prose, then delete the comment. If the root cause is out of scope, land the smallest in-scope fix and report the rest open. Never bolt on a symptom guard.

Check every `eslint-disable`, `@ts-ignore`, `@ts-expect-error`, and similar suppression against the rule it silences. If the rule catches real bugs or protects correctness or safety, do not suppress it: fix the underlying code and delete the suppression.

Treat constraint comments (`IMPORTANT`, `do not remove`, `do not change wording`, `talk to X before changing`, `too risky`, `fine for now`) as a lead, not proof. Read nearby code and trace the named symbol or its history before deciding. Keep the comment only when it is proven to be an external constraint you cannot change on a live path. When the constraint is on our own code, replace the prose with the cheapest in-scope enforcement — a type, runtime check, test, or CI/lint rule — then delete the comment; if enforcement needs approval or is out of scope, propose the cheapest encoding and report the unenforced constraint open. If the claim is refuted or still ambiguous after tracing, delete the comment.

Update or delete any comment that becomes false after a change. Delete completed TODOs, and name an owner on any new TODO.
