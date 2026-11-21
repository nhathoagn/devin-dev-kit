import glob
import json
import os
import re
import sys
import subprocess

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
path = ""
if isinstance(tool_input, dict):
    path = tool_input.get("file_path") or tool_input.get("path") or ""

cwd = event.get("cwd") or ""

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

if tool_name == "Bash" and isinstance(tool_input, dict):
    command = tool_input.get("command") or ""
    if name == "PreToolUse":
        commit = git_commit(command, cwd)
        if commit:
            reason = commit_block(commit[0], commit[1])
            if reason:
                print(json.dumps({
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    }
                }))
                sys.exit(0)
    path = bash_target.write_target(command, cwd) if bash_target else ""
    declared = label_store.declared_lines(command) if label_store and not path else []
    if not path and not declared:
        # A rejected declaration must say why, or the agent runs it again and reads the same deny.
        if label_store and label_store.LABEL_RE.search(command):
            note = "fe-kit could not read a declaration from this command. " + (
                label_store.declaration_problem(command)
                or 'Run one plain echo with quoted labels: echo "Runtime owner: OrderForm" "Decision: reuse"'
            )
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": note}}))
        sys.exit(0)

full_path = path
if path and not os.path.isabs(path) and cwd:
    full_path = os.path.join(cwd, path)

prompt_hit = re.search(
    r"frontend|front-end|\breact\b|\bvue\b|\bsvelte\b|\.tsx\b|\.jsx\b|\.vue\b|\.svelte\b|\btsx\b|\bjsx\b|\bcomponents?\b|\bUI\b|giao diện|viết\s+(ui|frontend|component)|fe-kit|fe kit|skill://fe-kit",
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
    r"fe-gate|fe gate|fe-kit|fe kit|skill://fe-kit|\bplugin\b|\blexer\b|\btokenizer\b|"
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
def transcript_lines(path):
    if not path or not os.path.isfile(path):
        return []
    try:
        handle = open(path, encoding="utf-8", errors="ignore")
    except OSError:
        return []
    with handle:
        return handle.readlines()

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
    r"^\s*(?:"
    r"ok(?:ay|i|ie)?(?:\s+(?:nhé|nha|nhe|bạn|ạ|đi|làm tiếp(?: đi)?))?|"
    r"oke|yes|yeah|yep|sure|go on|go ahead|continue|proceed|do it|"
    r"thanks|lgtm|ừ|uh|vâng|dạ|đồng ý|"
    r"được(?:\s+(?:nhé|nha|nhe|ạ|rồi|đấy))?|"
    r"(?:cứ\s+)?(?:làm|đi)?\s*tiếp(?:\s*(?:đi|nhé|nha|tục))?|"
    r"(?:làm|chạy|sửa|đi)\s+(?:tiếp|đi)(?:\s*(?:đi|nhé))?"
    r")\s*[.!…]*\s*$",
    re.I,
)

def entry_texts(entry):
    message = entry.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    # The transcript keeps the thinking text that the user sees as a summary, so it counts as authored too.
    texts = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            texts.append(block.get("text") or "")
        elif block.get("type") == "thinking":
            texts.append(block.get("thinking") or "")
    return texts

def entry_blocks(entry):
    message = entry.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]

def entry_bash_calls(entry):
    calls = []
    for block in entry_blocks(entry):
        if block.get("type") != "tool_use" or block.get("name") != "Bash":
            continue
        tool_input = block.get("input")
        if isinstance(tool_input, dict):
            calls.append((block.get("id") or "", tool_input.get("command") or ""))
    return calls

def entry_tool_results(entry):
    results = []
    for block in entry_blocks(entry):
        if block.get("type") == "tool_result":
            results.append((block.get("tool_use_id") or "", block.get("is_error") is True))
    return results

