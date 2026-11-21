"""Tests for scripts/devin_gate.py. Run: python scripts/test_devin_gate.py (exit code = number of failures).

Each case sends one Devin hook payload (UTF-8 JSON on stdin) and checks stdout: a
{"decision": "block"} object, hookSpecificOutput context, or silence. Devin payloads carry
prompt/session_id/prompt_id, so no transcript file is needed. A real request is a
UserPromptSubmit event followed by PreToolUse events with the same session_id/prompt_id.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "devin_gate.py")
TMP = tempfile.mkdtemp(prefix="devin-gate-test-")
ENV = dict(os.environ, FE_ARCH_ROOT=os.path.dirname(HERE),
           FE_GATE_STATE_DIR=os.path.join(TMP, "state"))

CASES = []
FAILURES = []

def case(expect, label):
    def wrap(fn):
        CASES.append((expect, label, fn))
        return fn
    return wrap

def call_gate(payload, env=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    result = subprocess.run([sys.executable, "-I", GATE], input=data, capture_output=True, env=env or ENV)
    return result.stdout.decode("utf-8"), result.stderr.decode("utf-8"), result.returncode

def output_of(payload, env=None):
    out, err, rc = call_gate(payload, env)
    return out + err

S = ["s0"]  # main() gives each case a fresh session id, so state cannot leak across cases.

def prompt_event(text, session=None, prompt_id="p1"):
    return {"hook_event_name": "UserPromptSubmit", "prompt": text, "source": "user",
            "session_id": session or S[0], "prompt_id": prompt_id}

def edit_event(path="src/B.tsx", old="a", new="b", session=None, prompt_id="p1", tool="edit"):
    return {"hook_event_name": "PreToolUse", "tool_name": tool,
            "tool_input": {"file_path": path, "old_string": old, "new_string": new},
            "session_id": session or S[0], "prompt_id": prompt_id}

def exec_event(command, session=None, prompt_id="p1", workdir=None):
    tool_input = {"command": command}
    if workdir:
        tool_input["workdir"] = workdir
    return {"hook_event_name": "PreToolUse", "tool_name": "exec",
            "tool_input": tool_input, "session_id": session or S[0], "prompt_id": prompt_id}

def declare(*labels, session=None, prompt_id="p1"):
    cmd = "echo " + " ".join('"%s"' % line for line in labels)
    return exec_event(cmd, session=session, prompt_id=prompt_id)

def write_source(name="src/B.tsx", text="export const X = 1\n"):
    target = os.path.join(TMP, name)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(text)
    return target

def blocked(payload, env=None):
    out, _, _ = call_gate(payload, env)
    try:
        return json.loads(out).get("decision") == "block"
    except ValueError:
        return False

def seq(events, env=None):
    # Run every event but the last; return the last event's stdout.
    for event in events[:-1]:
        call_gate(event, env)
    return output_of(events[-1], env)

# --- prompt injection -----------------------------------------------------
@case("inject", "frontend prompt injects the fe-implementation rule")
def _():
    return "skill://fe-kit" in output_of(prompt_event("viết component order form bằng react"))

@case("quiet", "non-frontend prompt with no author intent stays silent")
def _():
    return output_of(prompt_event("xem log server staging")) == ""

@case("inject", "authoring prompt injects the review rule")
def _():
    return "Do not grade a diff you wrote" in output_of(prompt_event("implement a helper to sum numbers"))

@case("inject", "a non-frontend source write injects the review rule")
def _():
    out = output_of(edit_event(path="util/sum.py", old="a", new="b"))
    return "Do not grade a diff you wrote" in out

@case("inject", "post-compaction still reminds the review rule after a non-gated edit")
def _():
    seq([prompt_event("implement a helper to sum numbers"),
         edit_event(path="util/sum.py", old="a", new="b")])
    out = output_of({"hook_event_name": "PostCompaction", "session_id": S[0]})
    return "Do not grade a diff you wrote" in out

@case("inject", "bug prompt injects rules")
def _():
    return "Runtime owner" in output_of(prompt_event("tổng hiển thị sai khi có discount"))

@case("quiet", "wording-only prompt skips the reuse bundle")
def _():
    return "Reuse an existing implementation" not in output_of(prompt_event("đổi chữ nút Save thành Lưu"))

@case("inject", "user labels typed in the prompt count")
def _():
    target = write_source()
    out = seq([
        prompt_event('Runtime owner: B\nDecision: reuse\nthêm nút vào component react'),
        edit_event(path=target),
    ])
    return '"decision"' not in out

# --- the gate --------------------------------------------------------------
@case("block", "edit a .tsx with no labels is blocked")
def _():
    target = write_source()
    out = seq([prompt_event("thêm validate vào form react"), edit_event(path=target)])
    return "Blocked. Run this exec command" in out and "Runtime owner" in out

@case("open", ".ts edit is not blocked")
def _():
    target = write_source("src/x.ts", "export const X = 1\n")
    return '"decision"' not in output_of(edit_event(path=target), dict(ENV))

@case("allow", "echo declaration then the edit is open")
def _():
    target = write_source()
    events = [
        prompt_event("thêm validate vào form react"),
        declare("Runtime owner: OrderForm", "Decision: reuse"),
        edit_event(path=target),
    ]
    return '"decision"' not in seq(events)

@case("note", "the echo declaration gets a recorded note")
def _():
    out = seq([
        prompt_event("thêm validate vào form react", session="s9", prompt_id="q9"),
        declare("Runtime owner: OrderForm", "Decision: reuse", session="s9", prompt_id="q9"),
    ])
    return "fe-kit recorded these labels" in out

@case("block", "a new request cannot reuse old labels")
def _():
    target = write_source()
    events = [
        prompt_event("thêm validate vào form react"),
        declare("Runtime owner: OrderForm", "Decision: reuse"),
        prompt_event("thêm cột mới vào table react", prompt_id="p2"),
        edit_event(path=target, prompt_id="p2"),
    ]
    return "Blocked." in seq(events)

@case("allow", "labels survive a continuation reply")
def _():
    target = write_source()
    events = [
        prompt_event("thêm validate vào form react"),
        declare("Runtime owner: OrderForm", "Decision: reuse"),
        prompt_event("làm đi", prompt_id="p2"),
        edit_event(path=target, prompt_id="p2"),
    ]
    return '"decision"' not in seq(events)

@case("block", "exec that writes a frontend file is gated")
def _():
    workdir = os.path.join(TMP, "repo-sh")
    write_source("repo-sh/sh.tsx")
    out = seq([
        prompt_event("thêm nút vào màn hình react"),
        exec_event('printf "x" >> sh.tsx', workdir=workdir),
    ])
    return "Blocked." in out

@case("block", "block reason forbids routing through exec")
def _():
    workdir = os.path.join(TMP, "repo-sh2")
    write_source("repo-sh2/sh.tsx")
    out = seq([
        prompt_event("thêm nút vào màn hình react"),
        exec_event('printf "x" >> sh.tsx', workdir=workdir),
    ])
    return "Do not route the change through exec" in out

# --- bug edits ---------------------------------------------------------------
@case("block-bug", "bug prompt makes the edit need Trigger/Expected/Actual")
def _():
    target = write_source()
    out = seq([
        prompt_event("tổng hiển thị sai khi có discount"),
        declare("Runtime owner: OrderForm", "Decision: reuse"),
        edit_event(path=target),
    ])
    return "Trigger:" in out and "Expected:" in out

@case("allow", "bug edit opens after full repro labels")
def _():
    target = write_source()
    events = [
        prompt_event("tổng hiển thị sai khi có discount"),
        declare("Runtime owner: OrderForm", "Decision: reuse",
                "Trigger: đơn sau 17h", "Expected: đúng ngày", "Actual: lệch 1 ngày"),
        edit_event(path=target),
    ]
    return '"decision"' not in seq(events)

@case("open", "a non-bug request after a bug request is not bug mode")
def _():
    target = write_source()
    events = [
        prompt_event("tổng hiển thị sai khi có discount"),
        prompt_event("thêm cột mới vào table", prompt_id="p2"),
        declare("Runtime owner: T", "Decision: reuse", prompt_id="p2"),
        edit_event(path=target, prompt_id="p2"),
    ]
    return '"decision"' not in seq(events)

# --- wording exemption ---------------------------------------------------------
@case("open", "wording-only JSX text edit is exempt")
def _():
    target = write_source("src/word.tsx", 'export const L = () => <button className="a">Save</button>\n')
    out = seq([
        prompt_event("đổi chữ nút"),
        edit_event(path=target, old="Save", new="Lưu"),
    ])
    return '"decision"' not in out

@case("block", "behavior edit is not exempt")
def _():
    target = write_source("src/beh.tsx", 'export const L = () => <button onClick={a}>Save</button>\n')
    out = seq([
        prompt_event("đổi handler nút"),
        edit_event(path=target, old="onClick={a}", new="onClick={b}"),
    ])
    return "Blocked." in out

# --- PostToolUse -----------------------------------------------------------------
@case("post", "conflict markers left behind exit 2 with a message")
def _():
    target = write_source("src/c.tsx", "<<<<<<< ours\na\n=======\nb\n>>>>>>> theirs\n")
    out, err, rc = call_gate({"hook_event_name": "PostToolUse", "tool_name": "edit",
                              "tool_input": {"file_path": target}, "session_id": S[0], "prompt_id": "p1"})
    return rc == 2 and "Conflict markers remain" in err

@case("post-note", "bug session gets the UT reminder after an edit")
def _():
    target = write_source("src/u.tsx")
    events = [
        prompt_event("tổng hiển thị sai khi có discount"),
        declare("Runtime owner: T", "Decision: reuse", "Trigger: x", "Expected: y", "Actual: z"),
        {"hook_event_name": "PostToolUse", "tool_name": "edit",
         "tool_input": {"file_path": target}, "session_id": S[0], "prompt_id": "p1"},
    ]
    return "unit test" in seq(events)

@case("quiet", "PostToolUse after a non-bug request stays silent")
def _():
    target = write_source("src/u2.tsx")
    events = [
        prompt_event("thêm cột vào table"),
        {"hook_event_name": "PostToolUse", "tool_name": "edit",
         "tool_input": {"file_path": target}, "session_id": S[0], "prompt_id": "p1"},
    ]
    return seq(events) == ""

# --- session isolation -------------------------------------------------------------
@case("block", "another session cannot see the labels")
def _():
    target = write_source()
    events = [
        prompt_event("thêm nút react", session="sA"),
        declare("Runtime owner: T", "Decision: reuse", session="sA"),
        prompt_event("thêm nút react", session="sB"),
        edit_event(path=target, session="sB"),
    ]
    return "Blocked." in seq(events)

@case("inject", "PostCompaction re-injects the pointer for a frontend session")
def _():
    events = [
        prompt_event("thêm nút vào màn react"),
        {"hook_event_name": "PostCompaction", "session_id": S[0], "prompt_id": "p1"},
    ]
    return "fe-kit gate is active" in seq(events)

@case("quiet", "PostCompaction stays silent for a backend session")
def _():
    events = [
        prompt_event("sửa câu SQL"),
        {"hook_event_name": "PostCompaction", "session_id": S[0], "prompt_id": "p1"},
    ]
    return seq(events) == ""

@case("inject", "SessionStart on resume re-injects the pointer")
def _():
    events = [
        prompt_event("thêm nút vào màn react"),
        {"hook_event_name": "SessionStart", "source": "resume", "session_id": S[0], "prompt_id": "p1"},
    ]
    return "fe-kit gate is active" in seq(events)

@case("quiet", "SessionStart on startup stays silent")
def _():
    events = [
        prompt_event("thêm nút vào màn react"),
        {"hook_event_name": "SessionStart", "source": "startup", "session_id": S[0], "prompt_id": "p1"},
    ]
    return seq(events) == ""

@case("block", "apply_patch touching a gated file is gated")
def _():
    patch = "*** Begin Patch\n*** Update File: src/B.tsx\n@@\n-a\n+b\n*** End Patch"
    out = seq([
        prompt_event("thêm nút react"),
        {"hook_event_name": "PreToolUse", "tool_name": "apply_patch",
         "tool_input": {"patch": patch}, "session_id": S[0], "prompt_id": "p1"},
    ])
    return "Blocked." in out

EXPECT = {"block", "block-bug", "allow", "open", "inject", "quiet", "note", "post", "post-note"}

def main():
    os.chdir(os.path.dirname(HERE))
    for i, (expect, label, fn) in enumerate(CASES):
        assert expect in EXPECT, expect
        S[0] = "s%d" % i
        try:
            ok = bool(fn())
        except Exception as exc:
            ok = False
            print("ERR ", label, repr(exc))
        if expect in ("block", "block-bug", "inject", "note", "post", "post-note"):
            passed = ok
        else:  # allow, open, quiet: the payload must not produce the checked output
            passed = ok
        print("OK  " if passed else "FAIL", "%-9s" % expect, label)
        if not passed:
            FAILURES.append(label)
    print("cases: %d, failures: %d" % (len(CASES), len(FAILURES)))
    sys.exit(len(FAILURES))

if __name__ == "__main__":
    main()
