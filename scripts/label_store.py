"""Labels an agent declares with one Bash echo or printf.

The gate keys a declaration by the host's prompt id, and reads the command again from the
transcript. This module is the one parser: it reconstructs the text the command prints, so an
unquoted label, a cd prefix, or a stdout redirect is judged by what the shell would output.
"""
import hashlib
import json
import os
import re
import shlex
import tempfile

LABEL_RE = re.compile(r"(?:Runtime owner|Decision|Interface depth|Trigger|Steps?|Expected|Actual)[*_]*[:：]", re.I)
LABEL_BREAK_RE = re.compile(
    r"\\n(?=(?:Runtime owner|Decision|Interface depth|Trigger|Steps?|Expected|Actual)[*_]*[:：])", re.I
)
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_]\w*=")
OPERATORS = {"|", "||", "&&", ";", "&", "(", ")", "<", "<<", ">", ">>", ">&", "&>"}
COMMANDS = ("echo", "printf")
ECHO_FLAGS_RE = re.compile(r"^-[neE]+$")
PRINTF_SPEC_RE = re.compile(r"%([sbiouxXfFeEgGc]|%|[-+ #0]*\d*(?:\.\d+)?[a-zA-Z])")
MAX_PRINTF_ARGS = 64

def tokenize(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)

def strip_assignments(tokens, index):
    while index < len(tokens) and ASSIGNMENT_RE.match(tokens[index]):
        index += 1
    return index

def skip_command_prefix(tokens):
    # cd is harmless before the echo and common in an agent command. Any other chain is not.
    index = strip_assignments(tokens, 0)
    if index < len(tokens) and tokens[index] == "export":
        index = strip_assignments(tokens, index + 1)
    if index < len(tokens) and tokens[index] == "cd":
        cursor = index + 1
        if cursor < len(tokens) and tokens[cursor] not in OPERATORS:
            cursor += 1
        if cursor < len(tokens) and tokens[cursor] in ("&&", ";"):
            index = strip_assignments(tokens, cursor + 1)
        else:
            return None, "A declaration must be one echo or printf, optionally after `cd <dir> &&`."
    return index, ""

def strip_devnull(tokens):
    # A stdout redirect to /dev/null changes nothing the declaration means.
    remaining = list(tokens)
    while remaining:
        if (len(remaining) >= 3 and remaining[-3] in ("1", "2")
                and remaining[-2] in (">", ">&", "&>") and remaining[-1] in ("/dev/null", "1")):
            del remaining[-3:]
        elif len(remaining) >= 2 and remaining[-2] in (">", "&>") and remaining[-1] == "/dev/null":
            del remaining[-2:]
        else:
            break
    return remaining

def printf_text(format_text, values):
    # Only the conversion forms a declaration needs. Any other spec is left for the caller to reject.
    output = []
    cursor = 0
    used = 0
    for match in PRINTF_SPEC_RE.finditer(format_text):
        output.append(format_text[cursor:match.start()])
        spec = match.group(0)
        if spec == "%%":
            output.append("%")
        elif spec in ("%s", "%b") and used < len(values):
            output.append(values[used])
            used += 1
        else:
            return None
        cursor = match.end()
    output.append(format_text[cursor:])
    return "".join(output)

def unescape(text):
    return text.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")

def printed_text(tokens, name):
    args = tokens[1:]
    if name == "printf":
        if not args:
            return None
        text = printf_text(args[0], args[1:MAX_PRINTF_ARGS + 1])
        return unescape(text) if text is not None else None
    escaped = False
    while args and ECHO_FLAGS_RE.match(args[0]):
        if "e" in args[0]:
            escaped = True
        args = args[1:]
    text = " ".join(args)
    text = LABEL_BREAK_RE.sub("\n", text)
    return unescape(text) if escaped else text

def declaration_text(command):
    # (printed text, problem). An empty problem with None text means the command is not a declaration.
    if not command or not LABEL_RE.search(command):
        return None, ""
    if "`" in command:
        return None, "Backticks run a command. Quote the value with double quotes instead."
    if "$(" in command or "${" in command:
        return None, "A command substitution is not a declaration. Write the value literally."
    try:
        tokens = tokenize(command)
    except ValueError:
        return None, "The command is not valid shell syntax, so the gate cannot read the labels."
    index, problem = skip_command_prefix(tokens)
    if problem:
        return None, problem
    if index >= len(tokens) or tokens[index] not in COMMANDS:
        return None, "A declaration must be one echo or printf command with real values."
    name, args = tokens[index], tokens[index + 1:]
    args = strip_devnull(args)
    if any(token in OPERATORS for token in args):
        return None, "A declaration cannot pipe, chain, or redirect. Run one plain echo instead."
    if any("$" in token for token in args):
        return None, "A variable expands before the shell prints it. Write the value literally."
    text = printed_text([name] + args, name)
    if text is None:
        return None, "printf must use %s for each value and no other conversion."
    return text, ""

def declared_lines(command):
    text, _ = declaration_text(command)
    if not text:
        return []
    return [line.strip() for line in text.splitlines() if LABEL_RE.search(line)]

def declaration_problem(command):
    _, problem = declaration_text(command)
    return problem

def _state_path(session, agent_id):
    # The session is the host session id, or the transcript path when the host sends no id.
    root = os.environ.get("FE_GATE_STATE_DIR") or os.path.join(tempfile.gettempdir(), "fe-kit-gate")
    key = "%s|%s" % (session, agent_id or "")
    return os.path.join(root, hashlib.sha1(key.encode("utf-8")).hexdigest() + ".json")

def _read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}

def _lock(path):
    # A locked read-modify-write keeps two parallel echoes from losing each other.
    lock = open(path + ".lock", "a+")
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
    except (OSError, ImportError):
        pass
    return lock

def _unlock(handle):
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except (OSError, ImportError):
        pass
    handle.close()

def _write(path, data):
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False)
    os.replace(temp, path)

def save(session, agent_id, request_id, lines):
    # Labels of another prompt are dropped, so they do not open a later one.
    if not session or not lines:
        return False
    path = _state_path(session, agent_id)
    lock = None
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lock = _lock(path)
        data = _read(path)
        if data.get("request") != request_id or not isinstance(data.get("lines"), list):
            data = {"request": request_id, "lines": []}
        for line in lines:
            if line not in data["lines"]:
                data["lines"].append(line)
        _write(path, data)
    except OSError:
        return False
    finally:
        if lock is not None:
            _unlock(lock)
    return True

def load(session, agent_id, request_id):
    if not session:
        return []
    path = _state_path(session, agent_id)
    data = _read(path)
    if data.get("request") != request_id:
        return []
    lines = data.get("lines")
    return [line for line in lines if isinstance(line, str)] if isinstance(lines, list) else []