def entry_request_id(entry):
    # Claude Code writes the prompt UUID on every entry of a turn. uuid is the older stable id.
    for key in ("promptId", "uuid"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return ""

_TRANSCRIPT_CACHE = {}

def parse_transcript(path):
    # A line the host is still writing is not a declaration. It is not authored text either.
    # One hook process parses the same file many times, so the parsed list is cached by mtime and size.
    if not path or not os.path.isfile(path):
        return []
    try:
        stat = os.stat(path)
    except OSError:
        return []
    key = (path, stat.st_mtime_ns, stat.st_size)
    cached = _TRANSCRIPT_CACHE.get(key)
    if cached is not None:
        return cached
    entries = []
    for line in transcript_lines(path):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    if len(_TRANSCRIPT_CACHE) > 8:
        _TRANSCRIPT_CACHE.clear()
    _TRANSCRIPT_CACHE[key] = entries
    return entries

def transcript_signature(path):
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size

# The host writes these as user entries, but no person typed them. They do not start a request.
HOST_NOTICE_RE = re.compile(
    r"<(?:task-notification|command-name|command-message|command-args|local-command-[a-z-]+|"
    r"bash-input|bash-stdout|bash-stderr|bash-exit-code|total_tokens|user-prompt-submit-hook|"
    r"post-tool-use-hook|mcp-resource-update|mcp-polling-update|agent-message|teammate-message|"
    r"cross-session-message|ide_selection|ide_opened_file|wake|tick|slack-ping)\b"
)
COMMAND_ARGS_RE = re.compile(r"<command-args>(.*?)</command-args>", re.S)

def typed_by_person(entry):
    origin = entry.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return False
    text = REMINDER_RE.sub("", "\n".join(entry_texts(entry)))
    return not HOST_NOTICE_RE.search(text)

def person_texts(entry):
    # A slash command carries the only person-typed text in its <command-args>.
    if typed_by_person(entry):
        texts = entry_texts(entry)
        if texts:
            return texts
        if any(block.get("type") == "image" for block in entry_blocks(entry)):
            return ["[image]"]
        return []
    match = COMMAND_ARGS_RE.search(REMINDER_RE.sub("", "\n".join(entry_texts(entry))))
    return [match.group(1)] if match and match.group(1).strip() else []

def clean_text(text):
    return REMINDER_RE.sub("", text).replace(DENY_REASON, "").replace(DENY_BUG_REASON, "")

def authored_entries(path, roles):
    # Only text a person typed or Claude wrote, as (role, text) in transcript order.
    # Tool output, reminders, and hook notes are not authored.
    entries = []
    for entry in parse_transcript(path):
        if entry.get("type") not in roles or entry.get("isMeta"):
            continue
        texts = person_texts(entry) if entry.get("type") == "user" else entry_texts(entry)
        # A compact summary is a user entry that no person typed. Its text counts, but it is not a request.
        role = "summary" if entry.get("isCompactSummary") else entry.get("type")
        for text in texts:
            text = clean_text(text)
            if text.strip():
                entries.append((role, text))
    return entries

def is_continuation(text):
    # "ok", "làm đi", and an interrupt continue the current task. Everything else starts one.
    if text.lstrip().startswith("[Request interrupted"):
        return True
    return bool(CONTINUATION_RE.match(text))

def request_scope(path):
    # Labels count from the latest task on, so labels for an earlier task do not open a later one.
    entries = authored_entries(path, ("user", "assistant"))
    for index in range(len(entries) - 1, -1, -1):
        role, text = entries[index]
        if role == "user" and not is_continuation(text):
            return entries[index:]
    return entries

def latest_user_request(path):
    # (text, request id) of the latest person message that starts a request.
    for entry in reversed(parse_transcript(path)):
        if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isCompactSummary"):
            continue
        texts = [clean_text(text) for text in person_texts(entry)]
        texts = [text for text in texts if text.strip()]
        if not texts or any(is_continuation(text) for text in texts):
            continue
        text = "\n".join(texts)
        return text, (entry_request_id(entry) or text)
    return "", ""

def latest_user_text(path):
    return latest_user_request(path)[0]

def user_is_bug(path):
    # The latest task decides, so an old bug report does not gate later work.
    return bug_signal(latest_user_text(path))

def has_label_value(labels, text, next_line):
    if re.search("(?:" + labels + ")" + LABEL_END + VALUE, text, re.I):
        return True
    return next_line and bool(re.search("(?:" + labels + ")[*_]*" + COLON + "?" + NEXT_LINE_VALUE, text, re.I))

def reproduce_found():
    found = {key: False for key in REPRODUCE_LABELS}
    for role, text in scoped_entries():
        for key, labels in REPRODUCE_LABELS.items():
            if has_label_value(labels, text, next_line=role == "user"):
                found[key] = True
    return found

def reproduce_present(path):
    return all(reproduce_found().values())

def subagent_transcript():
    # Inside a subagent, transcript_path is the main session. The subagent writes its own text to
    # <session>/subagents/agent-<id>.jsonl, so read that file too when the payload names the agent.
    explicit = event.get("agent_transcript_path") or ""
    if explicit and os.path.isfile(explicit):
        return explicit
    agent_id = event.get("agent_id") or ""
    main = event.get("transcript_path") or ""
    if not agent_id or not main:
        return ""
    session_dir = os.path.splitext(main)[0]
    candidate = os.path.join(session_dir, "subagents", "agent-%s.jsonl" % agent_id)
    if os.path.isfile(candidate):
        return candidate
    # A workflow-spawned agent lives in subagents/workflows/<run>/agent-<id>.jsonl.
    matches = glob.glob(os.path.join(session_dir, "subagents", "**", "agent-%s.jsonl" % agent_id), recursive=True)
    return matches[0] if matches else ""

def label_session():
    # omp writes a new transcript file on every call, so the session id comes first.
    session = event.get("session_id") or ""
    if session:
        return "session:" + session
    transcript = event.get("transcript_path") or ""
    return "transcript:" + os.path.normcase(os.path.abspath(transcript)) if transcript else ""

def payload_prompt_id():
    # Claude Code sends one UUID per user prompt on every hook call of that turn.
    value = event.get("prompt_id")
    return value if isinstance(value, str) and value else ""

def own_request_id(path):
    return payload_prompt_id() or latest_user_request(path)[1]

def request_boundary(entries):
    boundary = 0
    for index, entry in enumerate(entries):
        if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isCompactSummary"):
            continue
        texts = [clean_text(text) for text in person_texts(entry)]
        texts = [text for text in texts if text.strip()]
        if texts and not any(is_continuation(text) for text in texts):
            boundary = index
    return boundary

def transcript_declarations(path, request_id):
    # A declaration counts only when its prompt matches and the echo actually ran.
    if not label_store or not request_id or not path or not os.path.isfile(path):
        return []
    entries = parse_transcript(path)
    success = set()
    for entry in entries:
        for tool_id, is_error in entry_tool_results(entry):
            if not is_error:
                success.add(tool_id)
    boundary = request_boundary(entries)
    lines = []
    for index, entry in enumerate(entries):
        if entry.get("type") != "assistant":
            continue
        item_id = entry_request_id(entry)
        if item_id:
            # The prompt UUID orders the turn even when the host flushed the prompt line after the echo.
            if item_id != request_id:
                continue
        elif index < boundary:
            continue
        for tool_id, command in entry_bash_calls(entry):
            if tool_id in success:
                lines.extend(label_store.declared_lines(command))
    return lines

def declared_texts():
    # Labels from an echo declaration of the latest request. A subagent also sees the main agent's labels.
    if not label_store:
        return []
    main = event.get("transcript_path") or ""
    own = event.get("agent_id") or ""
    own_request = own_request_id(main)
    main_request = latest_user_request(main)[1] if own else own_request
    agent_ids = [""]
    if own:
        agent_ids.append(own)
    texts = []
    for agent_id in agent_ids:
        request = own_request if agent_id else main_request
        lines = label_store.load(label_session(), agent_id, request)
        if lines:
            texts.append("\n".join(lines))
    transcripts = [(main, main_request)]
    own_transcript = subagent_transcript() if own else ""
    if own_transcript:
        transcripts.append((own_transcript, own_request))
    for transcript, request in transcripts:
        lines = transcript_declarations(transcript, request)
        if lines:
            texts.append("\n".join(lines))
    return texts

def declared_only():
    # With a session id, Claude's labels count only from a declaration.
    # The hook can read the transcript before the host writes the reply text.
    return label_store is not None and bool(event.get("session_id"))

def scoped_entries():
    entries = []
    for transcript in (event.get("transcript_path") or "", subagent_transcript()):
        if transcript and os.path.isfile(transcript):
            entries.extend(request_scope(transcript))
    if declared_only():
        # Text a person typed and a compact summary are in the transcript before the hook runs.
        entries = [(role, text) for role, text in entries if role != "assistant"]
    entries.extend(("declared", text) for text in declared_texts())
    return entries

DECISION_WORD = r"\b(reuse|extend|feature-local|shared|n/a)\b"
REUSE_HEADING_RE = re.compile(r"^\s*(?:#{1,6}\s*|[*_]{2})?\s*Reuse Decision\b", re.I)
HEADING_RE = re.compile(r"^\s*#{1,6}\s")
# Under a Reuse Decision heading, any label can carry the decision, as in "- FE side: **reuse**".
SECTION_DECISION_RE = re.compile(r"[:：]\s*[*_`]*\s*" + DECISION_WORD, re.I)
OWNER_LINE_RE = re.compile(r"Runtime owner[*_]*[:：][ \t]*[*_`]*[ \t]*([^\s,`]+)", re.I)
OWNER_PLACEHOLDER_RE = re.compile(
    r"^(?:tbd\w*|tba|todo|to-do|none|no[- ]?one|nobody|null|nil|unknown|n/?a|na|pending|placeholder|"
    r"not[- ]?applicable|see|the|this|that|below|above|same|\$.*|%s|x+|\.+|\?+|-+|<.*)$",
    re.I,
)
# The decision word must follow the colon, so "Decision: do not reuse" is not a reuse decision.
DECISION_LINE_RE = re.compile(r"Decision[*_]*[:：][ \t]*[*_`]*[ \t]*" + DECISION_WORD, re.I)
# A menu of the allowed values is the template, not a decision.
DECISION_MENU_RE = re.compile(
    r"\b(?:reuse|extend|feature-local|shared|n/a)\b\s*[/,|]\s*(?:reuse|extend|feature-local|shared|n/a)\b",
    re.I,
)

def clean_label_value(value):
    return value.strip("*_` \t.,;:()[]{}")

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
            if line.lstrip().startswith("|"):
                continue
            if owner_value(line):
                found_owner = True
            menu = DECISION_MENU_RE.search(line)
            if not menu and DECISION_LINE_RE.search(line):
                found_reuse = True
            elif not menu and in_reuse_section and SECTION_DECISION_RE.search(line):
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
        return "The lines were not in the transcript when the hook read it. Run the command, then retry."
    note = "Not found after the latest request: " + "; ".join(missing) + ". "
    if declared_only():
        note += "Labels in the reply text, in thinking, or in prose do not count. "
    else:
        note += ("This payload has no session id, so a reply-text line such as `Runtime owner: <name>` also counts. "
                 "Thinking, prose, and a table row do not count. ")
    note += (
        "Labels written before the latest user message do not count, so declare them again for this request. "
        + DENY_REASON + " Run the command now and retry the edit in this turn. Do not end the turn to ask the user to continue."
    )
    if tool_name == "Bash":
        note += " A Bash command that writes a frontend file is gated like Edit. Do not route the change through Bash to skip the gate."
    return note

CONFLICT_MARKER_RE = re.compile(r"^(?:<{7}|={7}|>{7}|\|{7})(?:\s|$)", re.M)

def conflict_edit():
    if tool_name != "Edit" or not isinstance(tool_input, dict):
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

GATED_EXT_RE = re.compile(r"\.(tsx|jsx|js|mjs|cjs|vue|svelte|astro|mdx)$", re.I)

def edit_pairs():
    # Edit has one pair. MultiEdit has one pair per edit. A path-only payload has none and stays gated.
    if tool_name == "Edit":
        old = tool_input.get("old_string")
        new = tool_input.get("new_string")
        if isinstance(old, str) and isinstance(new, str):
            return [(old, new)]
        return []
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits")
        if not isinstance(edits, list):
            return []
        pairs = []
        for edit in edits:
            if not isinstance(edit, dict):
                continue
            old = edit.get("old_string")
            new = edit.get("new_string")
            if isinstance(old, str) and isinstance(new, str):
                pairs.append((old, new))
        return pairs
    return []

def wording_exempt():
    # Fail closed: a missing lexer, an unreadable file, or an unknown extension is gated.
    if wording is None or os.environ.get("FE_GATE_WORDING") == "off":
        return False
    if tool_name not in ("Edit", "MultiEdit") or conflict_edit():
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

gated_view = (
    tool_name in ("Write", "Edit", "MultiEdit", "Bash")
    and GATED_EXT_RE.search(path)
    and not wording_exempt()
    and not conflict_lines_only()
    and not conflict_merge_only()
)

def gate_open(bug_edit):
    return decisions_present() and not (bug_edit and not reproduce_present(event.get("transcript_path") or ""))

def gate_open_after_flush(bug_edit):
    # Claude Code can write the reply text of the current turn after this hook reads the transcript.
    # Read again for a short time before a deny, but only when the transcript actually changed.
    import time
    if os.environ.get("FE_GATE_NO_FLUSH") == "1" or declared_only():
        return gate_open(bug_edit)
    if gate_open(bug_edit):
        return True
    transcript = event.get("transcript_path") or ""
    signature = transcript_signature(transcript)
    for _ in range(FLUSH_RETRIES):
        time.sleep(FLUSH_WAIT_SECONDS)
        current = transcript_signature(transcript)
        if current == signature:
            continue
        signature = current
        if gate_open(bug_edit):
            return True
    return False

FLUSH_RETRIES = 10
FLUSH_WAIT_SECONDS = 0.3

# A conflict resolution is a merge, not a bug fix, even when the user said the merge failed.
if name == "PreToolUse" and tool_name == "Bash" and not path:
    # A declaration is allowed. Its labels are saved for the gated edits of the same request.
    transcript = event.get("transcript_path") or ""
    saved = label_store.save(label_session(), event.get("agent_id") or "", own_request_id(transcript), declared)
    note = "fe-kit recorded these labels for this request: %s. Retry the edit now." % "; ".join(declared)
    if not saved and declared_only():
        note = "fe-kit could not save the labels, because the state folder is not writable. Tell the user."
    elif not saved:
        note = "fe-kit could not save the labels, because the payload has no session. Write them in the reply text."
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": note}}))
    sys.exit(0)

def declare_command(bug_edit):
    target = os.path.basename(path) or "this file"
    parts = ['"Runtime owner: <the component or hook that runs %s>"' % target,
             '"Decision: <reuse|extend|feature-local|shared|n/a>"']
    if bug_edit:
        parts += ['"Trigger: <steps>"', '"Expected: <value>"', '"Actual: <value>"']
    return "echo " + " ".join(parts)

bug_edit = gated_view and not conflict_edit() and user_is_bug(event.get("transcript_path") or "")
if name == "PreToolUse" and gated_view and not gate_open_after_flush(bug_edit):
    # The command comes first, because an agent follows "run X" more reliably than "write text".
    reason = (
        "Blocked. Run this Bash command with each <...> replaced by a real value, then retry the same edit: "
        + declare_command(bug_edit) + " . "
    )
    if bug_edit:
        reason += DENY_BUG_REASON + " "
    reason += missing_note(bug_edit)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)

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
    path = os.path.join(plugin_root(), "rules", filename)
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError):
        return ""
    return re.sub(r"^---\n.*?\n---\n*", "", text, count=1, flags=re.S).strip()

