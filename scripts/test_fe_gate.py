"""Tests for fe-gate.py: payload-level characterization of the edit label gate and the
pre-commit handoff gate. The script executes at import time, so each test feeds it a JSON
payload on stdin and reads the JSON decision on stdout.

REGRESSION classes below name the bug they pin down (A3a, A3b, A3c, B6, A4); they fail on
purpose until the fix wave lands.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fe-gate.py")
HANDOFF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "handoff.py")
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DECL_ECHO = 'echo "Runtime owner: OrderForm" "Decision: extend" "Interface depth: unchanged"'
BUG_DECL_ECHO = ('echo "Runtime owner: OrderForm" "Decision: extend" '
                 '"Interface depth: unchanged" "Trigger: apply discount" '
                 '"Expected: 90" "Actual: 100"')

TSX_SOURCE = (
    "export function OrderForm() {\n"
    "  const submit = () => {};\n"
    "  return (\n"
    "    <form onSubmit={submit}>\n"
    "      <button type=\"submit\">Place your order</button>\n"
    "    </form>\n"
    "  );\n"
    "}\n"
)


def write_file(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def git(root, *args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, check=True)


def make_repo(path):
    """A real repo with one committed file, so gate_scope sees product code."""
    os.makedirs(path, exist_ok=True)
    git(path, "init")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "test")
    write_file(path, "src/app.tsx", TSX_SOURCE)
    git(path, "add", "-A")
    git(path, "commit", "-m", "init")
    return path


def stage_source(root, rel="app.ts"):
    path = write_file(root, rel, "export const value = 1;\n")
    git(root, "add", rel)
    return path


def user_entry(text, request="req-1"):
    return {"type": "user", "message": {"content": text}, "promptId": request, "uuid": request}


def assistant_text(text, request="req-1"):
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
        "promptId": request,
        "uuid": request + "-a",
    }


def assistant_echo(command, tool_id="t1", request="req-1"):
    return {
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use", "name": "Bash", "id": tool_id,
                "input": {"command": command},
            }]
        },
        "promptId": request,
        "uuid": request + "-a",
    }


def tool_result(tool_id="t1", is_error=False, request="req-1"):
    return {
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result", "tool_use_id": tool_id,
                "content": "ok", "is_error": is_error,
            }]
        },
        "promptId": request,
        "uuid": request + "-r",
    }


def image_entry(request="req-2"):
    return {
        "type": "user",
        "message": {"content": [{"type": "image", "source": {"data": "AAAA"}}]},
        "promptId": request,
        "uuid": request,
    }


def write_transcript(folder, entries):
    path = os.path.join(folder, "transcript.jsonl")
    with open(path, "w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")
    return path


def run_gate(payload, state_dir=None, env_extra=None):
    env = {key: value for key, value in os.environ.items()
           if key not in ("CLAUDE_PROJECT_DIR", "DEVIN_PROJECT_DIR")}
    env["FE_GATE_NO_FLUSH"] = "1"
    env["FE_ARCH_ROOT"] = PLUGIN_ROOT
    env["FE_GATE_STATE_DIR"] = state_dir or os.path.join(
        tempfile.gettempdir(), "fe-gate-test-state")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, GATE], input=json.dumps(payload),
        capture_output=True, text=True, env=env, timeout=60)


def gate_output(payload, state_dir=None):
    """The hookSpecificOutput dict, or {} when the hook is silent."""
    result = run_gate(payload, state_dir)
    if not result.stdout.strip():
        return {}
    try:
        event = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"_unparsed": result.stdout}
    return event.get("hookSpecificOutput") or {}


def hook_specific(payload, state_dir=None):
    """Full parsed stdout for a payload expected to print one JSON event."""
    result = run_gate(payload, state_dir)
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def edit_event(file_path, old="x", new="y", cwd="", transcript="", session="", prompt_id="req-1"):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "old_string": old, "new_string": new},
        "cwd": cwd,
        "session_id": session,
        "transcript_path": transcript,
        "prompt_id": prompt_id,
    }


def bash_event(command, cwd="", transcript="", session="", prompt_id="req-1"):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": cwd,
        "session_id": session,
        "transcript_path": transcript,
        "prompt_id": prompt_id,
    }


def prompt_event(prompt, cwd=""):
    return {
        "hook_event_name": "UserPromptSubmit",
        "prompt": prompt,
        "cwd": cwd,
    }


def decision_of(output):
    return output.get("permissionDecision") or ""


def reason_of(output):
    return output.get("permissionDecisionReason") or ""


class GateCase(unittest.TestCase):
    """Shared fixtures: a repo, a .tsx file in it, a transcript of one user request."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "repo")
        make_repo(self.root)
        self.tsx = os.path.join(self.root, "src", "app.tsx")
        self.state_dir = os.path.join(self.tmp.name, "state")
        self.transcript = write_transcript(self.tmp.name, [user_entry("update the order form")])

    def edit(self, path=None, old="const submit = () => {};", new="const submit = async () => {};",
             transcript=None, session="", prompt_id="req-1"):
        return edit_event(
            path or self.tsx, old=old, new=new, cwd=self.root,
            transcript=self.transcript if transcript is None else transcript,
            session=session, prompt_id=prompt_id)


