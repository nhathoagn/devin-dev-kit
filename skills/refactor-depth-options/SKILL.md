---
name: refactor-depth-options
description: "When asked to improve/refactor/clean up code without a stated depth — enumerate refactor-depth options and tradeoffs before editing. Also use for Vietnamese requests such as improve code, refactor, sửa lại, tối ưu, làm gọn, code này dở, viết lại cho sạch."
---

# Refactor depth requests

"Improve", "refactor", "clean up", "tối ưu", "sửa cho gọn" without a scope qualifier is ambiguous about HOW DEEP the change goes, not whether to change. Picking a depth silently is the failure mode — the user may want a different level and will only discover it after several rounds.

### Procedure

1. Before editing, list the viable depth levels for this code. Typical ladder:
   - **Keep shape**: remove nesting/duplication, rename, destructure — structure and APIs unchanged.
   - **Change pattern**: table-driven lookup, predicate/rule lists, `find`/`??`, strategy map — same behavior, different maintenance model (edit data, not logic).
   - **Restructure**: new types, new file layout, changed function signatures — affects callers.
2. Give each option a one-line tradeoff (diff size, extensibility, indirection cost, API impact).
3. Recommend one with a reason tied to the code's actual shape (number of decision dimensions, expected change frequency).
4. Then either:
   - ask when levels differ materially in maintenance model or API surface, or
   - proceed with the recommended level AND state explicitly in the reply that it is the smallest/largest option and name the alternatives not taken.

### Skip conditions

- Only ONE level is genuinely viable (e.g. file already table-driven; the request names the exact pattern to apply) → proceed, no ladder needed.
- The request already specifies depth ("just flatten it", "keep the structure") → obey, no ladder.

### Rules

- Never present a table/pattern rewrite as "the improvement" when a keep-shape version exists — present both.
- If the user pushes back ("still too much if"), treat it as a depth signal and jump a level, do not re-apply the same pattern differently.
- A review finding that proposes a deeper refactor stays a finding — state it as an option, do not dismiss it as "not worth it" on your own judgment alone.
- One-off demo files still get the options; conservatism is a stated choice, not an assumption.
