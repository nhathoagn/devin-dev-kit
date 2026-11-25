---
description: Review a diff only when the user asks.
alwaysApply: true
trigger: always_on
---

Review a diff only when the user asks for a review. Do not start a review on your own after an edit, before a commit, or before you report done. When the user asks, do not grade a diff you wrote, on any source file, not only frontend. Fan out reviewers by lens: a diff of 10 files or fewer gets one reviewer per lens from `scripts/review_lenses.py`, in parallel; a larger diff gets one reviewer per package from `review_packages.py split` plus one `--lens contract` reviewer over the whole range. Merge with `review_packages.py merge`, fix the merged findings once, then send the fix to one fresh reviewer that checks each finding at HEAD. On Claude Code, hand each lens's diff and the playbook path to agent `fe-kit:reviewer`. On Devin, spawn the `fe-kit:reviewer` subagent once per lens. On omp, each fresh context reads `skill://fe-kit/playbooks/review-diff.md`. You do not write the verdict.
