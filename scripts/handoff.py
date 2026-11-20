"""Pre-commit logic handoff.

The handoff is the file a person reads before approving a commit: what the change does, how the
code flows, what to look at when it breaks, and the answers the user gave to the gate's questions.
The commit gate refuses until the file covers every staged source file and the user approves it.
"""
import argparse
import datetime
import os
import re
import subprocess
import sys

HANDOFF_PATH = ".fe-kit/handoff.md"
SOURCE_RE = re.compile(
    r"\.(?:tsx?|jsx?|mjs|cjs|vue|svelte|astro|mdx|py|go|rs|java|kt|kts|rb|php|cs|swift)$",
    re.I,
)
SECTIONS = (
    ("Logic", r"^##\s+(?:\d+[.)]\s*)?Logic\b"),
    ("Implementation", r"^##\s+(?:\d+[.)]\s*)?Implementation\b"),
    ("Decisions", r"^##\s+(?:\d+[.)]\s*)?Decisions?\b"),
    ("Debug without AI", r"^##\s+(?:\d+[.)]\s*)?Debug without AI\b"),
    ("Risks", r"^##\s+(?:\d+[.)]\s*)?Risks?\b"),
    ("Q&A", r"^##\s+(?:\d+[.)]\s*)?Q&A\b"),
)
CONFIRMED_BY_RE = re.compile(r"^Confirmed-by:\s*(\S.*)$", re.M)
CONFIRMED_AT_RE = re.compile(r"^Confirmed-at:\s*(\S+)$", re.M)
STALE_SECONDS = 1.0


def run_git(root, *args):
    try:
        result = subprocess.run(
            ["git", "-C", root] + list(args),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout if result.returncode == 0 else ""


def staged_files(root):
    return [line.strip() for line in run_git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines() if line.strip()]


def changed_files(root):
    return [line.strip() for line in run_git(root, "diff", "--name-only", "--diff-filter=ACMR").splitlines() if line.strip()]


def source_files(files):
    return [path for path in files if SOURCE_RE.search(path)]


def read_handoff(root):
    path = os.path.join(root, HANDOFF_PATH)
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return ""


def parse_time(value):
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def stale_files(root, files, confirmed_at):
    if confirmed_at is None:
        return []
    stale = []
    for path in files:
        full = os.path.join(root, path)
        try:
            modified = os.path.getmtime(full)
        except OSError:
            continue
        if modified > confirmed_at.timestamp() + STALE_SECONDS:
            stale.append(path)
    return stale


def problems(root, files=None, require_confirmation=True):
    files = staged_files(root) if files is None else files
    sources = source_files(files)
    if not sources:
        return []
    text = read_handoff(root)
    if not text.strip():
        return ["`%s` is missing or empty." % HANDOFF_PATH]
    found = []
    for name, pattern in SECTIONS:
        if not re.search(pattern, text, re.M):
            found.append("section `## %s` is missing" % name)
    for path in sources:
        if path not in text and ("./" + path) not in text:
            found.append("`%s` is not named in the handoff" % path)
    if not require_confirmation:
        return found
    by = CONFIRMED_BY_RE.search(text)
    at = CONFIRMED_AT_RE.search(text)
    if not by:
        found.append("`Confirmed-by:` is missing; ask the user to approve the handoff")
    if not at:
        found.append("`Confirmed-at:` is missing; ask the user to approve the handoff")
    else:
        confirmed_at = parse_time(at.group(1))
        if confirmed_at is None:
            found.append("`Confirmed-at:` is not an ISO timestamp")
        else:
            stale = stale_files(root, sources, confirmed_at)
            if stale:
                found.append("approval is older than `%s`; ask the user to approve again" % stale[0])
    return found


def approval_name(root):
    return run_git(root, "config", "user.name").strip() or os.environ.get("USER") or os.environ.get("USERNAME") or "user"


def stamp(text, by):
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    lines = [line for line in text.splitlines() if not re.match(r"^Confirmed-(?:by|at):", line)]
    while lines and not lines[-1].strip():
        lines.pop()
    lines += ["", "Confirmed-by: %s" % by, "Confirmed-at: %s" % now, ""]
    return "\n".join(lines)


def approve(root, by=None):
    found = problems(root, require_confirmation=False)
    if found:
        return found
    path = os.path.join(root, HANDOFF_PATH)
    text = read_handoff(root)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(stamp(text, by or approval_name(root)))
    except OSError as exc:
        return ["cannot write `%s`: %s" % (HANDOFF_PATH, exc)]
    return []


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check or approve the pre-commit logic handoff.")
    parser.add_argument("action", choices=("check", "approve", "status"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--by", default="")
    parser.add_argument("--files", nargs="*", help="check these files instead of the staged set")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    if args.action == "approve":
        found = approve(root, args.by or None)
        if found:
            for item in found:
                print("FAIL " + item)
            return 1
        print("OK   handoff approved for the staged source files")
        return 0
    found = problems(root, args.files)
    for item in found:
        print("FAIL " + item)
    if found:
        print("Write %s, answer the Q&A in chat, then ask the user to run: handoff.py approve --root %s" % (HANDOFF_PATH, root))
        return 1
    sources = source_files(staged_files(root) if args.files is None else args.files)
    print("OK   handoff covers %d source file(s)" % len(sources))
    return 0


if __name__ == "__main__":
    sys.exit(main())
