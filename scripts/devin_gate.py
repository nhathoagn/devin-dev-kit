"""fe-kit edit gate for the Devin CLI host.

Devin's hook payload already carries what the gate needs: `prompt` on UserPromptSubmit,
a stable `session_id`, and a `prompt_id` that rotates on every user message. So this
file never reads a transcript. A per-session state file remembers the latest request
(non-continuation user message) and whether it reported a bug; prompt_id scopes the
labels a request declares, so an old task's labels cannot open a later edit.

Deny uses Devin's {"decision": "block", "reason": ...} output; context goes through
hookSpecificOutput.additionalContext. Shared helpers (wording, bash_target,
label_store, project_config) are host-free and are imported unchanged.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
try:
    import wording
except Exception:
    wording = None
try:
    import bash_target
except Exception:
    bash_target = None
try:
    import label_store
except Exception:
    label_store = None
try:
    import gate_scope
except Exception:
    gate_scope = None
try:
    import project_config
except Exception:
    project_config = None
try:
    import handoff
except Exception:
    handoff = None

# The hook payload is UTF-8. Windows Python decodes stdin as cp1252 by default, which breaks Vietnamese prompts.
raw = sys.stdin.buffer.read().decode("utf-8", errors="replace").strip()
if not raw:
    sys.exit(0)
try:
    event = json.loads(raw)
except json.JSONDecodeError:
    sys.exit(0)

name = event.get("hook_event_name") or ""
prompt = event.get("prompt") or ""
tool_name = event.get("tool_name") or ""
tool_input = event.get("tool_input") or {}
session_id = event.get("session_id") or ""
prompt_id = event.get("prompt_id") or ""

path = ""
if isinstance(tool_input, dict):
    path = tool_input.get("file_path") or tool_input.get("path") or ""

cwd = ""
if isinstance(tool_input, dict):
    cwd = tool_input.get("workdir") or ""
cwd = cwd or os.environ.get("DEVIN_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

def git_commit(command, cwd):
    # (repo root, stages all tracked files) when the command runs git commit, else None.
    if not bash_target or not command:
        return None
    for tokens, _ in bash_target.shell_segments(command):
        index = bash_target.command_index(tokens)
        if index >= len(tokens) or os.path.basename(tokens[index]) != "git":
            continue
        rest = tokens[index + 1:]
        if "commit" not in rest:
            continue
        root = cwd or "."
        for position, token in enumerate(rest):
            if token == "-C" and position + 1 < len(rest):
                candidate = rest[position + 1]
                root = candidate if os.path.isabs(candidate) else os.path.join(cwd or ".", candidate)
        return os.path.abspath(root), ("-a" in rest or "--all" in rest)
    return None

def handoff_disabled(root):
    if not project_config:
        return False
    try:
        config, _ = project_config.load_config(root)
    except Exception:
        return False
    return bool(config and config.get("handoff") == "off")

def handoff_script():
    root = os.environ.get("FE_ARCH_ROOT") or os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    return os.path.join(root, "scripts", "handoff.py")

def commit_block(root, all_files):
    if not handoff or not os.path.isdir(root) or handoff_disabled(root):
        return ""
    files = handoff.staged_files(root)
    if all_files:
        files += handoff.changed_files(root)
    found = handoff.problems(root, sorted(set(files)))
    if not found:
        return ""
    return (
        "Blocked. Before a commit, write the logic handoff a person can read and debug from. "
        + " ".join(found)
        + " Write `%s` with sections Logic, Implementation, Decisions, Debug without AI, Risks, Q&A; "
          "name every staged source file; ask the user the Q&A in chat; then ask the user to run: "
          'python3 "%s" approve --root "%s". Do not run approve yourself.'
        % (handoff.HANDOFF_PATH, handoff_script(), root)
    )

declared = []
if tool_name == "exec" and isinstance(tool_input, dict):
    command = tool_input.get("command") or ""
    if name == "PreToolUse":
        commit = git_commit(command, cwd)
        if commit:
            reason = commit_block(commit[0], commit[1])
            if reason:
                print(json.dumps({"decision": "block", "reason": reason}))
                sys.exit(0)
    path = bash_target.write_target(command, cwd) if bash_target else ""
    declared = label_store.declared_lines(command) if label_store and not path else []
    # An exec command that writes no frontend file and declares no label has nothing to gate or inject.
    if not path and not declared:
        sys.exit(0)

full_path = path
if path and not os.path.isabs(path) and cwd:
    full_path = os.path.join(cwd, path)

prompt_hit = re.search(
    r"frontend|front-end|\breact\b|\bvue\b|\bsvelte\b|\.tsx\b|\.jsx\b|\.vue\b|\.svelte\b|\btsx\b|\bjsx\b|\bcomponents?\b|\bUI\b|giao diện|viết\s+(ui|frontend|component)|fe-kit|fe kit",
    prompt,
    re.I,
)
conflict_hit = re.search(
    r"conflict|<<<<<<<|merge markers?|rebase conflict|conflict.{0,30}rebase|rebase.{0,30}conflict|xung đột|xung dot|hợp nhất|hop nhat|duplicate items?|trùng(?: item| lặp)?",
    prompt,
    re.I,
)
reuse_hit = re.search(
    r"reuse|re-use|duplicat|dùng lại|dung lai|tái sử|tai su|trùng|trung(?!\s*t[âa]m)|lặp|lap lai|song song|existing (?:code|component|hook|helper|implementation)|copy (?:a |the )?(?:component|hook|helper|function)",
    prompt,
    re.I,
)
author_hit = re.search(
    r"\b(add|implement|write|create|extract|refactor|introduce|fix)\b|viết|viet |thêm |them |tách |tach |sửa |sua |bug",
    prompt,
    re.I,
)
BUG_RE = re.compile(
    r"\bbug\b|lỗi|sai khi|(?:tổng|tong|tính|tinh|hiển thị|hien thi|bị|bi) sai\b|không (?:đúng|hiển thị|hien thi|trừ|tru|chạy|chay|mở|mo)\b|màn hình trắng|man hinh trang|mất dữ liệu|mat du lieu|does not work|not working|\bbroken\b|wrong (?:total|value|result|behavior|behaviour)",
    re.I,
)
WORDING_RE = re.compile(
    r"\btypo\b|wording|chính tả|chinh ta|button label|style tweak|from blue to|đổi màu|doi mau|"
    r"\btext\b|\bcopy\b|\blabel\b|câu chữ|noi dung|nội dung",
    re.I,
)
# A strong bug signal is a symptom, not just the word "lỗi". Wording tasks often mention "lỗi".
BUG_STRONG_RE = re.compile(
    r"\bbug\b|sai khi|(?:tổng|tong|tính|tinh|hiển thị|hien thi|bị|bi) sai\b|"
    r"không (?:đúng|hiển thị|hien thi|trừ|tru|chạy|chay|mở|mo)\b|"
    r"màn hình trắng|man hinh trang|mất dữ liệu|mat du lieu|"
    r"does not work|not working|\bbroken\b|wrong (?:total|value|result|behavior|behaviour)",
    re.I,
)
META_RE = re.compile(
    r"fe-gate|fe gate|devin-gate|fe-kit|fe kit|\bplugin\b|\blexer\b|\btokenizer\b|"
    r"wording_hit|path_hit",
    re.I,
)

def bug_signal(text):
    if not text or not BUG_RE.search(text):
        return False
    if BUG_STRONG_RE.search(text):
        return True
    if WORDING_RE.search(text):
        return False
    if META_RE.search(text):
        return False
    return True

wording_hit = WORDING_RE.search(prompt)
bug_hit = bug_signal(prompt)
review_hit = re.search(
    r"review(?: the)? diff|git diff|trước commit|truoc commit|before commit|code review|soi diff",
    prompt,
    re.I,
)
path_hit = re.search(r"\.(tsx|jsx|vue|svelte)$", path, re.I)
source_hit = re.search(
    r"\.(tsx?|jsx?|mjs|cjs|vue|svelte|py|go|rs|java|kt|kts|rb|php|cs|swift)$",
    path,
    re.I,
)
GATED_EXT_RE = re.compile(r"\.(tsx|jsx|js|ts|mjs|cjs|vue|svelte|astro|mdx|py|go|rs|java|kt|kts|rb|php|cs|swift)$", re.I)

DENY_REASON = "Only a behaviorless wording or style change is exempt."
DENY_BUG_REASON = "A bug fix also needs Trigger:, Expected:, and Actual:, each with a value, from playbooks/fix-bug.md."
REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
# A Japanese IME types the full-width colon.
COLON = "[:：]"
# A label can be bold or italic, as in **Decision**: or _Decision_:.
LABEL_END = "[*_]*" + COLON
# A value starts after the colon. A comma, or a backquote right after the colon, is prose that names the field.
VALUE = r"(?:[ \t]+`?[^\s,`<]|[^\s,`<])"
REPRODUCE_LABELS = {"Trigger": "Trigger|Steps?", "Expected": "Expected", "Actual": "Actual"}
# A person can end a line with the label and put the value on the next line.
NEXT_LINE_VALUE = r"[ \t]*\n\s*(?!`|\||(?:Trigger|Steps?|Expected|Actual)\b)\S"
# A short reply continues the current task. Anything else starts a new task, so old labels do not count.
CONTINUATION_RE = re.compile(
    r"^\s*(?:ok(?:ay)?|oke|yes|yeah|yep|sure|go on|go ahead|continue|proceed|do it|"
    r"thanks|lgtm|ừ|uh|vâng|dạ|được|đồng ý|làm đi|chạy đi|tiếp tục|tiếp|"
    r"(?:ok(?:ay)?|oke|ừ|vâng|dạ|được)\s*[,.!]*\s*(?:làm đi|chạy đi|tiếp tục|tiếp)"
    r")\s*[.!…]*\s*$",
    re.I,
)

def is_continuation(text):
    return bool(CONTINUATION_RE.match(text or ""))

# --- session state -------------------------------------------------------
# prompt_id rotates on every user message, but a continuation ("ok", "làm đi")
# belongs to the same request, so the state keeps the request id of the latest
# non-continuation prompt and the labels declared under it stay valid.

def state_dir():
    return os.environ.get("FE_GATE_STATE_DIR") or os.path.join(tempfile.gettempdir(), "fe-kit-gate")

def state_path():
    key = hashlib.sha1(("devin|" + session_id).encode("utf-8")).hexdigest()
    return os.path.join(state_dir(), "devin-" + key + ".json")

def load_state():
    try:
        with open(state_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}

def save_state(data):
    try:
        os.makedirs(state_dir(), exist_ok=True)
        with open(state_path(), "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
        return True
    except OSError:
        return False

state = load_state()
request_key = state.get("request") or ""

# The user can type labels in the message itself; they count like an echo declaration.
PROMPT_LABEL_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:Runtime owner|Decision|Trigger|Steps?|Expected|Actual)[*_]*[:：].+$",
    re.I | re.M,
)

def label_session():
    return "devin-session:" + session_id if session_id else ""

def declared_texts():
    # Devin always carries a session id, so labels count only from a declaration
    # (echo command or a label line in the user's own prompt), never reply prose.
    if not label_store or not label_session():
        return []
    lines = label_store.load(label_session(), "", request_key)
    return ["\n".join(lines)] if lines else []

def has_label_value(labels, text, next_line):
    if re.search("(?:" + labels + ")" + LABEL_END + VALUE, text, re.I):
        return True
    return next_line and bool(re.search("(?:" + labels + ")[*_]*" + COLON + "?" + NEXT_LINE_VALUE, text, re.I))

def scoped_entries():
    return [("declared", text) for text in declared_texts()]

def reproduce_found():
    found = {key: False for key in REPRODUCE_LABELS}
    for role, text in scoped_entries():
        for key, labels in REPRODUCE_LABELS.items():
            if has_label_value(labels, text, next_line=role == "user"):
                found[key] = True
    return found

def reproduce_present():
    return all(reproduce_found().values())

DECISION_WORD = r"\b(reuse|extend|feature-local|shared|n/a)\b"
REUSE_HEADING_RE = re.compile(r"^\s*(?:#{1,6}\s*|[*_]{2})?\s*Reuse Decision\b", re.I)
HEADING_RE = re.compile(r"^\s*#{1,6}\s")
# Under a Reuse Decision heading, any label can carry the decision, as in "- FE side: **reuse**".
SECTION_DECISION_RE = re.compile(r"[:：]\s*[*_`]*\s*" + DECISION_WORD, re.I)
OWNER_LINE_RE = re.compile(r"Runtime owner[*_]*[:：][ \t]*[*_`]*[ \t]*([^\s,`]+)", re.I)
OWNER_PLACEHOLDER_RE = re.compile(
    r"^(?:tbd|tba|todo|to-do|none|null|nil|unknown|n/a|na|pending|placeholder|x+|\.+|\?+|-+|<.*)$",
    re.I,
)
# The decision word must follow the colon, so "Decision: do not reuse" is not a reuse decision.
DECISION_LINE_RE = re.compile(r"Decision[*_]*[:：][ \t]*[*_`]*[ \t]*" + DECISION_WORD, re.I)

def clean_label_value(value):
    return value.strip("*_` \t.,;:")

def owner_value(line):
    match = OWNER_LINE_RE.search(line)
    if not match:
        return ""
    value = clean_label_value(match.group(1))
    if OWNER_PLACEHOLDER_RE.match(value):
        return ""
    return value

def decisions_found():
    # Returns (owner found, decision found) for the current request.
    found_owner = False
    found_reuse = False
    for _, text in scoped_entries():
        in_reuse_section = False
        for line in text.splitlines():
            if REUSE_HEADING_RE.match(line):
                in_reuse_section = True
            elif HEADING_RE.match(line):
                in_reuse_section = False
            if "|" in line:
                continue
            if owner_value(line):
                found_owner = True
            if DECISION_LINE_RE.search(line):
                found_reuse = True
            elif in_reuse_section and SECTION_DECISION_RE.search(line):
                found_reuse = True
        if found_owner and found_reuse:
            break
    return found_owner, found_reuse

def decisions_present():
    return all(decisions_found())

def missing_note(bug_edit):
    # Name what the gate did not find, so the agent does not retry the same edit.
    owner, reuse = decisions_found()
    missing = []
    if not owner:
        missing.append("`Runtime owner:` with a name")
    if not reuse:
        missing.append("`Decision:` with reuse, extend, feature-local, shared, or n/a")
    if bug_edit:
        found = reproduce_found()
        missing += ["`%s:` with a value" % key for key, ok in found.items() if not ok]
    if not missing:
        return "The lines were not recorded for this request. Run the command, then retry."
    note = "Not found for the current request: " + "; ".join(missing) + ". "
    note += "Labels in reply text, thinking, or prose do not count on Devin — declare them with the echo command; labels the user types in a message also count. "
    note += (
        "Labels declared for an earlier request do not count, so declare them again for a new request. "
        + DENY_REASON + " Run the command now and retry the edit in this turn. Do not end the turn to ask the user to continue."
    )
    if tool_name == "exec":
        note += " An exec command that writes a frontend file is gated like edit. Do not route the change through exec to skip the gate."
    return note

CONFLICT_MARKER_RE = re.compile(r"^(?:<{7}|={7}|>{7}|\|{7})(?:\s|$)", re.M)

def conflict_edit():
    if tool_name != "edit" or not isinstance(tool_input, dict):
        return False
    return bool(CONFLICT_MARKER_RE.search(tool_input.get("old_string") or ""))

def conflict_lines_only():
    # A resolution that only keeps or reorders lines from the conflict block writes no new code.
    if not conflict_edit():
        return False
    old = tool_input.get("old_string") or ""
    new = tool_input.get("new_string") or ""
    if CONFLICT_MARKER_RE.search(new):
        return False
    old_lines = {line.strip() for line in old.splitlines() if not CONFLICT_MARKER_RE.match(line)}
    return all(line.strip() in old_lines for line in new.splitlines() if line.strip())

TOKEN_RE = re.compile(r"[\w$]+|[^\s\w]")

def conflict_merge_only():
    # A one-line merge that only combines tokens already present in the conflict block writes no new code.
    if not conflict_edit():
        return False
    old = tool_input.get("old_string") or ""
    new = tool_input.get("new_string") or ""
    if len(new.splitlines()) != 1 or CONFLICT_MARKER_RE.search(new):
        return False
    old_lines = "\n".join(line for line in old.splitlines() if not CONFLICT_MARKER_RE.match(line))
    old_tokens = set(TOKEN_RE.findall(old_lines))
    new_tokens = set(TOKEN_RE.findall(new))
    return bool(new_tokens) and new_tokens <= old_tokens

PATCH_PATH_RE = re.compile(r"(?m)^\s*(?:\*\*\*\s*(?:Update|Add|Delete)\s+File:|[+-]{3}\s+[ab]/)\s*([^\s]+)")

def patch_target():
    # apply_patch carries a patch body, not a file_path. Name the first product-code file it touches.
    if not isinstance(tool_input, dict):
        return ""
    text = "\n".join(str(v) for v in tool_input.values() if isinstance(v, str))
    for match in PATCH_PATH_RE.finditer(text):
        candidate = match.group(1).strip().strip('"')
        if not GATED_EXT_RE.search(candidate):
            continue
        full = candidate if os.path.isabs(candidate) or not cwd else os.path.join(cwd, candidate)
        if gate_scope is None or gate_scope.in_scope(full, cwd):
            return full
    return ""

def edit_pairs():
    # Devin's edit takes one old/new pair. write and apply_patch have none and stay gated.
    if tool_name != "edit":
        return []
    old = tool_input.get("old_string")
    new = tool_input.get("new_string")
    if isinstance(old, str) and isinstance(new, str):
        return [(old, new)]
    return []

def wording_exempt():
    # Fail closed: a missing lexer, an unreadable file, or an unknown extension is gated.
    if wording is None or os.environ.get("FE_GATE_WORDING") == "off":
        return False
    if tool_name != "edit" or conflict_edit():
        return False
    pairs = [(old, new) for old, new in edit_pairs() if old and old != new]
    if not pairs:
        return False
    for old, new in pairs:
        if CONFLICT_MARKER_RE.search(old) or CONFLICT_MARKER_RE.search(new):
            return False
    if not full_path or not os.path.isfile(full_path):
        return False
    if not wording.dialect_for(full_path):
        return False
    try:
        if os.path.getsize(full_path) > wording.MAX_SOURCE_BYTES:
            return False
        with open(full_path, encoding="utf-8", errors="strict") as handle:
            source = handle.read()
    except (OSError, UnicodeDecodeError):
        return False
    try:
        return wording.edits_are_wording(source, pairs, wording.dialect_for(full_path))
    except Exception:
        return False

if tool_name == "apply_patch" and not path:
    path = patch_target()
    full_path = path

gated_view = (
    tool_name in ("edit", "write", "apply_patch", "exec")
    and GATED_EXT_RE.search(path)
    and (tool_name == "exec" or gate_scope is None or gate_scope.in_scope(full_path, cwd))
    and not wording_exempt()
    and not conflict_lines_only()
    and not conflict_merge_only()
)

def gate_open(bug_edit):
    return decisions_present() and not (bug_edit and not reproduce_present())

def find_git_dir(start):
    current = os.path.abspath(start) if start else ""
    while current and os.path.isdir(current):
        candidate = os.path.join(current, ".git")
        if os.path.isdir(candidate):
            return candidate
        if os.path.isfile(candidate):
            try:
                with open(candidate, encoding="utf-8", errors="ignore") as handle:
                    first = handle.readline().strip()
                if first.startswith("gitdir:"):
                    target = first.split(":", 1)[1].strip()
                    return target if os.path.isabs(target) else os.path.join(current, target)
            except OSError:
                return None
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent
    return None

def repo_in_conflict(start):
    git_dir = find_git_dir(start)
    if not git_dir:
        return False
    return any(
        os.path.exists(os.path.join(git_dir, marker))
        for marker in ("MERGE_HEAD", "rebase-merge", "rebase-apply")
    )

def file_has_markers(target):
    if not target or not os.path.isfile(target):
        return False
    try:
        with open(target, encoding="utf-8", errors="ignore") as handle:
            saw_open = False
            saw_close = False
            for line in handle:
                if line.startswith("<<<<<<<"):
                    saw_open = True
                elif line.startswith(">>>>>>>"):
                    saw_close = True
                if saw_open and saw_close:
                    return True
    except OSError:
        return False
    return False

def plugin_root():
    return os.environ.get("FE_ARCH_ROOT") or os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

def load_rule(filename):
    rule_path = os.path.join(plugin_root(), "rules", filename)
    text = open(rule_path, encoding="utf-8").read()
    return re.sub(r"^---\n.*?\n---\n*", "", text, count=1, flags=re.S).strip()

def project_root(start):
    for env_root in (os.environ.get("DEVIN_PROJECT_DIR"), os.environ.get("CLAUDE_PROJECT_DIR")):
        if env_root and os.path.isdir(env_root):
            return env_root
    root = gate_scope.repo_root(start) if gate_scope and start else None
    return root or start or ""

def project_rules_command(mode):
    script = os.path.join(plugin_root(), "scripts", "project_config.py").replace("\\", "/")
    root = (project_root(cwd) or ".").replace("\\", "/")
    return 'python3 "%s" --root "%s" --mode %s' % (script, root, mode)

def review_context():
    playbook = os.path.join(plugin_root(), "skills", "fe-kit", "playbooks", "review-diff.md")
    return (load_rule("review-diff.md") + "\n\nPlaybook path: " + playbook
            + "\n\nReviewer profile: fe-kit:reviewer (a read-only Devin subagent; spawn it with run_subagent)."
            + "\n\nProject rules command: " + project_rules_command("review"))

def project_config_context():
    # Only a repo that wrote a config gets this line, because the fallback search needs no reminder.
    if not project_config or not os.path.isfile(os.path.join(project_root(cwd), project_config.CONFIG_PATH)):
        return ""
    return ("This repo has %s. Before the first edit, run `%s --files <each file you will change>` "
            "and read each `read:` line. Use its `gate:` commands to verify."
            % (project_config.CONFIG_PATH, project_rules_command("author")))

def rule_bundle():
    return load_rule("reuse-duplication.md") + "\n\n" + load_rule("modules.md") + "\n\n" + load_rule("comments.md")

def text_has_frontend(text):
    if not text:
        return False
    if re.search(r"skill://fe-kit|Runtime owner:|Reuse Decision", text):
        return True
    return bool(re.search(
        r"frontend|front-end|\breact\b|\bvue\b|\bsvelte\b|\.tsx\b|\.jsx\b|\.vue\b|\.svelte\b|\btsx\b|\bjsx\b|\bcomponents?\b|\bUI\b|giao diện|viết\s+(ui|frontend|component)",
        text,
        re.I,
    ))

def session_has_frontend():
    if state.get("frontend"):
        return True
    return text_has_frontend(event.get("summary") or "")

def run_repo_rules(start, target):
    root = project_root(start)
    script = os.path.join(root, ".claude", "rules.sh")
    if not os.path.isfile(script):
        script = os.path.join(root, ".devin", "rules.sh")
    if not (os.path.isfile(script) and os.access(script, os.X_OK)):
        return ""
    try:
        result = subprocess.run(
            ["sh", script, target or ""],
            cwd=root or None,
            capture_output=True,
            text=True,
            timeout=150,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "repo rules.sh failed: %s" % exc
    if result.returncode == 0:
        return ""
    lines = ((result.stdout or "") + (result.stderr or "")).splitlines()[:40]
    return "VI PHẠM RULE / LỖI CHECK. Sửa ngay trước khi làm tiếp:\n" + "\n".join(lines)

def emit(event_name, bodies):
    bodies = [b for b in bodies if b]
    if not bodies:
        sys.exit(0)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": "\n\n".join(bodies),
        }
    }))

def fail(message):
    sys.stderr.write(message.rstrip() + "\n")
    sys.exit(2)

# --- UserPromptSubmit ----------------------------------------------------
if name == "UserPromptSubmit":
    if not is_continuation(prompt):
        # A new request: labels scope to its prompt_id, and its text decides bug mode.
        request_key = prompt_id or hashlib.sha1(prompt.strip().encode("utf-8")).hexdigest()
        state["request"] = request_key
        state["prompt"] = prompt
        state["bug"] = bool(bug_hit)
        if prompt_hit or bug_hit:
            state["frontend"] = True
    prompt_labels = PROMPT_LABEL_RE.findall(prompt)
    if prompt_labels and label_store and label_session():
        label_store.save(label_session(), "", request_key, prompt_labels)
    save_state(state)

    bodies = []
    if prompt_hit or bug_hit:
        bodies.append(load_rule("fe-implementation.md"))
        if project_config_context():
            bodies.append(project_config_context())
    if (prompt_hit or reuse_hit or author_hit or bug_hit) and not (wording_hit and not bug_hit):
        bodies.append(rule_bundle())
    if prompt_hit or review_hit or author_hit:
        bodies.append(review_context())
    if conflict_hit or repo_in_conflict(cwd):
        bodies.append(load_rule("conflict-fix.md"))
    emit(name, bodies)

# --- PreToolUse: label declaration --------------------------------------
# An exec command of one plain echo/printf declares the labels for this request.
if name == "PreToolUse" and tool_name == "exec" and not path:
    if declared:
        saved = label_store.save(label_session(), "", request_key, declared) if label_store else False
        note = "fe-kit recorded these labels for this request: %s. Retry the edit now." % "; ".join(declared)
        if not saved:
            note = "fe-kit could not save the labels, because the state folder is not writable. Tell the user."
        emit(name, [note])
    sys.exit(0)

def declare_command(bug_edit):
    target = os.path.basename(path) or "this file"
    parts = ['"Runtime owner: <the component or hook that runs %s>"' % target,
             '"Decision: <reuse|extend|feature-local|shared|n/a>"']
    if bug_edit:
        parts += ['"Trigger: <steps>"', '"Expected: <value>"', '"Actual: <value>"']
    return "echo " + " ".join(parts)

# --- PreToolUse: the edit gate -------------------------------------------
bug_edit = gated_view and not conflict_edit() and bool(state.get("bug"))
if name == "PreToolUse" and gated_view:
    if path:
        state["frontend"] = True
        save_state(state)
    if not gate_open(bug_edit):
        reason = (
            "Blocked. Run this exec command with each <...> replaced by a real value, then retry the same edit: "
            + declare_command(bug_edit) + " . "
        )
        if bug_edit:
            reason += DENY_BUG_REASON + " "
        reason += missing_note(bug_edit)
        print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)
elif name == "PreToolUse" and path and source_hit and tool_name in ("edit", "write", "apply_patch"):
    # A non-gated source edit still makes the session's diff reviewable.
    if not state.get("edited"):
        state["edited"] = True
        save_state(state)

# --- PostToolUse ----------------------------------------------------------
if name == "PostToolUse":
    errors = []
    if file_has_markers(full_path):
        errors.append(
            "Conflict markers remain in %s. Finish the resolution before the next edit." % full_path
        )
    if full_path:
        rule_error = run_repo_rules(cwd, full_path)
        if rule_error:
            errors.append(rule_error)
    if errors:
        fail("\n".join(errors))
    if source_hit and state.get("bug"):
        emit(name, [
            "Write or update the unit test beside the owner. It must fail on Actual and pass on Expected. For a text check, include undefined, null, empty, leading space, and trailing space. Then re-run that test and the reproduction. Hand this diff to the fe-kit:reviewer subagent or a fresh context that reads playbooks/review-diff.md in the fe-kit skill. Do not write the verdict."
        ])
    sys.exit(0)

# --- SessionStart (resume) / PostCompaction -------------------------------
# Devin fires PostCompaction after a summary, and SessionStart on every resume.
# The rules may still be in context; what compaction loses is this session's
# gate mechanics, so the reminder names them instead of repeating the rules.
if name == "PostCompaction" or (name == "SessionStart" and event.get("source") == "resume"):
    if session_has_frontend():
        bodies = [
            "fe-kit gate is active. Before editing a frontend file, declare the labels with one exec echo command "
            "(`Runtime owner:`, `Decision:`, plus `Trigger:`/`Expected:`/`Actual:` for a bug fix). "
            "Read the fe-kit skill before a non-trivial frontend edit. "
            "Do not grade a diff you wrote — a fresh reviewer reads the fe-kit review-diff playbook "
            "for any source file, not only frontend; spawn it with the playbook path.",
            review_context(),
        ]
        if project_config_context():
            bodies.append(project_config_context())
        emit(name, bodies)
    elif state.get("edited"):
        emit(name, [
            "Do not grade a diff you wrote — a fresh reviewer reads the fe-kit review-diff playbook "
            "for any source file, not only frontend; spawn it with the playbook path.",
            review_context(),
        ])
    sys.exit(0)

# --- PreToolUse context injection -----------------------------------------
bodies = []
if name == "PreToolUse":
    if path_hit:
        bodies.append(load_rule("fe-implementation.md"))
    if source_hit:
        bodies.append(rule_bundle())
        bodies.append(review_context())
    if file_has_markers(full_path) or repo_in_conflict(cwd):
        bodies.append(load_rule("conflict-fix.md"))

emit(name, bodies)
