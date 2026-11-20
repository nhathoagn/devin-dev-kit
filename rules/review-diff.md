---
description: Do not grade a frontend diff you wrote.
alwaysApply: true
trigger: always_on
---

Do not grade a frontend diff you wrote. On Claude Code, hand the diff and the playbook path to agent `fe-kit:reviewer`. On Devin, spawn the `fe-kit:reviewer` subagent with the diff range and the playbook path. On omp, a fresh context reads `skill://fe-kit/playbooks/review-diff.md`. You do not write the verdict. A behaviorless wording or style change skips this, as defined in `rules/fe-implementation.md`: a change that alters runtime behavior never skips it.
