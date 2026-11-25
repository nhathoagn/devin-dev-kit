"""Find the product-code file that a Bash command writes.

The fe-kit gate covers Edit, Write, and MultiEdit. A Bash command can write the same file through a
redirect, tee, cp, mv, sed -i, perl -i, or a script. write_target() checks every file the command
writes and names the first one that gate_scope.in_scope() calls product code, so fe-gate.py can gate
the command like Write. Shell operators are read outside quotes, and a script run by a test is not
scanned, because its writes are fixtures.
"""
import os
import re
import shlex
import tempfile

try:
    import gate_scope
except Exception:
    gate_scope = None

BASH_EXT = r"\.(?:tsx|jsx|js|ts|mjs|cjs|vue|svelte|astro|mdx|py|go|rs|java|kt|kts|rb|php|cs|swift)\b"
FRONTEND_RE = re.compile(BASH_EXT + r"$", re.I)
# A writer that builds the path in a variable names only the extension, as in endsWith('.tsx') or '*.tsx'.
BASH_EXT_MENTION_RE = re.compile(r"\.(tsx|jsx|js|ts|mjs|cjs|vue|svelte|astro|mdx|py|go|rs|java|kt|kts|rb|php|cs|swift)\b", re.I)
UNKNOWN_PATH_RE = re.compile(r"[$`~*?\[\]{}^|]|\\\.")
BUILT_TARGET_RE = re.compile(r"[$`]")
SUBSHELL_RE = re.compile(
    r"(?:^|[;&|\n])\s*[({]|[<>$]\(|(?<![\w.-])(?:pushd|popd|eval|source)(?![\w.-])|(?:^|[;&|\n])\s*\.\s"
)
CHDIR_RE = re.compile(r"\bchdir\s*\(|\bcwd\s*=")
CD_WORD_RE = re.compile(r"(?<![\w.-])cd(?![\w.-])")
HEREDOC_START_RE = re.compile(r"<<-?")
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")
DATA_SINK_COMMANDS = {"cat", "tee"}
BASH_ASSIGN_RE = re.compile(r"(?:^|[;&|\n]\s*|\s)([A-Za-z_]\w*)=(?:\"([^\"]*)\"|'([^']*)'|([^\s;&|]+))")
BASH_SCRIPT_RUN_RE = re.compile(
    r"(?<![.\w/\\-])(?:node|python3?|py|deno|bun|tsx|ts-node|bash|sh|perl|ruby)\s+"
    r"(?:-[\w-]+\s+)*['\"]?([^\s;&|'\"]+\.(?:m?js|cjs|ts|py|sh|pl|rb))",
    re.I,
)
BASH_CD_RE = re.compile(r"(?:^|[;&|\n]\s*)cd\s+['\"]?([^\s;&|'\"]+)")
ASSIGN_TOKEN_RE = re.compile(r"^[A-Za-z_]\w*=")
SHELL_KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "for", "in", "time",
                  "sudo", "env", "command", "exec", "nohup", "!"}
SCRIPT_MAX_BYTES = 200_000
COMMAND_MAX_BYTES = 200_000
# A test script writes fixtures, not product source. Its writes are not a frontend edit.
TEST_SCRIPT_RE = re.compile(
    r"(?:^|[\\/])(?:tests?|__tests__|specs?)[\\/]|(?:^|[\\/])test_[^\\/]*\.py$|\.(?:test|spec)\.[cm]?[jt]sx?$",
    re.I,
)
# The path argument of each write call in a script. Only that argument is a target, so a script that
# reads src/A.tsx and writes out.json is not gated.
WRITE_ARG_RES = [
    re.compile(r"(?:writeFileSync|writeFile|appendFileSync)\(\s*([^,)]*)"),
    re.compile(r"(\S+?)\.write_text\("),
    re.compile(r"\bopen\(\s*([^,)]*),\s*['\"][wa]"),
]
# A quoted literal, bare or inside Path(...). Anything else is built at run time.
LITERAL_ARG_RE = re.compile(r"^(?:\w+\()?(['\"])([^'\"$+`{}]*)\1\)?$")

