---
description: Design questions before code in a project that rewrites an old system. Read when `.fe-kit/config.yaml` lists the preset `legacy-rewrite`.
---

# Legacy rewrite — design questions

Answer each question that applies before the first edit. Write the answer under Departures / Notes, with its source line. Skip a question that does not apply.

- Which old-system event fills or reads each field you touch? Name each one with `file:line`.
- Does a change request add, remove, or rename this field, column, or message? Name the entry. With no entry, keep the old behavior.
- After submit, does the field show the value the old system normalized (trim, case, width)?
- Do the client and the server allow the same characters?
- Does each limit (maximum days, maximum rows) match the old system or the change request?
- A reversed date range: what does the old system do?
- A message: is it the same text, with the same parameters, on the same field as the old system?
- A lookup or a popup: which other fields does the old system fill on return? Does the new code fill the same fields?
- An export or a print: are the columns, their order, the headers, and the encoding the same as the old system or the change request?
