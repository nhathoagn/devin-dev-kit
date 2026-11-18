"""Find the frontend file that a Bash command writes.

The fe-kit gate covers Edit, Write, and MultiEdit. A Bash command can write the same file through a
redirect, tee, cp, mv, sed -i, perl -i, or a script. write_target() names that file, so fe-gate.py can
gate the command like Write. It reads the command text and any script file the command runs.
"""
import os
import re

# A Bash command can write a frontend file without Edit or Write: a redirect, tee, sed -i, perl -i, cp, mv,
# or a script that calls writeFileSync or write_text. Such a command is gated like Write on its target file.
# A target in a temp or scratchpad folder is a throwaway script, so it stays open.
BASH_EXT = r"\.(?:tsx|jsx|js|mjs|cjs|vue|svelte|astro|mdx)"
BASH_PATH = r"['\"]?([^\s;&|<>'\"()]+" + BASH_EXT + r")(?=['\"\s;&|)]|$)"
BASH_TARGET_RES = [
    re.compile(r"(?<![0-9&<>=-])>>?\s*" + BASH_PATH, re.I),
    re.compile(r"\btee\s+(?:-\w+\s+)*" + BASH_PATH, re.I),
    re.compile(r"\b(?:cp|mv)\s+(?:-\w+\s+)*\S+\s+" + BASH_PATH, re.I),
]
# sed -i and perl -i edit every file in their arguments, up to the end of the shell command.
IN_PLACE_RE = re.compile(r"\b(?:sed|perl)\b[^;&|\n]*?\s-[a-zA-Z]*i\b([^;&|\n]*)")
BASH_ANY_PATH_RE = re.compile(r"(?<![\w.-])" + BASH_PATH, re.I)
TEMP_PATH_RE = re.compile(r"(?:^|[\\/])(?:tmp|temp|scratchpad)(?:[\\/]|$)", re.I)
TEMP_TOKEN_RE = re.compile(r"[^\s;&|<>'\"()]*(?:^|[\\/])(?:tmp|temp|scratchpad)[\\/][^\s;&|<>'\"()]*", re.I)
# A writer that builds the path in a variable names only the extension, as in endsWith('.tsx') or '*.tsx'.
# .js and .mjs are left out here, because the script file itself often has that extension.
BASH_EXT_MENTION_RE = re.compile(r"\.(tsx|jsx|vue|svelte|astro|mdx)\b", re.I)
# A variable set in the same command, as in S="C:/x/rename.mjs"; node "$S".
BASH_ASSIGN_RE = re.compile(r"(?:^|[;&|\n]\s*|\s)([A-Za-z_]\w*)=(?:\"([^\"]*)\"|'([^']*)'|([^\s;&|]+))")
BASH_SCRIPT_RUN_RE = re.compile(
    r"\b(?:node|python3?|py|deno|bun|tsx|ts-node|bash|sh|perl|ruby)\s+(?:-[\w-]+\s+)*['\"]?([^\s;&|'\"]+\.(?:m?js|cjs|ts|py|sh|pl|rb))",
    re.I,
)
BASH_CD_RE = re.compile(r"(?:^|[;&|\n]\s*)cd\s+['\"]?([^\s;&|'\"]+)")
SCRIPT_MAX_BYTES = 200_000

def dir_at(text, pos):
    # A relative path resolves against the last cd before it, as in cd "$SP"; sed -i ... check.js.
    # With no cd the base is "": the session cwd itself may sit in a temp folder, so it never makes a path temp.
    base = ""
    for match in BASH_CD_RE.finditer(text):
        if match.start() < pos:
            base = local_path(match.group(1))
    return base

def outside_temp(target, base):
    target = local_path(target)
    full = target if os.path.isabs(target) or not base else os.path.join(base, target)
    return not TEMP_PATH_RE.search(full)

def expand_variables(command):
    values = {}
    for match in BASH_ASSIGN_RE.finditer(command):
        values[match.group(1)] = next(value for value in match.groups()[1:] if value is not None)
    for name_, value in values.items():
        command = re.sub(r"\$\{" + name_ + r"\}|\$" + name_ + r"\b", lambda _: value, command)
    return command

def local_path(candidate):
    # Git Bash writes C:\x as /c/x. Windows Python needs the drive letter back.
    if os.name == "nt":
        candidate = re.sub(r"^/([a-zA-Z])/", r"\1:/", candidate)
    return candidate

def script_sources(command, cwd):
    # (text, run folder) of each script file the command runs, read from disk when it exists.
    sources = []
    for match in BASH_SCRIPT_RUN_RE.finditer(command):
        base = dir_at(command, match.start())
        script = local_path(match.group(1))
        candidate = script if os.path.isabs(script) else os.path.join(base or cwd, script)
        try:
            if os.path.isfile(candidate) and os.path.getsize(candidate) <= SCRIPT_MAX_BYTES:
                with open(candidate, encoding="utf-8", errors="ignore") as handle:
                    sources.append((handle.read(), base))
        except OSError:
            continue
    return sources

# The path argument of each write call in a script. Only that argument is a target, so a script that reads
# src/A.tsx and writes out.json is not gated.
WRITE_ARG_RES = [
    re.compile(r"(?:writeFileSync|writeFile|appendFileSync)\(\s*([^,)]*)"),
    re.compile(r"(\S+?)\.write_text\("),
    re.compile(r"\bopen\(\s*([^,)]*),\s*['\"][wa]"),
]
# A quoted literal, bare or inside Path(...). Anything else is built at run time.
LITERAL_ARG_RE = re.compile(r"^(?:\w+\()?(['\"])([^'\"$+`{}]*)\1\)?$")

def write_target_in(text, run_dir=None):
    # run_dir is the cd a script file runs under. A command resolves each path against its own cd.
    def base_at(pos):
        return dir_at(text, pos) if run_dir is None else run_dir
    targets = []
    dynamic = False
    for pattern in BASH_TARGET_RES:
        targets += [(match.group(1), base_at(match.start())) for match in pattern.finditer(text)]
    for match in IN_PLACE_RE.finditer(text):
        args = match.group(1)
        targets += [(found.group(1), base_at(match.start())) for found in BASH_ANY_PATH_RE.finditer(args)]
        dynamic = dynamic or "$" in args
    for pattern in WRITE_ARG_RES:
        for match in pattern.finditer(text):
            literal = LITERAL_ARG_RE.match(match.group(1).strip())
            if not literal:
                dynamic = True
            elif re.search(BASH_EXT + "$", literal.group(2), re.I):
                targets.append((literal.group(2), base_at(match.start())))
    for target, base in targets:
        if outside_temp(target, base):
            return target
    if dynamic:
        mention = BASH_EXT_MENTION_RE.search(TEMP_TOKEN_RE.sub(" ", text))
        if mention:
            return "(script that writes *" + mention.group(0) + ")" + mention.group(0)
    return ""

def write_target(command, cwd):
    # The frontend file a Bash command writes, or "" when it writes none.
    command = expand_variables(command)
    target = write_target_in(command)
    if target:
        return target
    for source, run_dir in script_sources(command, cwd):
        target = write_target_in(source, run_dir)
        if target:
            return target
    return ""