def dir_at(text, pos):
    """(folder, known) for a relative path at `pos`: the one cd before it, or "" for the hook cwd.

    known is False when a subshell, a group, pushd, popd, a second cd, a cd the pattern cannot read
    (inside if or {}, builtin cd), a cd option, or a cd to a built path comes first.
    """
    before = mask_quotes(text[:pos], quoted_ranges(text[:pos]))
    cds = [match for match in BASH_CD_RE.finditer(text) if match.start() < pos]
    if SUBSHELL_RE.search(before) or len(cds) > 1 or len(CD_WORD_RE.findall(before)) != len(cds):
        return "", False
    if not cds:
        return "", True
    folder = local_path(cds[0].group(1))
    if folder.startswith("-") or UNKNOWN_PATH_RE.search(folder) or rooted_without_drive(folder):
        return "", False
    return folder, True

def rooted_without_drive(path):
    """On Windows a rooted path without a drive, as in /proc/self/cwd/x, names no known folder."""
    return os.name == "nt" and path[:1] in "/\\" and not os.path.splitdrive(path)[0]

def resolved_path(target, folder, known, cwd):
    """The full path the command writes, or None when it is known only at run time."""
    target = local_path(target)
    if UNKNOWN_PATH_RE.search(target):
        return None
    if rooted_without_drive(target):
        return None
    if os.path.isabs(target):
        return target
    if not known or not cwd:
        return None
    return os.path.join(cwd, folder, target)

def product_target(target, folder, known, cwd):
    """The target when it is product code or unknown, else "". An unknown path keeps the gate on."""
    full = resolved_path(target, folder, known, cwd)
    if full is None:
        return target
    if gate_scope is None or gate_scope.in_scope(full):
        return full
    return ""

def strip_data_heredocs(text):
    """Drop heredoc bodies only when the whole command does nothing but write quoted heredocs
    (<<'EOF') with cat or tee to plain files. The shell then runs nothing in the body and nothing
    reads it as code. Any other command keeps every body."""
    kept = []
    delimiter = None
    for line in text.split("\n"):
        if delimiter is not None:
            if line.strip() == delimiter:
                delimiter = None
            continue
        kept.append(line)
        if not line.strip():
            continue
        masked = mask_quotes(line, quoted_ranges(line))
        start = HEREDOC_START_RE.search(masked)
        match = HEREDOC_RE.match(line, start.start()) if start else None
        words = masked.split()
        if (not match or not match.group(1) or re.search(r"[;&|`]|[<>$]\(", masked)
                or masked.count("<<") > 1 or line.rstrip().endswith("\\")
                or os.path.basename(words[0]) not in DATA_SINK_COMMANDS):
            return text
        delimiter = match.group(2)
    return "\n".join(kept)

SHELL_STATE_VARIABLES = {"PWD", "OLDPWD"}

def expand_environment(target):
    """Put in the value of an environment variable the shell does not change while it runs.
    PWD and OLDPWD follow each cd, so they stay unknown, and so does any unset variable."""
    def value(match):
        name = match.group(1) or match.group(2)
        if name in SHELL_STATE_VARIABLES or name not in os.environ:
            return match.group(0)
        return os.environ[name].replace("\\", "/")
    return re.sub(r"\$\{(\w+)\}|\$(\w+)", value, target)

def expand_variables(command):
    values = {}
    for match in BASH_ASSIGN_RE.finditer(command):
        values[match.group(1)] = next(value for value in match.groups()[1:] if value is not None)
    for name_, value in values.items():
        if "$" in value:
            continue
        command = re.sub(r"\$\{" + name_ + r"\}|\$" + name_ + r"\b", lambda _: value, command)
        if len(command) > COMMAND_MAX_BYTES:
            return command[:COMMAND_MAX_BYTES]
    return command

def local_path(candidate):
    # Git Bash writes C:\x as /c/x and mounts the Windows temp folder at /tmp.
    if os.name == "nt":
        candidate = re.sub(r"^/([a-zA-Z])/", r"\1:/", candidate)
        candidate = re.sub(r"^/tmp(?=/|$)", lambda _: tempfile.gettempdir().replace("\\", "/"), candidate)
    return candidate

def quoted_ranges(text):
    ranges = []
    index = 0
    while index < len(text):
        char = text[index]
        if char not in "'\"":
            index += 1
            continue
        start, quote = index, char
        index += 1
        while index < len(text):
            if quote == '"' and text[index] == "\\":
                index += 2
                continue
            if text[index] == quote:
                index += 1
                break
            index += 1
        ranges.append((start, index))
    return ranges

def mask_quotes(text, ranges):
    chars = list(text)
    for start, end in ranges:
        chars[start:end] = " " * (end - start)
    return "".join(chars)