class EditGateDeny(GateCase):
    def test_edit_in_repo_without_labels_denied(self):
        output = gate_output(self.edit(), self.state_dir)
        self.assertEqual(decision_of(output), "deny")

    def test_deny_reason_contains_echo_command(self):
        output = gate_output(self.edit(), self.state_dir)
        self.assertIn("echo", reason_of(output))

    def test_deny_reason_names_runtime_owner(self):
        output = gate_output(self.edit(), self.state_dir)
        self.assertIn("Runtime owner", reason_of(output))

    def test_deny_reason_names_decision(self):
        output = gate_output(self.edit(), self.state_dir)
        self.assertIn("Decision", reason_of(output))

    def test_deny_reason_names_interface_depth(self):
        output = gate_output(self.edit(), self.state_dir)
        self.assertIn("Interface depth", reason_of(output))

    def test_write_tool_also_gated(self):
        payload = self.edit()
        payload["tool_name"] = "Write"
        payload["tool_input"] = {"file_path": self.tsx, "content": "export const x = 1;\n"}
        output = gate_output(payload, self.state_dir)
        self.assertEqual(decision_of(output), "deny")

    def test_python_source_also_gated(self):
        path = write_file(self.root, "src/util.py", "x = 1\n")
        git(self.root, "add", "src/util.py")
        git(self.root, "commit", "-m", "add py")
        output = gate_output(self.edit(path=path, old="x = 1", new="x = 2"), self.state_dir)
        self.assertEqual(decision_of(output), "deny")

    def test_non_source_extension_not_gated(self):
        path = write_file(self.root, "notes.txt", "hello\n")
        output = gate_output(self.edit(path=path, old="hello", new="bye"), self.state_dir)
        self.assertNotEqual(decision_of(output), "deny")


class ScopeBoundary(GateCase):
    def test_edit_outside_any_repo_not_gated(self):
        outside = write_file(self.tmp.name, "loose/x.tsx", TSX_SOURCE)
        payload = edit_event(outside, old="x", new="y", cwd=self.root)
        output = gate_output(payload, self.state_dir)
        self.assertNotEqual(decision_of(output), "deny")

    def test_edit_outside_committed_scope_not_gated(self):
        write_file(self.root, ".fe-kit/config.yaml", "scope:\n  - \"src/**\"\n")
        write_file(self.root, "docs/readme.py", "x = 1\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-m", "scope")
        output = gate_output(
            self.edit(path=os.path.join(self.root, "docs", "readme.py"), old="x = 1", new="x = 2"),
            self.state_dir)
        self.assertNotEqual(decision_of(output), "deny")

    def test_edit_inside_committed_scope_gated(self):
        write_file(self.root, ".fe-kit/config.yaml", "scope:\n  - \"src/**\"\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-m", "scope")
        output = gate_output(self.edit(), self.state_dir)
        self.assertEqual(decision_of(output), "deny")


