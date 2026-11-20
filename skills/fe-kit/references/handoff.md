# Pre-commit handoff

Write `.fe-kit/handoff.md` after the code works and before `git commit`. The reader is the person
who will maintain this code without the AI that wrote it. If they cannot debug it from the handoff,
the change is not finished.

The commit gate (`.fe-kit/config.yaml` `handoff: required`, the default) refuses a commit whose
staged source files are not covered by this file and approved by the user.

## The file

One file per change, overwritten each time. Keep it short enough to read in one sitting; detail goes
in the code, not here.

```md
# Handoff — <feature or fix>

## 1. Logic
What the change does, in plain language. Input → output, states, branches, and the edge cases that
decide behavior. A reader must be able to predict what happens for a new input without opening code.

## 2. Implementation
The flow the code takes, in order. Name every file changed and the function that owns each step.
    - `src/order-form.tsx:42` `OrderForm` — reads the draft, calls `useOrderDraft`
    - `src/use-order-draft.ts:18` `useOrderDraft` — validates and stores
    - `api/orders.ts:31` `createOrder` — posts and maps the response
Say where data is created, read, copied, and written. Name the one holder of each piece of state.

## 3. Decisions
Why this shape. What was rejected and why. Constraints that forced it (API, legacy data, platform).
A reader who does not know the alternatives will "fix" this back to the rejected shape.

## 4. Debug without AI
The part that matters most.
    - Reproduce: the exact command or click path, with inputs that show the bug.
    - Watch: file:line to open, the values to print, the network call to inspect.
    - Failure meanings: each error message or wrong output and what it points to.
    - Verify a fix: the command or check that must pass.
    - Rollback: the smallest revert that leaves the app working.
A reader must be able to do this without asking an AI what the code means.

## 5. Risks and open items
Unverified edges, missing tests, follow-ups, and the cost if left. "None" is a claim the user can
challenge.

## 6. Q&A
The questions the agent asked and the user's answers, one line each.
    - Q: What happens when the list is empty? A: <the user's answer>
    - Q: Which caller breaks first if the response shape changes? A: <answer>
```

End with the user's approval, written by the approve command, not by the agent:

```
Confirmed-by: <name>
Confirmed-at: <ISO timestamp>
```

## The Q&A

Ask 3–5 questions in chat, in one round, before writing the confirmation. Ask about the parts the
user will have to debug: the state holder, the branch that is easy to miss, the caller that breaks
first, the check that proves a fix. Do not ask "does it look good"; ask for a fact.

Record the user's answers in section 6, in their words. If the user cannot answer, the handoff is
not clear enough: rewrite section 1 or 4, or simplify the code, then ask again.

The agent does not approve its own handoff. After reading, the user runs:

```bash
python3 "<plugin>/scripts/handoff.py" approve --root .
```

The gate re-checks coverage and staleness on every commit. Editing a source file after approval
invalidates it; ask the user to read the changed part and approve again.

## Check and turn it off

```bash
python3 "<plugin>/scripts/handoff.py" check --root .    # exit 1 lists what is missing
```

A repo that does not want this gate writes `.fe-kit/config.yaml`:

```yaml
handoff: "off"
```

Quote `"off"`; unquoted `off` is a YAML boolean.