def inside(ranges, pos):
    return any(start <= pos < end for start, end in ranges)

def read_token(text, pos):
    length = len(text)
    while pos < length and text[pos] in " \t":
        pos += 1
    if pos >= length:
        return "", pos
    if text[pos] in "'\"":
        quote = text[pos]
        pos += 1
        start = pos
        while pos < length:
            if quote == '"' and text[pos] == "\\":
                pos += 2
                continue
            if text[pos] == quote:
                break
            pos += 1
        return text[start:pos], min(pos + 1, length)
    start = pos
    while pos < length and text[pos] not in " \t\n;&|<>()`":
        pos += 1
    return text[start:pos], pos

def tee_targets(text, masked):
    targets = []
    for match in re.finditer(r"\btee\b", masked):
        tail = text[match.end():]
        segment = re.split(r"[;&|]", tail, 1)[0]
        try:
            parts = shlex.split(segment)
        except ValueError:
            parts = []
        for part in parts:
            if part.startswith("-"):
                continue
            if FRONTEND_RE.search(part):
                targets.append((part, match.start()))
                break
    return targets

READ_ONLY_COMMANDS = {"grep", "rg", "ag", "ack", "echo", "printf", "git", "cat", "ls", "head", "tail", "sed", "awk"}

def tokenize_chunk(text):
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return []

def shell_segments(text):
    # Split on shell operators outside quotes, and keep each segment's start offset.
    ranges = quoted_ranges(text)
    masked = mask_quotes(text, ranges)
    segments = []
    start = 0
    for match in re.finditer(r"[;&|]+|\n", masked):
        chunk = text[start:match.start()]
        if chunk.strip():
            segments.append((tokenize_chunk(chunk), start + len(chunk) - len(chunk.lstrip())))
        start = match.end()
    chunk = text[start:]
    if chunk.strip():
        segments.append((tokenize_chunk(chunk), start + len(chunk) - len(chunk.lstrip())))
    return segments

def segment_command(text, pos, ranges):
    masked = mask_quotes(text, ranges)
    start = 0
    for match in re.finditer(r"[;&|]+|\n", masked[:pos]):
        start = match.end()
    token, _ = read_token(text, start)
    return os.path.basename(token)

def command_index(tokens):
    index = 0
    while index < len(tokens) and (ASSIGN_TOKEN_RE.match(tokens[index]) or tokens[index] in SHELL_KEYWORDS):
        index += 1
    return index

def sed_files(args):
    in_place = False
    scripts = 0
    files = []
    dynamic = False
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in ("-e", "--expression"):
            index += 1
            scripts += 1
        elif arg in ("-f", "--file"):
            index += 1
            scripts += 1
        elif arg.startswith("--in-place"):
            in_place = True
        elif arg.startswith("-") and not arg.startswith("--") and "i" in arg[1:]:
            in_place = True
        elif arg.startswith("-"):
            pass
        elif scripts == 0:
            scripts += 1
        else:
            files.append(arg)
            dynamic = dynamic or "$" in arg
        index += 1
    return (files if in_place else []), dynamic

def perl_files(args):
    in_place = False
    has_script = False
    expect_script = False
    files = []
    dynamic = False
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "-e":
            has_script = True
            expect_script = True
        elif arg.startswith("-") and not arg.startswith("--"):
            flags = arg[1:]
            if "i" in flags:
                in_place = True
            if "e" in flags:
                has_script = True
                expect_script = True
        elif arg.startswith("--"):
            pass
        elif expect_script:
            expect_script = False
        elif has_script:
            files.append(arg)
            dynamic = dynamic or "$" in arg
        else:
            has_script = True
        index += 1
    return (files if in_place else []), dynamic

def copy_files(tokens):
    name = tokens[0]
    args = tokens[1:]
    target_dir = ""
    positional = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in ("-t", "--target-directory"):
            index += 1
            if index < len(args):
                target_dir = args[index]
        elif arg.startswith("--target-directory="):
            target_dir = arg.split("=", 1)[1]
        elif arg.startswith("-"):
            pass
        else:
            positional.append(arg)
        index += 1
    targets = []
    if target_dir:
        targets = [os.path.join(target_dir, os.path.basename(path))
                   for path in positional if FRONTEND_RE.search(path)]
    elif len(positional) >= 2:
        destination = positional[-1]
        sources = positional[:-1]
        if FRONTEND_RE.search(destination):
            targets = [destination]
        elif name == "cp":
            targets = [os.path.join(destination, os.path.basename(path))
                       for path in sources if FRONTEND_RE.search(path)]
    dynamic = any("$" in path for path in positional)
    return targets, dynamic