def project_rules_command(mode):
    script = os.path.join(plugin_root(), "scripts", "project_config.py").replace("\\", "/")
    root = (project_root(cwd) or ".").replace("\\", "/")
    return 'python3 "%s" --root "%s" --mode %s' % (script, root, mode)

def review_context():
    playbook = os.path.join(plugin_root(), "skills", "fe-kit", "playbooks", "review-diff.md")
    return (load_rule("review-diff.md") + "\n\nPlaybook path: " + playbook
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

def transcript_has_frontend(event):
    if text_has_frontend(event.get("compact_summary") or ""):
        return True
    transcript = event.get("transcript_path") or ""
    if not transcript or not os.path.isfile(transcript):
        return False
    try:
        with open(transcript, encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if text_has_frontend(line):
                    return True
    except OSError:
        return False
    return False

CODE_EDIT_RE = re.compile(
    r'"file_path"\s*:\s*"[^"]*\.(tsx?|jsx?|mjs|cjs|vue|svelte|py|go|rs|java|kt|kts|rb|php|cs|swift)"',
    re.I,
)

def transcript_has_code(event):
    # A code-editing session that never mentioned frontend still owes a fresh-eyes review.
    if transcript_has_frontend(event):
        return True
    transcript = event.get("transcript_path") or ""
    if not transcript or not os.path.isfile(transcript):
        return False
    try:
        with open(transcript, encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if CODE_EDIT_RE.search(line):
                    return True
    except OSError:
        return False
    return False

def project_root(start):
    env_root = os.environ.get("CLAUDE_PROJECT_DIR") or ""
    if env_root and os.path.isdir(env_root):
        return env_root
    current = os.path.abspath(start) if start else ""
    while current and os.path.isdir(current):
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return start or ""

def run_repo_rules(start, target):
    root = project_root(start)
    script = os.path.join(root, ".claude", "rules.sh")
    if not (os.path.isfile(script) and os.access(script, os.X_OK)):
        return ""
    try:
        result = subprocess.run(
            ["sh", script, target or ""] if os.name == "nt" else [script, target or ""],
            cwd=root or None,
            capture_output=True,
            text=True,
            timeout=150,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ".claude/rules.sh failed: %s" % exc
    if result.returncode == 0:
        return ""
    lines = ((result.stdout or "") + (result.stderr or "")).splitlines()[:40]
    return "VI PHẠM RULE / LỖI CHECK. Sửa ngay trước khi làm tiếp:\n" + "\n".join(lines)

def emit(event_name, bodies):
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

if name == "PreCompact":
    if transcript_has_code(event):
        sys.stdout.write(
            "Keep these rules in the summary. Read skill://fe-kit before a non-trivial frontend edit. "
            "Keep the review rule in the summary. Do not grade a diff you wrote — "
            "a fresh reviewer reads the fe-kit review-diff playbook for any source file, not only frontend. "
            "A different job goes in a new file, per rules/modules.md. "
            "Keep any Architecture ownership and Reuse Decision already recorded.\n"
        )
    sys.exit(0)

if name == "PostToolUse":
    errors = []
    if file_has_markers(full_path):
        errors.append(
            "Conflict markers remain in %s. Finish the resolution before the next edit." % full_path
        )
    rule_error = run_repo_rules(cwd, full_path) if full_path else ""
    if rule_error:
        errors.append(rule_error)
    if errors:
        fail("\n".join(errors))
    if source_hit and user_is_bug(event.get("transcript_path") or ""):
        emit(name, [
            "Write or update the unit test beside the owner. It must fail on Actual and pass on Expected. For a text check, include undefined, null, empty, leading space, and trailing space. Then re-run that test and the reproduction. Hand this diff to fe-kit:reviewer or a fresh context that reads skill://fe-kit/playbooks/review-diff.md. Do not write the verdict."
        ])
    sys.exit(0)

bodies = []
if name == "SessionStart" and event.get("source") == "compact" and transcript_has_code(event):
    if transcript_has_frontend(event):
        bodies.append(load_rule("fe-implementation.md"))
    bodies.append(rule_bundle())
    bodies.append(review_context())
    if project_config_context():
        bodies.append(project_config_context())
elif name == "UserPromptSubmit":
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
elif name == "PreToolUse":
    if path_hit:
        bodies.append(load_rule("fe-implementation.md"))
    if source_hit:
        bodies.append(rule_bundle())
        bodies.append(review_context())
    if file_has_markers(full_path) or repo_in_conflict(cwd):
        bodies.append(load_rule("conflict-fix.md"))

emit(name, bodies)