class LabelUnlock(GateCase):
    def test_reply_text_labels_count_without_session(self):
        transcript = write_transcript(self.tmp.name, [
            user_entry("update the order form"),
            assistant_text("Runtime owner: OrderForm\nDecision: extend\nInterface depth: unchanged"),
        ])
        output = gate_output(self.edit(transcript=transcript), self.state_dir)
        self.assertNotEqual(decision_of(output), "deny")
        self.assertIn("skill://fe-kit", output.get("additionalContext") or "")

    def test_reply_text_labels_ignored_with_session(self):
        transcript = write_transcript(self.tmp.name, [
            user_entry("update the order form"),
            assistant_text("Runtime owner: OrderForm\nDecision: extend\nInterface depth: unchanged"),
        ])
        output = gate_output(
            self.edit(transcript=transcript, session="sess-1"), self.state_dir)
        self.assertEqual(decision_of(output), "deny")

    def test_successful_echo_in_transcript_unlocks(self):
        transcript = write_transcript(self.tmp.name, [
            user_entry("update the order form"),
            assistant_echo(DECL_ECHO),
            tool_result(),
        ])
        output = gate_output(self.edit(transcript=transcript), self.state_dir)
        self.assertNotEqual(decision_of(output), "deny")

    def test_echo_hook_call_saves_labels_for_the_edit(self):
        transcript = write_transcript(self.tmp.name, [
            user_entry("update the order form"),
            assistant_echo(DECL_ECHO),
            tool_result(),
        ])
        declare = hook_specific(
            bash_event(DECL_ECHO, cwd=self.root, transcript=transcript,
                       session="sess-1", prompt_id="req-1"),
            self.state_dir)
        context = (declare or {}).get("hookSpecificOutput", {})
        self.assertIn("recorded", context.get("additionalContext") or "")
        output = gate_output(
            self.edit(transcript=transcript, session="sess-1"), self.state_dir)
        self.assertNotEqual(decision_of(output), "deny")

    def test_labels_from_earlier_request_do_not_unlock_next(self):
        transcript = write_transcript(self.tmp.name, [
            user_entry("first request", request="req-0"),
            assistant_echo(DECL_ECHO, request="req-0"),
            tool_result(request="req-0"),
            user_entry("update the order form", request="req-1"),
        ])
        output = gate_output(self.edit(transcript=transcript), self.state_dir)
        self.assertEqual(decision_of(output), "deny")


class BugGate(GateCase):
    def setUp(self):
        super().setUp()
        self.bug_transcript = write_transcript(
            self.tmp.name, [user_entry("tổng sai khi có discount", request="bug-1")])
        self.bug_edit = edit_event(
            self.tsx, old="const submit = () => {};", new="const submit = async () => {};",
            cwd=self.root, transcript=self.bug_transcript, prompt_id="bug-1")

    def test_bug_request_requires_trigger_in_reason(self):
        output = gate_output(self.bug_edit, self.state_dir)
        self.assertIn("Trigger", reason_of(output))

    def test_bug_request_requires_expected_actual(self):
        output = gate_output(self.bug_edit, self.state_dir)
        reason = reason_of(output)
        self.assertIn("Expected", reason)
        self.assertIn("Actual", reason)

    def test_bug_denied_when_only_decisions_declared(self):
        transcript = write_transcript(self.tmp.name, [
            user_entry("tổng sai khi có discount", request="bug-1"),
            assistant_echo(DECL_ECHO, request="bug-1"),
            tool_result(request="bug-1"),
        ])
        payload = edit_event(
            self.tsx, old="const submit = () => {};", new="const submit = async () => {};",
            cwd=self.root, transcript=transcript, prompt_id="bug-1")
        output = gate_output(payload, self.state_dir)
        self.assertEqual(decision_of(output), "deny")
        self.assertIn("Trigger", reason_of(output))

    def test_bug_edit_opens_with_full_labels(self):
        transcript = write_transcript(self.tmp.name, [
            user_entry("tổng sai khi có discount", request="bug-1"),
            assistant_echo(BUG_DECL_ECHO, request="bug-1"),
            tool_result(request="bug-1"),
        ])
        payload = edit_event(
            self.tsx, old="const submit = () => {};", new="const submit = async () => {};",
            cwd=self.root, transcript=transcript, prompt_id="bug-1")
        output = gate_output(payload, self.state_dir)
        self.assertNotEqual(decision_of(output), "deny")

    def test_non_bug_request_does_not_need_repro_labels(self):
        transcript = write_transcript(self.tmp.name, [
            user_entry("update the order form"),
            assistant_echo(DECL_ECHO),
            tool_result(),
        ])
        output = gate_output(self.edit(transcript=transcript), self.state_dir)
        self.assertNotEqual(decision_of(output), "deny")

    def test_post_tool_use_bug_context_suggests_test(self):
        payload = dict(self.bug_edit)
        payload["hook_event_name"] = "PostToolUse"
        output = gate_output(payload, self.state_dir)
        self.assertNotEqual(decision_of(output), "deny")
        self.assertIn("test", (output.get("additionalContext") or "").lower())