def inplace_targets(text, base_at):
    targets = []
    dynamic = False
    for tokens, start in shell_segments(text):
        index = command_index(tokens)
        if index >= len(tokens):
            continue
        name = os.path.basename(tokens[index])
        if name == "sed":
            files, is_dynamic = sed_files(tokens[index + 1:])
        elif name == "perl":
            files, is_dynamic = perl_files(tokens[index + 1:])
        elif name in ("cp", "mv"):
            files, is_dynamic = copy_files(tokens[index:])
        else:
            continue
        dynamic = dynamic or is_dynamic
        targets += [(path, start) for path in files]
    return targets, dynamic

def write_call_targets(text, ranges):
    targets = []
    dynamic = False
    for pattern in WRITE_ARG_RES:
        for match in pattern.finditer(text):
            if inside(ranges, match.start()) and segment_command(text, match.start(), ranges) in READ_ONLY_COMMANDS:
                continue
            literal = LITERAL_ARG_RE.match(match.group(1).strip())
            if not literal:
                dynamic = True
            elif FRONTEND_RE.search(literal.group(2)):
                targets.append((literal.group(2), match.start()))
    return targets, dynamic

def dynamic_target(text, base_at, cwd):
    """For a write call whose path is built at run time: the first code file the text names that is
    product code or unknown, else "". A bare extension such as `.tsx` names no file."""
    for match in re.finditer(r"[^\s;&|<>'\"()]+", text):
        token = match.group(0)
        mention = BASH_EXT_MENTION_RE.search(token)
        if not mention:
            continue
        bare = not re.search(r"[\\/]", token)
        if bare or os.path.basename(token).startswith(".") or UNKNOWN_PATH_RE.search(token):
            return "(script that writes *%s)%s" % (mention.group(0), mention.group(0))
        target = product_target(token, *base_at(match.start()), cwd)
        if target:
            return target
    return ""

def write_target_in(text, cwd, run_dir=None):
    if run_dir is None:
        text = strip_data_heredocs(text)
    # A script that changes its own folder makes every relative path in it unknown.
    moves = CHDIR_RE.search(text)
    def base_at(pos):
        if moves:
            return "", False
        return dir_at(text, pos) if run_dir is None else run_dir
    ranges = quoted_ranges(text)
    masked = mask_quotes(text, ranges)
    targets = []
    for match in re.finditer(r">>?|&>", masked):
        token, _ = read_token(text, match.end())
        if token:
            targets.append((token, match.start()))
    targets += tee_targets(text, masked)
    inplace, inplace_dynamic = inplace_targets(text, base_at)
    calls, call_dynamic = write_call_targets(text, ranges)
    targets += inplace + calls
    dynamic = inplace_dynamic or call_dynamic
    for target, pos in targets:
        target = expand_environment(target)
        if not FRONTEND_RE.search(target):
            if BUILT_TARGET_RE.search(target):
                return "(write to a path built at run time: %s).ts" % target
            continue
        hit = product_target(target, *base_at(pos), cwd)
        if hit:
            return hit
    return dynamic_target(text, base_at, cwd) if dynamic else ""

def script_sources(command, cwd):
    # (text, run folder) of each script file the command runs, read from disk when it exists.
    sources = []
    for match in BASH_SCRIPT_RUN_RE.finditer(command):
        base = dir_at(command, match.start())
        script = local_path(match.group(1))
        candidate = script if os.path.isabs(script) else os.path.join(cwd or "", base[0], script)
        if TEST_SCRIPT_RE.search(candidate):
            continue
        try:
            if os.path.isfile(candidate) and os.path.getsize(candidate) <= SCRIPT_MAX_BYTES:
                with open(candidate, encoding="utf-8", errors="ignore") as handle:
                    sources.append((handle.read(), base))
        except OSError:
            continue
    return sources

def write_target(command, cwd):
    # The full path of a product-code file the Bash command writes, or "" when it writes none.
    command = expand_variables(command)[:COMMAND_MAX_BYTES]
    target = write_target_in(command, cwd)
    if target:
        return target
    for source, run_dir in script_sources(command, cwd):
        target = write_target_in(source, cwd, run_dir)
        if target:
            return target
    return ""
