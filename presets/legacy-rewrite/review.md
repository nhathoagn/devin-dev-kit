---
description: Review rules for a project that rewrites an old system. Read when `.fe-kit/config.yaml` lists the preset `legacy-rewrite`.
---

# Legacy rewrite — review

The project config names the old-system source in `legacy.source` and the change requests in `legacy.cr`.

- The old system is the business source. A behavior that matches the old system, with no change request against it, is not a finding. Do not report it. Say it only when the user asks.
- A behavior that differs from the old system, with no change request that names it, is a finding. Quote the old-system line and the new line.
- A change request wins over the old system. Quote the change-request entry.
- Do not use "the old code is written this way" to defend a code shape. The old system decides behavior, not structure.
- A message, a label, and a column order match the old system or the change request word for word, parameters included.
- An error marks the same field as the old system.
- When you cannot read the old-system source (the folder is missing or not in git), say that in one line under Kết luận. Do not guess the old behavior.
