"""Behavioral parity checks for the two host-specific gate implementations.

The hosts use different tool names and decision envelopes, but a source edit without
labels must be blocked in both, and the same prompt-typed labels must open both.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE_GATE = os.path.join(ROOT, "scripts", "fe-gate.py")
DEVIN_GATE = os.path.join(ROOT, "scripts", "devin_gate.py")

TSX = "export function A(){ return <div>x</div> }\n"
DECL_ECHO = ('echo "Runtime owner: OrderForm" "Decision: extend" '
             '"Interface depth: unchanged"')


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, check=True)


def make_repo(path):
    os.makedirs(os.path.join(path, "src"), exist_ok=True)
    git(path, "init")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "test")
    target = os.path.join(path, "src", "app.tsx")
    with open(target, "w", encoding="utf-8") as handle:
        handle.write(TSX)
    git(path, "add", "-A")
    git(path, "commit", "-m", "init")
    return target


def run(script, payload, state_dir):
    env = dict(os.environ)
    env["FE_GATE_STATE_DIR"] = state_dir
    env["FE_ARCH_ROOT"] = ROOT
    env["FE_GATE_NO_FLUSH"] = "1"
    env.pop("DEVIN_PROJECT_DIR", None)
    env.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run(
        [sys.executable, script], input=json.dumps(payload),
        capture_output=True, text=True, env=env, timeout=30)


def user_entry(text, request="req-1"):
    return {"type": "user", "message": {"content": text}, "promptId": request, "uuid": request}


def write_transcript(folder, entries):
    path = os.path.join(folder, "transcript.jsonl")
    with open(path, "w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")
    return path


def fe_edit(target, root, transcript):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": target, "old_string": "x", "new_string": "y"},
        "cwd": root,
        "session_id": "sess-1",
        "transcript_path": transcript,
        "prompt_id": "req-1",
    }


def fe_bash(command, root, transcript):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": root,
        "session_id": "sess-1",
        "transcript_path": transcript,
        "prompt_id": "req-1",
    }


def devin_payload(name, prompt="", tool="", tool_input=None):
    return {
        "hook_event_name": name,
        "prompt": prompt,
        "tool_name": tool,
        "tool_input": tool_input or {},
        "session_id": "sess-1",
        "prompt_id": "req-1",
    }


def devin_edit(target, root):
    return devin_payload(
        "PreToolUse", tool="edit",
        tool_input={"file_path": target, "old_string": "x", "new_string": "y", "workdir": root})


def fe_denied(result):
    if not result.stdout.strip():
        return False
    out = json.loads(result.stdout).get("hookSpecificOutput") or {}
    return out.get("permissionDecision") == "deny"


def devin_blocked(result):
    if not result.stdout.strip():
        return False
    return json.loads(result.stdout).get("decision") == "block"


class GateDriftBehavior(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "repo")
        self.target = make_repo(self.root)
        self.state = os.path.join(self.tmp.name, "state")
        self.transcript = write_transcript(self.tmp.name, [user_entry("update the order form")])

    def test_unlabelled_source_edit_blocked_on_both_hosts(self):
        fe = run(FE_GATE, fe_edit(self.target, self.root, self.transcript), self.state)
        run(DEVIN_GATE, devin_payload("UserPromptSubmit", prompt="update the order form"), self.state)
        devin = run(DEVIN_GATE, devin_edit(self.target, self.root), self.state)
        self.assertTrue(fe_denied(fe), fe.stdout + fe.stderr)
        self.assertTrue(devin_blocked(devin), devin.stdout + devin.stderr)

    def test_prompt_typed_labels_open_both_hosts(self):
        labels = ("Runtime owner: OrderForm\nDecision: extend\nInterface depth: unchanged")
        transcript = write_transcript(self.tmp.name, [user_entry("update the order form\n" + labels)])
        fe = run(FE_GATE, fe_edit(self.target, self.root, transcript), self.state)
        run(DEVIN_GATE, devin_payload("UserPromptSubmit", prompt="update the order form\n" + labels), self.state)
        devin = run(DEVIN_GATE, devin_edit(self.target, self.root), self.state)
        self.assertFalse(fe_denied(fe), fe.stdout + fe.stderr)
        self.assertFalse(devin_blocked(devin), devin.stdout + devin.stderr)


if __name__ == "__main__":
    unittest.main()