class WordingExempt(GateCase):
    def test_jsx_text_only_edit_not_gated(self):
        output = gate_output(
            self.edit(old="Place your order", new="Confirm your order"), self.state_dir)
        self.assertNotEqual(decision_of(output), "deny")

    def test_code_change_still_gated(self):
        output = gate_output(
            self.edit(old="onSubmit={submit}", new="onSubmit={handleSubmit}"),
            self.state_dir)
        self.assertEqual(decision_of(output), "deny")


class PromptContext(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_frontend_prompt_injects_fe_rules(self):
        output = gate_output(
            prompt_event("Build a React form component for checkout", cwd=self.tmp.name))
        self.assertIn("skill://fe-kit", output.get("additionalContext") or "")

    def test_backend_prompt_injects_bundle_only(self):
        output = gate_output(
            prompt_event("Add a database index for faster lookup", cwd=self.tmp.name))
        context = output.get("additionalContext") or ""
        self.assertNotIn("skill://fe-kit", context)
        self.assertTrue(context.strip())

    def test_wording_only_prompt_injects_nothing(self):
        output = gate_output(
            prompt_event("fix the button label typo", cwd=self.tmp.name))
        self.assertFalse(output.get("additionalContext"))


class CommitGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "repo")
        make_repo(self.root)
        self.state_dir = os.path.join(self.tmp.name, "state")

    def commit_output(self, command, cwd=None):
        return gate_output(
            bash_event(command, cwd=cwd or self.root), self.state_dir)

    def test_commit_with_staged_source_denied(self):
        stage_source(self.root)
        output = self.commit_output("git commit -m x")
        self.assertEqual(decision_of(output), "deny")
        self.assertIn("handoff", reason_of(output))

    def test_commit_a_flag_covers_unstaged_change(self):
        write_file(self.root, "app.ts", "export const value = 1;\n")
        git(self.root, "add", "app.ts")
        git(self.root, "commit", "-m", "add app.ts")
        write_file(self.root, "app.ts", "export const value = 2;\n")
        output = self.commit_output("git commit -a -m x")
        self.assertEqual(decision_of(output), "deny")
        self.assertIn("handoff", reason_of(output))

    def test_commit_all_long_flag_covers_unstaged_change(self):
        write_file(self.root, "app.ts", "export const value = 1;\n")
        git(self.root, "add", "app.ts")
        git(self.root, "commit", "-m", "add app.ts")
        write_file(self.root, "app.ts", "export const value = 2;\n")
        output = self.commit_output("git commit --all -m x")
        self.assertEqual(decision_of(output), "deny")

    def test_commit_with_only_docs_staged_allowed(self):
        write_file(self.root, "README.md", "# readme\n")
        git(self.root, "add", "README.md")
        output = self.commit_output("git commit -m x")
        self.assertNotEqual(decision_of(output), "deny")

    def test_commit_outside_repo_not_gated(self):
        loose = os.path.join(self.tmp.name, "loose")
        os.makedirs(loose)
        output = self.commit_output("git commit -m x", cwd=loose)
        self.assertNotEqual(decision_of(output), "deny")

    def test_git_c_flag_targets_named_repo(self):
        other = os.path.join(self.tmp.name, "other")
        make_repo(other)
        stage_source(other)
        output = self.commit_output("git -C %s commit -m x" % other)
        self.assertEqual(decision_of(output), "deny")

    def test_handoff_off_config_disables_gate(self):
        stage_source(self.root)
        write_file(self.root, ".fe-kit/config.yaml", "handoff: off\n")
        output = self.commit_output("git commit -m x")
        self.assertNotEqual(decision_of(output), "deny")

    def test_approved_handoff_allows_commit(self):
        stage_source(self.root)
        write_file(self.root, ".fe-kit/handoff.md", "\n".join([
            "# Handoff",
            "## Logic", "app.ts holds the constant.",
            "## Implementation", "app.ts exports value.",
            "## Decisions", "app.ts: feature-local.",
            "## Debug without AI", "Read app.ts.",
            "## Risks", "app.ts has no callers yet.",
            "## Q&A", "app.ts naming confirmed.",
            "",
        ]))
        subprocess.run(
            [sys.executable, HANDOFF, "approve", "--root", self.root],
            capture_output=True, text=True)
        output = self.commit_output("git commit -m x")
        self.assertNotEqual(decision_of(output), "deny")


