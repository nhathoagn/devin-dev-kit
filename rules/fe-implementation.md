---
description: Read skill fe-kit before non-trivial frontend code.
alwaysApply: true
---

If the task changes UI, a component, a hook, a form, data fetching, or feature state, and it is not a behaviorless wording or style change, read `skill://fe-kit` before you write code.

Before you create a file, name the convention it follows and the existing file or folder whose shape it takes, per `rules/modules.md`.

A wording or style change is behaviorless by what it changes, not by how many lines it touches. It may touch any number of lines only when every changed token is copy, style, or a comment: no new state, prop, variable, branch, validation, handler, fallback, or default, and no changed value, condition, or call. Copy means JSX text, a whitelisted text attribute such as `title`, `aria-label`, `placeholder`, `alt`, or `label`, a copy call such as `t`, `i18n.t`, `alert`, or `toast.*`, or a property or constant whose name ends in a copy word such as `label`, `text`, `title`, `message`, or `description`. Style means a class or style attribute, a `cn`/`clsx`/`styled` call, or a style key. Everything else is code and follows `playbooks/fix-bug.md` when the task is a fix: an import source, an endpoint, an enum value, a route, a storage key, a config constant, a condition, and a call. `scripts/wording.py` implements the token diff the gate uses.

Before the first gated edit of a request, declare two labels with one plain Bash command. The gate reads the command, not the transcript, so a thinking block or a late transcript write does not lose them: `echo "Runtime owner: OrderForm" "Decision: reuse"`. Use a real name, not `<...>`. The decision is one of `reuse`, `extend`, `feature-local`, `shared`, or `n/a`. A bug fix also declares `"Trigger: ..." "Expected: ..." "Actual: ..."`. A new request needs a new declaration. Lines in the reply text, such as `Runtime owner: OrderForm` on its own line, still count.
