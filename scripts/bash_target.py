"""Find the product-code file that a Bash command writes.

The fe-kit gate covers Edit, Write, and MultiEdit. A Bash command can write the same file through a
redirect, tee, cp, mv, rsync, install, dd, sed -i, perl -i, patch, an archive extraction, a git
worktree rewrite (checkout/restore/stash/reset/clean/merge/pull/apply...), a wrapped command
(eval, bash -c, xargs -I), a script run by path or source, or a script's write calls.
write_target() checks every file the command writes and names the first one that
gate_scope.in_scope() calls product code, so fe-gate.py can gate the command like Write. Shell
operators are read outside quotes, and a script run by a test is not scanned, because its writes
are fixtures.
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
LINK_RE = re.compile(r"\bmklink\b|\bln\s+-\w*s|-ItemType\s+['\"]?(?:Junction|SymbolicLink)|\bsubst\b", re.I)
CD_WORD_RE = re.compile(r"(?<![\w.-])cd(?![\w.-])")
HEREDOC_START_RE = re.compile(r"<<-?")
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")
DATA_SINK_COMMANDS = {"cat", "tee"}
BASH_ASSIGN_RE = re.compile(r"(?:^|[;&|\n]\s*|\s)([A-Za-z_]\w*)=(?:\"([^\"]*)\"|'([^']*)'|([^\s;&|]+))")
BASH_SCRIPT_RUN_RE = re.compile(
    r"(?<![.\w\\-])(?:node|python3?|py|deno|bun|tsx|ts-node|bash|sh|perl|ruby)\s+"
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
# reads src/A.tsx and writes out.json is not gated. Each entry pairs the pattern with the group that
# holds the written path. The last flag marks calls where the group is the destination of a two-path
# call, so a literal folder destination still counts as a product write.
WRITE_ARG_RES = [
    (re.compile(r"(?:writeFileSync|writeFile|appendFileSync)\(\s*([^,)]*)"), 1, False),
    (re.compile(r"(\S+?)\.(?:write_text|write_bytes)\("), 1, False),
    (re.compile(r"\bopen\(\s*([^,)]*),\s*['\"][wa]"), 1, False),
    (re.compile(r"\bshutil\.(?:copyfile|copy2?|copytree|move)\s*\([^,)]*,\s*([^)]*)"), 1, True),
    (re.compile(r"\bos\.(?:rename|replace)\s*\([^,)]*,\s*([^)]*)"), 1, True),
]
# A quoted literal, bare or inside Path(...). Anything else is built at run time.
LITERAL_ARG_RE = re.compile(r"^(?:\w+\()?(['\"])([^'\"$+`{}]*)\1\)?$")
# Magic bytes of compiled executables. A binary run by path is ordinary tooling, so only a readable
# text file or an unreadable one is scanned or gated; gating /usr/bin/curl would fire constantly.
BINARY_MAGICS = (b"\x7fELF", b"MZ", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
                 b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe")
MAX_DEPTH = 3

def dir_at(text, pos):
    """(folder, known) for a relative path at `pos`: the one cd before it, or "" for the hook cwd.

    known is False when a subshell, a group, pushd, popd, a second cd, a cd the pattern cannot read
    (inside if or {}, builtin cd), a cd option, or a cd to a built path comes first.
    """
    before = mask_quotes(text[:pos], quoted_ranges(text[:pos]))
    cds = [match for match in BASH_CD_RE.finditer(text) if match.start() < pos]
    if SUBSHELL_RE.search(before) or len(cds) > 1 or len(CD_WORD_RE.findall(before)) != len(cds):
        return "", False
    if cds and ("CDPATH" in text or os.environ.get("CDPATH")):
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
    if gate_scope is None or gate_scope.in_scope(full, cwd):
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

def reassigned(command, name):
    """True when the command also sets `name` in a way the assignment pattern does not read."""
    word = re.escape(name)
    return bool(re.search(
        r"\b(?:for|select)\s+" + word + r"\b|\b(?:read|readarray|mapfile|getopts)\b[^;&|\n]*\b" + word + r"\b"
        r"|\bprintf\s+-v\s*" + word + r"\b|\b(?:declare|typeset|local)\b[^;&|\n]*\b" + word + r"\b",
        command))

def expand_variables(command):
    """Put in each variable the command assigns once with a plain value. Any other variable stays,
    so a target that still holds `$` counts as built at run time."""
    values = {}
    counts = {}
    for match in BASH_ASSIGN_RE.finditer(command):
        values[match.group(1)] = next(value for value in match.groups()[1:] if value is not None)
        counts[match.group(1)] = counts.get(match.group(1), 0) + 1
    for name_, value in values.items():
        if "$" in value or counts[name_] > 1 or reassigned(command, name_):
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

# Flags of copy-style commands that consume the next token, so it is not read as a file.
COPY_FLAG_ARGS = {
    "install": {"-g", "-m", "-o", "-S", "-t", "--group", "--mode", "--owner", "--suffix",
                "--target-directory"},
    "rsync": {"-e", "--rsh", "--rsync-path", "--files-from", "--exclude", "--include", "--filter",
              "--exclude-from", "--include-from", "--chmod", "--chown", "--temp-dir", "--backup-dir",
              "--log-file", "--out-format", "--link-dest", "--copy-dest", "--compare-dest",
              "--max-size", "--min-size", "--bwlimit", "--port", "--iconv", "--password-file",
              "--timeout", "--contimeout", "--modify-window", "--address", "--compress-level",
              "--partial-dir", "--info", "--debug"},
    "cp": {"-t", "--target-directory"},
    "mv": {"-t", "--target-directory"},
}

def looks_dir(path, base, cwd):
    if path.endswith("/") or path in (".", ".."):
        return True
    folder, known = base
    full = resolved_path(path, folder, known, cwd)
    return bool(full) and os.path.isdir(full)

def dir_write(dest, base, cwd, verb):
    """A command that writes a whole folder in product scope, as a marker since no single file is
    named. A dest outside the repo or a folder that cannot be found writes nothing scoped."""
    folder, known = base
    if UNKNOWN_PATH_RE.search(dest) or not known:
        return "(%s into a folder known only at run time: %s).ts" % (verb, dest)
    full = resolved_path(dest, folder, known, cwd)
    if full is None:
        return "(%s into a folder known only at run time: %s).ts" % (verb, dest)
    if gate_scope is None or gate_scope.in_scope(full, cwd):
        return "(%s into product folder %s).ts" % (verb, dest)
    return ""

def copy_files(tokens, base, cwd):
    name = os.path.basename(tokens[0])
    args = tokens[1:]
    flag_args = COPY_FLAG_ARGS.get(name, set())
    target_dir = ""
    positional = []
    index = 0
    mkdir_only = False
    while index < len(args):
        arg = args[index]
        if arg in ("-t", "--target-directory"):
            index += 1
            if index < len(args):
                target_dir = args[index]
        elif arg.startswith("--target-directory="):
            target_dir = arg.split("=", 1)[1]
        elif arg == "-d" and name == "install":
            # install -d is mkdir, not a copy.
            mkdir_only = True
        elif arg in flag_args:
            index += 1
        elif arg.startswith("-"):
            pass
        else:
            positional.append(arg)
        index += 1
    if mkdir_only:
        return [], False, ""
    targets = []
    destination = ""
    sources = []
    if target_dir:
        destination = target_dir
        sources = positional
        targets = [os.path.join(target_dir, os.path.basename(path))
                   for path in positional if FRONTEND_RE.search(path)]
    elif len(positional) >= 2:
        destination = positional[-1]
        sources = positional[:-1]
        if FRONTEND_RE.search(destination):
            targets = [destination]
        else:
            targets = [os.path.join(destination, os.path.basename(path))
                       for path in sources if FRONTEND_RE.search(path)]
    dynamic = any("$" in path for path in positional)
    # When either side is a folder the destination is a write even when no source names product code:
    # `cp -r src/ dest/`, `rsync a/ b/`, `install -t`. A dest outside the repo still returns "".
    dir_dest = ""
    remote = ":" in destination.split("/", 1)[0] if destination else False
    if destination and not remote and (looks_dir(destination, base, cwd)
                                       or any(looks_dir(path, base, cwd) for path in sources)
                                       or len(sources) > 1):
        dir_dest = destination
    return targets, dynamic, dir_dest

def dd_files(args):
    files = []
    dynamic = False
    for arg in args:
        if arg.startswith("of="):
            path = arg[3:]
            files.append(path)
            dynamic = dynamic or "$" in path or not path
    return files, dynamic

# patch short flags that consume an operand: prefix, define, directory, fuzz, input, output,
# reject-file, strip, version-control, suffix, prune-style.
PATCH_OPERAND_SHORT = "BdDFioprVzY"
PATCH_OPERAND_LONG = {"--directory", "--input", "--output", "--reject-file", "--strip", "--ifdef",
                      "--basename-prefix", "--suffix", "--version-control", "--fuzz",
                      "--quoting-style"}

def patch_files(args, base, cwd):
    files = []
    dirs = []
    positional = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            positional += args[index + 1:]
            break
        if arg.startswith("--"):
            key = arg.split("=", 1)[0]
            value = arg.split("=", 1)[1] if "=" in arg else None
            if value is None and key in PATCH_OPERAND_LONG:
                index += 1
                value = args[index] if index < len(args) else ""
            if key == "--directory" and value:
                dirs.append(value)
            elif key == "--output" and value:
                files.append(value)
            index += 1
            continue
        if arg.startswith("-") and len(arg) > 1:
            column = 1
            while column < len(arg):
                char = arg[column]
                if char in PATCH_OPERAND_SHORT:
                    operand = arg[column + 1:] if column + 1 < len(arg) else ""
                    if not operand:
                        index += 1
                        operand = args[index] if index < len(args) else ""
                    if char == "d" and operand:
                        dirs.append(operand)
                    elif char in ("o", "r") and operand:
                        files.append(operand)
                    break
                column += 1
            index += 1
            continue
        positional.append(arg)
        index += 1
    # With no patch file given the first positional is the file to patch; a second positional is the
    # patch input, which is read, not written.
    if positional:
        files.append(positional[0])
    dynamic = any("$" in path for path in files)
    markers = []
    if dirs:
        for folder in dirs:
            marker = dir_write(folder, base, cwd, "patch")
            if marker:
                markers.append(marker)
    elif not files:
        # patch < fix.diff applies the diff to files under the working directory.
        marker = dir_write(".", base, cwd, "patch")
        if marker:
            markers.append(marker)
    return files, dynamic, markers

GIT_NOARG_FLAGS = {"-P", "-p", "--paginate", "--no-pager", "--no-replace-objects", "--bare",
                   "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
                   "--icase-pathspecs", "--no-optional-locks", "--exec-path", "--html-path",
                   "--man-path", "--info-path", "--version", "--help"}
GIT_PREFIX_VALUE_FLAGS = ("--git-dir", "--work-tree", "--namespace")
# Subcommands that rewrite tracked worktree files with no pathspec arguments needed.
GIT_TREE_WRITES = {"merge", "pull", "rebase", "revert", "cherry-pick", "apply", "am"}
GIT_STASH_WRITES = {"pop", "apply", "push", "save", "create", "store", "branch"}

def git_base(args, base):
    # (subcommand, rest, base) after git's global flags. -C changes the folder pathspecs resolve in.
    folder, known = base
    cdirs = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "-C":
            index += 1
            if index < len(args):
                cdirs.append(args[index])
            index += 1
            continue
        if arg == "-c":
            index += 2
            continue
        if any(arg == flag or arg.startswith(flag + "=") for flag in GIT_PREFIX_VALUE_FLAGS):
            index += 1 if "=" in arg else 2
            continue
        if arg in GIT_NOARG_FLAGS or arg.startswith("-"):
            index += 1
            continue
        break
    if index >= len(args):
        return "", [], (folder, known)
    for cdir in cdirs:
        cdir = local_path(cdir)
        if not known or UNKNOWN_PATH_RE.search(cdir):
            known = False
            continue
        folder = cdir if os.path.isabs(cdir) else os.path.normpath(os.path.join(folder, cdir))
    return args[index], args[index + 1:], (folder, known)


def git_files(tokens, base, cwd):
    # (resolved hits, dynamic): markers or product paths the git subcommand writes.
    args = tokens[1:]
    sub, rest, gbase = git_base(args, base)
    markers = []
    dynamic = False
    if sub in ("checkout", "co"):
        dash = rest.index("--") if "--" in rest else -1
        before = rest[:dash] if dash >= 0 else rest
        after = rest[dash + 1:] if dash >= 0 else []
        flag_args = {"-b", "-B", "--orphan", "--conflict"}
        positional = []
        index = 0
        force = False
        while index < len(before):
            arg = before[index]
            if arg in flag_args:
                index += 2
                continue
            if arg.startswith("--pathspec-from-file=") or arg == "--pathspec-from-file":
                dynamic = True
                index += 1 if "=" in arg else 2
                continue
            if arg.startswith("-"):
                cluster = arg[1:] if not arg.startswith("--") else ""
                if arg in ("-f", "--force", "-m", "--merge", "--discard-changes") \
                        or (cluster and ("f" in cluster or "m" in cluster)):
                    force = True
                index += 1
                continue
            positional.append(arg)
            index += 1
        if after:
            for path in after:
                if path in (".", "..") or path.endswith("/"):
                    marker = dir_write(path, gbase, cwd, "git checkout")
                    if marker:
                        markers.append(marker)
                    continue
                hit = product_target(path, gbase[0], gbase[1], cwd)
                if hit:
                    markers.append(hit)
            dynamic = dynamic or any("$" in path for path in after)
        elif len(positional) >= 2:
            # checkout A B without -- is a ref plus pathspecs or all pathspecs; either way it writes.
            markers.append("(git checkout pathspecs rewrite worktree files).ts")
        elif force:
            markers.append("(git checkout -f discards worktree files).ts")
    elif sub == "restore":
        staged = False
        worktree = False
        flag_args = {"-s", "--source", "-m", "--merge", "--conflict"}
        positional = []
        index = 0
        while index < len(rest):
            arg = rest[index]
            if arg in flag_args:
                index += 2
                continue
            if arg in ("--pathspec-from-file",) or arg.startswith("--pathspec-from-file="):
                dynamic = True
                index += 1 if "=" in arg else 2
                continue
            if arg.startswith("--source=") or arg.startswith("--conflict="):
                index += 1
                continue
            if arg.startswith("--staged") or arg == "-S":
                staged = True
                index += 1
                continue
            if arg.startswith("--worktree") or arg == "-W":
                worktree = True
                index += 1
                continue
            if arg.startswith("-") and not arg.startswith("--") and len(arg) > 1:
                cluster = arg[1:]
                if "S" in cluster:
                    staged = True
                if "W" in cluster:
                    worktree = True
                if "s" in cluster:
                    index += 1 if cluster.endswith("s") else 0
                index += 1
                continue
            if arg.startswith("--"):
                index += 1
                continue
            positional.append(arg)
            index += 1
        # Default restore touches the worktree; --staged alone touches only the index.
        writes = worktree or not staged
        if writes:
            for path in positional:
                if path in (".", "..") or path.endswith("/"):
                    marker = dir_write(path, gbase, cwd, "git restore")
                    if marker:
                        markers.append(marker)
                    continue
                hit = product_target(path, gbase[0], gbase[1], cwd)
                if hit:
                    markers.append(hit)
            dynamic = dynamic or any("$" in path for path in positional)
    elif sub == "stash":
        op = rest[0] if rest and not rest[0].startswith("-") else "push"
        if op in GIT_STASH_WRITES:
            markers.append("(git stash %s rewrites tracked files).ts" % op)
    elif sub in GIT_TREE_WRITES:
        markers.append("(git %s rewrites tracked files).ts" % sub)
    elif sub == "switch":
        if any(arg in ("-f", "--force", "--discard-changes")
               or (arg.startswith("-") and not arg.startswith("--") and "f" in arg[1:])
               for arg in rest):
            markers.append("(git switch -f discards worktree changes).ts")
    elif sub == "reset":
        if "--hard" in rest:
            markers.append("(git reset --hard rewrites tracked files).ts")
    elif sub == "clean":
        if any(arg in ("-f", "--force") or
               (arg.startswith("-") and not arg.startswith("--") and "f" in arg[1:])
               for arg in rest):
            markers.append("(git clean -f deletes untracked files).ts")
    elif sub == "submodule":
        if rest and rest[0] == "update":
            markers.append("(git submodule update rewrites tracked files).ts")
    return markers, dynamic

TAR_OPERAND_SHORT = "bCfkNTwX"
TAR_OPERAND_LONG = {"--file", "--directory", "--files-from", "--exclude-from", "--transform",
                    "--newer", "--exclude", "--include", "--strip-components", "--to-command",
                    "--index-file", "--checkpoint-action", "--group", "--owner", "--mode",
                    "--format", "--occurrence", "--label", "--volno-file",
                    "--use-compress-program", "--rsh-command", "--info-script", "--newer-mtime",
                    "--exclude-tag", "--exclude-tag-all", "--exclude-tag-under", "--starting-file",
                    "--reference", "--level", "--record-size", "--tape-length"}

def archive_files(name, args, base, cwd):
    markers = []
    if name in ("tar", "bsdtar"):
        mode = ""
        dirs = []
        index = 0
        while index < len(args):
            arg = args[index]
            if arg.startswith("--"):
                if arg.startswith("--extract") or arg.startswith("--get"):
                    mode = "x"
                elif arg.startswith("--create") or arg.startswith("--append"):
                    mode = "c"
                elif arg.startswith("--list") or arg.startswith("--diff"):
                    mode = "t"
                key = arg.split("=", 1)[0]
                value = arg.split("=", 1)[1] if "=" in arg else None
                if value is None and key in TAR_OPERAND_LONG:
                    index += 1
                    value = args[index] if index < len(args) else ""
                if key == "--directory" and value:
                    dirs.append(value)
                index += 1
                continue
            if arg.startswith("-") and len(arg) > 1:
                column = 1
            elif index == 0:
                column = 0  # old-style `tar xvf`
            else:
                index += 1
                continue
            while column < len(arg):
                char = arg[column]
                if char in "xct":
                    mode = char
                elif char in TAR_OPERAND_SHORT:
                    operand = arg[column + 1:] if column + 1 < len(arg) else ""
                    if not operand:
                        index += 1
                        operand = args[index] if index < len(args) else ""
                    if char == "C" and operand:
                        dirs.append(operand)
                    break
                column += 1
            index += 1
        if mode == "x":
            if dirs:
                for folder in dirs:
                    marker = dir_write(folder, base, cwd, "tar extracts")
                    if marker:
                        markers.append(marker)
            else:
                marker = dir_write(".", base, cwd, "tar extracts")
                if marker:
                    markers.append(marker)
    elif name == "unzip":
        read_only = any(arg.startswith(("-l", "-t", "-z", "-Z", "-T", "-p", "-c", "-v"))
                        for arg in args if arg.startswith("-"))
        if not read_only:
            dirs = []
            index = 0
            while index < len(args):
                if args[index] == "-d" and index + 1 < len(args):
                    dirs.append(args[index + 1])
                    index += 1
                index += 1
            if dirs:
                for folder in dirs:
                    marker = dir_write(folder, base, cwd, "unzip extracts")
                    if marker:
                        markers.append(marker)
            else:
                marker = dir_write(".", base, cwd, "unzip extracts")
                if marker:
                    markers.append(marker)
    elif name in ("jar", "7z", "7za", "7zr", "7zz"):
        if name == "jar":
            if args and "x" in args[0] and "t" not in args[0]:
                marker = dir_write(".", base, cwd, "jar extracts")
                if marker:
                    markers.append(marker)
        else:
            op = args[0] if args else ""
            if op in ("e", "x"):
                out_dirs = [arg[2:] for arg in args if arg.startswith("-o")]
                if out_dirs:
                    for folder in out_dirs:
                        marker = dir_write(folder, base, cwd, "7z extracts")
                        if marker:
                            markers.append(marker)
                else:
                    marker = dir_write(".", base, cwd, "7z extracts")
                    if marker:
                        markers.append(marker)
    return markers

INNER_SHELLS = {"bash", "sh", "dash", "zsh", "ksh", "ash", "csh", "tcsh", "fish"}
SHELL_OPERAND_FLAGS = {"-o", "+o", "-O", "+O"}
XARGS_WRITERS = {"cp", "mv", "tee", "install", "rsync", "dd", "patch", "git", "bash", "sh", "eval"}

def inner_command(name, args):
    """The command string `eval` or `sh -c` runs, or None."""
    if name == "eval":
        words = [arg for arg in args if not arg.startswith("-")]
        return " ".join(words) if words else None
    if name in INNER_SHELLS:
        index = 0
        while index < len(args):
            arg = args[index]
            if arg in SHELL_OPERAND_FLAGS:
                index += 2
                continue
            if arg == "-c":
                return args[index + 1] if index + 1 < len(args) else None
            if arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]:
                return args[index + 1] if index + 1 < len(args) else None
            if arg.startswith("-"):
                index += 1
                continue
            return None  # the first positional is a script path, not a -c string
    return None

def script_target(path, base, cwd, depth):
    """Gate a file run by path or by source: scan a readable text script, gate an unreadable one,
    and leave a compiled binary alone since ordinary tools run by path."""
    if UNKNOWN_PATH_RE.search(path):
        return "(runs a script at a path built at run time: %s).ts" % path
    folder, known = base
    local = local_path(path)
    if os.path.isabs(local):
        candidate = local
    elif not known or not cwd:
        return "(runs a script at a path known only at run time: %s).ts" % path
    else:
        candidate = os.path.join(cwd, folder, local)
    if TEST_SCRIPT_RE.search(candidate):
        return ""
    try:
        if not os.path.isfile(candidate) or os.path.getsize(candidate) > SCRIPT_MAX_BYTES:
            return "(runs a script that is not readable: %s).ts" % path
        with open(candidate, "rb") as handle:
            blob = handle.read(SCRIPT_MAX_BYTES + 1)
    except OSError:
        return "(runs a script that is not readable: %s).ts" % path
    if blob.startswith(BINARY_MAGICS) or b"\0" in blob[:4096]:
        return ""
    if depth >= MAX_DEPTH:
        return "(runs a script: %s).ts" % path
    text = blob.decode("utf-8", "ignore")
    return write_target_in(text, cwd, run_dir=base, depth=depth + 1) \
        or "(runs a script: %s).ts" % path

REDIRECT_TOKENS = {"<", "<<", "<<<", ">", ">>", "&>", "&>>", "<>"}

def clean_args(tokens, index):
    """The arguments after the command word at `index`, without redirections. `> f` is already a
    write target of the main scan, and `patch x < f` must not read f as a file argument."""
    tail = tokens[index + 1:]
    args = []
    pos = 0
    while pos < len(tail):
        token = tail[pos]
        if token in REDIRECT_TOKENS:
            pos += 2
            continue
        if re.match(r"^\d+$", token) and pos + 1 < len(tail) and tail[pos + 1] in REDIRECT_TOKENS:
            pos += 1  # the descriptor of 2>err
            continue
        args.append(token)
        pos += 1
    return args

def command_targets(text, base_at, cwd, depth):
    targets = []
    dynamic = False
    hits = []
    for tokens, start in shell_segments(text):
        index = command_index(tokens)
        if index >= len(tokens):
            continue
        token = tokens[index]
        name = os.path.basename(token)
        args = clean_args(tokens, index)
        base = base_at(start)
        files = []
        is_dynamic = False
        if name == "sed":
            files, is_dynamic = sed_files(args)
        elif name == "perl":
            files, is_dynamic = perl_files(args)
        elif name in ("cp", "mv", "install", "rsync"):
            files, is_dynamic, dir_dest = copy_files([token] + args, base, cwd)
            if dir_dest:
                marker = dir_write(dir_dest, base, cwd, name)
                if marker:
                    hits.append(marker)
        elif name == "dd":
            files, is_dynamic = dd_files(args)
        elif name == "patch":
            files, is_dynamic, markers = patch_files(args, base, cwd)
            hits += markers
        elif name in ("git", "git.exe"):
            markers, is_dynamic = git_files([token] + args, base, cwd)
            hits += markers
        elif name in ("tar", "bsdtar", "unzip", "jar", "7z", "7za", "7zr", "7zz"):
            hits += archive_files(name, args, base, cwd)
        elif name in ("eval", "source", ".") or name in INNER_SHELLS:
            if name in ("source", "."):
                words = [arg for arg in args if not arg.startswith("-")]
                if words:
                    marker = script_target(words[0], base, cwd, depth)
                    if marker:
                        hits.append(marker)
            elif depth < MAX_DEPTH:
                inner = inner_command(name, args)
                if inner:
                    target = write_target_in(inner, cwd, run_dir=base, depth=depth + 1)
                    hits.append(target or "(runs a command string).ts")
            elif name in INNER_SHELLS:
                hits.append("(runs a command string or stdin).ts")
            if name in INNER_SHELLS and not any(not arg.startswith("-") for arg in args):
                # A bare shell reads commands from stdin, as in `curl u | sh`.
                hits.append("(runs commands from stdin).ts")
        elif name == "xargs":
            replace = any(arg == "-i" or arg.startswith("-I") or arg.startswith("-J") for arg in args)
            if replace and any(os.path.basename(arg) in XARGS_WRITERS for arg in args):
                # xargs -I{} cp a.tsx {} runs the writer once per input line.
                is_dynamic = True
        elif "/" in token and not token.startswith("-"):
            marker = script_target(token, base, cwd, depth)
            if marker:
                hits.append(marker)
        else:
            continue
        dynamic = dynamic or is_dynamic
        targets += [(path, start) for path in files]
    return targets, dynamic, hits

def write_call_targets(text, ranges):
    targets = []
    dynamic = False
    for pattern, group, is_dest in WRITE_ARG_RES:
        for match in pattern.finditer(text):
            if inside(ranges, match.start()) and segment_command(text, match.start(), ranges) in READ_ONLY_COMMANDS:
                continue
            literal = LITERAL_ARG_RE.match(match.group(group).strip())
            if not literal:
                dynamic = True
            elif FRONTEND_RE.search(literal.group(2)):
                targets.append((literal.group(2), match.start()))
            elif is_dest:
                # A literal folder destination (copytree) still writes product code.
                dynamic = True
    return targets, dynamic

def dynamic_target(text, base_at, cwd):
    """A write whose path is built at run time names no single file, so the target is a marker.
    Naming the first code path the text mentions would pin the gate on a file that is not written."""
    for match in re.finditer(r"[^\s;&|<>'\"()]+", text):
        token = match.group(0)
        mention = BASH_EXT_MENTION_RE.search(token)
        if not mention:
            continue
        bare = not re.search(r"[\\/]", token)
        if bare or os.path.basename(token).startswith(".") or UNKNOWN_PATH_RE.search(token):
            return "(script that writes *%s)%s" % (mention.group(0), mention.group(0))
        return "(script writes a path built at run time).ts"
    return "(script writes a path built at run time).ts"

def write_target_in(text, cwd, run_dir=None, depth=0):
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
    commands, command_dynamic, hits = command_targets(text, base_at, cwd, depth)
    calls, call_dynamic = write_call_targets(text, ranges)
    targets += commands + calls
    dynamic = command_dynamic or call_dynamic
    # A command that makes a junction or symlink can point any path at product code before it writes.
    links = LINK_RE.search(text)
    for target, pos in targets:
        if not FRONTEND_RE.search(target):
            if BUILT_TARGET_RE.search(target):
                return "(write to a path built at run time: %s).ts" % target
            continue
        hit = target if links else product_target(target, *base_at(pos), cwd)
        if hit:
            return hit
    for hit in hits:
        if hit:
            return hit
    if dynamic and links:
        return "(script that writes through a new link).ts"
    if dynamic:
        return dynamic_target(text, base_at, cwd)
    if depth < MAX_DEPTH:
        for source, source_dir in script_sources(text, cwd, run_dir):
            hit = write_target_in(source, cwd, run_dir=source_dir, depth=depth + 1)
            if hit:
                return hit
    return ""

def script_sources(command, cwd, run_dir=None):
    # (text, run folder) of each script file the command runs, read from disk when it exists.
    sources = []
    for match in BASH_SCRIPT_RUN_RE.finditer(command):
        base = run_dir if run_dir is not None else dir_at(command, match.start())
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
    return write_target_in(command, cwd) or ""
