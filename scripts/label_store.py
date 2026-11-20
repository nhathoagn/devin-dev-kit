"""Labels an agent declares with one plain `echo` or `printf` Bash command.

The hook payload carries the command at call time, so a declaration does not depend on when the
host writes reply text to the transcript, and it survives a thinking block that the transcript drops.
"""
import hashlib
import json
import os
import re
import shlex
import tempfile

DECLARE_RE = re.compile(r"^\s*(?:echo|printf)(?:\s|$)")
LABEL_RE = re.compile(r"(?:Runtime owner|Decision|Trigger|Steps?|Expected|Actual)[*_]*[:：]", re.I)
OPERATOR_RE = re.compile(r"^[();<>|&]+$")

def declared_lines(command):
    # Only one plain echo or printf counts. A pipe, a redirect, a chain, or a substitution is not a declaration.
    if not command or not DECLARE_RE.match(command) or not LABEL_RE.search(command):
        return []
    if "`" in command or "$(" in command:
        return []
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []
    if any(OPERATOR_RE.match(token) for token in tokens):
        return []
    lines = []
    for token in tokens[1:]:
        for line in token.replace("\\n", "\n").splitlines():
            if LABEL_RE.search(line):
                lines.append(line.strip())
    return lines

def _state_path(session, agent_id):
    # The session is the host session id, or the transcript path when the host sends no id.
    root = os.environ.get("FE_GATE_STATE_DIR") or os.path.join(tempfile.gettempdir(), "fe-kit-gate")
    key = "%s|%s" % (session, agent_id or "")
    return os.path.join(root, hashlib.sha1(key.encode("utf-8")).hexdigest() + ".json")

def _request_id(request_text):
    return hashlib.sha1((request_text or "").strip().encode("utf-8")).hexdigest()

def _read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}

def save(session, agent_id, request_text, lines):
    # Labels of an earlier request are dropped, so they do not open a later one.
    if not session or not lines:
        return False
    path = _state_path(session, agent_id)
    data = _read(path)
    request = _request_id(request_text)
    if data.get("request") != request or not isinstance(data.get("lines"), list):
        data = {"request": request, "lines": []}
    data["lines"].extend(lines)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False)
    except OSError:
        return False
    return True

def load(session, agent_id, request_text):
    if not session:
        return []
    data = _read(_state_path(session, agent_id))
    if data.get("request") != _request_id(request_text):
        return []
    lines = data.get("lines")
    return [line for line in lines if isinstance(line, str)] if isinstance(lines, list) else []
