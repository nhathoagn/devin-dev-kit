---
description: Do not grade a diff you wrote.
alwaysApply: true
trigger: always_on
---

Do not grade a diff you wrote, on any source file, not only frontend. Fan out reviewers by lens: a diff of 10 files or fewer gets one reviewer per lens from `scripts/review_lenses.py`, in parallel; a larger diff gets one reviewer per package from `review_packages.py split` plus one `--lens contract` reviewer over the whole range. Merge with `review_packages.py merge`, fix the merged findings once, then send the fix to one fresh reviewer that checks each finding at HEAD. On Claude Code, hand each lens's diff and the playbook path to agent `fe-kit:reviewer`. On Devin, spawn the `fe-kit:reviewer` subagent once per lens. On omp, each fresh context reads `skill://fe-kit/playbooks/review-diff.md`. You do not write the verdict. A behaviorless wording or style change skips this, as defined in `rules/fe-implementation.md`: a change that alters runtime behavior never skips it.
