"""Keep the last review of a branch, so the next review reads only what changed after it.

Run: python3 scripts/review_record.py save --root <repo> --report <report.md> [--head <sha>] [--branch <name>]
     python3 scripts/review_record.py last --root <repo> [--branch <name>]

save writes `.fe-kit/reviews/<branch>.md`: the reviewed commit, then the report. Commit the reviewed code
first, because save records HEAD: it refuses while files outside .fe-kit/reviews/ are not committed, unless
--allow-dirty. Then commit the record.
last prints `base: <sha>` and each finding of that report. The next review uses `--diff <sha>` (that sha against the working
tree) and checks each old finding again. With no record, last prints `base: none` and exits 0.
"""
import argparse
import os
import re
import subprocess
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review_check

RECORD_DIR = ".fe-kit/reviews"
HEAD_RE = re.compile(r"^<!-- fe-kit review: head=([0-9a-f]{7,40}) -->$", re.M)


class RecordError(ValueError):
    pass


def _git(root, *args):
    result = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0:
        raise RecordError("git %s failed: %s" % (" ".join(args), result.stderr.strip()))
    return result.stdout.strip()


def record_path(root, branch=None):
    branch = branch or _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        raise RecordError("HEAD is detached: pass --branch with the branch name")
    # Percent-encoding keeps names apart: feat/x is feat%2Fx, and feat-x stays feat-x.
    return os.path.join(root, RECORD_DIR, urllib.parse.quote(branch, safe="") + ".md")


def _uncommitted(root):
    # Only files under root count. Porcelain paths start at the repo top, so the record folder gets root's prefix.
    prefix = _git(root, "rev-parse", "--show-prefix")
    lines = _git(root, "-c", "core.quotepath=off", "status", "--porcelain", "--untracked-files=all", "--", ".")
    # Split off the status code by whitespace, because _git strips the leading space of the first line.
    files = [line.split(None, 1)[1].split(" -> ")[-1].strip('"') for line in lines.splitlines() if line.strip()]
    return [path for path in files if not path.startswith(prefix + RECORD_DIR + "/")]


def save(root, report_text, head=None, branch=None, allow_dirty=False):
    if not head and not allow_dirty:
        dirty = _uncommitted(root)
        if dirty:
            raise RecordError("commit the reviewed code first, because save records HEAD. Not committed: %s"
                              % ", ".join(dirty[:10]))
    head = head or _git(root, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{7,40}", head):
        raise RecordError("head `%s` is not a commit sha" % head)
    path = record_path(root, branch)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("<!-- fe-kit review: head=%s -->\n\n%s\n" % (head, report_text.strip()))
    return path


def last(root, branch=None):
    """Return (base sha or None, list of finding paragraphs)."""
    path = record_path(root, branch)
    if not os.path.isfile(path):
        return None, []
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    match = HEAD_RE.search(text)
    if not match:
        raise RecordError("%s has no `fe-kit review: head=` line" % os.path.relpath(path, root))
    body = "\n".join(review_check.sections(text).get("Việc cần sửa", []))
    findings = [block.strip() for block in re.split(r"\n\s*\n", body) if block.strip()]
    return match.group(1), findings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Save or read the last fe-kit review of a branch.")
    commands = parser.add_subparsers(dest="command", required=True)
    save_cmd = commands.add_parser("save")
    save_cmd.add_argument("--root", default=".")
    save_cmd.add_argument("--report", required=True)
    save_cmd.add_argument("--head")
    save_cmd.add_argument("--branch")
    save_cmd.add_argument("--allow-dirty", action="store_true")
    last_cmd = commands.add_parser("last")
    last_cmd.add_argument("--root", default=".")
    last_cmd.add_argument("--branch")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        if args.command == "save":
            with open(args.report, encoding="utf-8") as handle:
                path = save(root, handle.read(), args.head, args.branch, args.allow_dirty)
            print("saved: %s" % os.path.relpath(path, root).replace("\\", "/"))
            return 0
        base, findings = last(root, args.branch)
        print("base: %s" % (base or "none"))
        for number, finding in enumerate(findings, start=1):
            print("finding %d: %s" % (number, " ".join(finding.split())))
        return 0
    except (OSError, RecordError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