class RegressionBundledFlags(unittest.TestCase):
    """regression A3a: `git commit -am x` must gate like `git commit -a -m x`."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "repo")
        make_repo(self.root)
        self.state_dir = os.path.join(self.tmp.name, "state")
        write_file(self.root, "app.ts", "export const value = 1;\n")
        git(self.root, "add", "app.ts")
        git(self.root, "commit", "-m", "add app.ts")
        write_file(self.root, "app.ts", "export const value = 2;\n")

    def test_commit_am_denied_like_commit_a_m(self):
        output = gate_output(
            bash_event("git commit -am x", cwd=self.root), self.state_dir)
        self.assertEqual(decision_of(output), "deny")
        self.assertIn("handoff", reason_of(output))


class RegressionCommitMessageReuse(unittest.TestCase):
    """regression A3b: `-C` after `commit` reuses a message; the repo stays the cwd repo."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "repo")
        make_repo(self.root)
        self.state_dir = os.path.join(self.tmp.name, "state")
        stage_source(self.root)

    def test_commit_message_reuse_flag_denied(self):
        output = gate_output(
            bash_event("git commit -C HEAD~1", cwd=self.root), self.state_dir)
        self.assertEqual(decision_of(output), "deny")
        self.assertIn("handoff", reason_of(output))


class RegressionCdThenCommit(unittest.TestCase):
    """regression A3c: `cd <dir> && git commit` gates the repo the command lands in."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo_a = os.path.join(self.tmp.name, "repoA")
        self.repo_b = os.path.join(self.tmp.name, "repoB")
        make_repo(self.repo_a)
        make_repo(self.repo_b)
        self.state_dir = os.path.join(self.tmp.name, "state")
        stage_source(self.repo_b)

    def test_cd_then_commit_gates_target_repo(self):
        output = gate_output(
            bash_event("cd %s && git commit -m x" % self.repo_b, cwd=self.repo_a),
            self.state_dir)
        self.assertEqual(decision_of(output), "deny")
        self.assertIn("handoff", reason_of(output))


class RegressionImageAfterBug(unittest.TestCase):
    """regression B6: an image-only user message must not reset the request scope."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "repo")
        make_repo(self.root)
        self.tsx = os.path.join(self.root, "src", "app.tsx")
        self.state_dir = os.path.join(self.tmp.name, "state")
        self.transcript = write_transcript(self.tmp.name, [
            user_entry("tổng sai khi có discount", request="bug-1"),
            assistant_echo(DECL_ECHO, request="bug-1"),
            tool_result(request="bug-1"),
            image_entry(request="img-1"),
        ])
        self.payload = edit_event(
            self.tsx, old="const submit = () => {};", new="const submit = async () => {};",
            cwd=self.root, transcript=self.transcript, prompt_id="img-1")

    def test_image_message_keeps_bug_classification(self):
        output = gate_output(self.payload, self.state_dir)
        self.assertEqual(decision_of(output), "deny")
        self.assertIn("Trigger", reason_of(output))

    def test_image_message_keeps_earlier_labels(self):
        transcript = write_transcript(self.tmp.name, [
            user_entry("update the order form", request="req-1"),
            assistant_echo(DECL_ECHO, request="req-1"),
            tool_result(request="req-1"),
            image_entry(request="img-1"),
        ])
        payload = edit_event(
            self.tsx, old="const submit = () => {};", new="const submit = async () => {};",
            cwd=self.root, transcript=transcript, prompt_id="img-1")
        output = gate_output(payload, self.state_dir)
        self.assertNotEqual(decision_of(output), "deny")


class RegressionFailedEcho(unittest.TestCase):
    """regression A4: an echo whose tool_result is_error=true must not unlock the gate."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "repo")
        make_repo(self.root)
        self.tsx = os.path.join(self.root, "src", "app.tsx")
        self.state_dir = os.path.join(self.tmp.name, "state")

    def test_failed_echo_does_not_unlock_via_state_store(self):
        transcript = write_transcript(self.tmp.name, [
            user_entry("update the order form"),
            assistant_echo(DECL_ECHO),
            tool_result(is_error=True),
        ])
        hook_specific(
            bash_event(DECL_ECHO, cwd=self.root, transcript=transcript,
                       session="sess-1", prompt_id="req-1"),
            self.state_dir)
        payload = edit_event(
            self.tsx, old="const submit = () => {};", new="const submit = async () => {};",
            cwd=self.root, transcript=transcript, session="sess-1", prompt_id="req-1")
        output = gate_output(payload, self.state_dir)
        self.assertEqual(decision_of(output), "deny")


if __name__ == "__main__":
    unittest.main()
