"""Check a review-diff report before it goes to the user.

Run: python3 scripts/review_check.py --root <repo> --report <file> [--files ...] [--diff BASE..HEAD | --staged]

Exit 0: the report passes. Lines that start with `!` are warnings to check by hand.
Exit 1: the report breaks a rule. Fix the report and run again. Do not change this script.
Exit 2: the report, the config, or git cannot be read.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project_config

VERDICTS = ("Không đưa lên", "Sửa rồi hãy đưa", "Đưa được")
LEVELS = ("nên sửa trước", "nên sửa trong lượt này", "có thể để sau")
SCOPE_LABELS = ("Luật đã đọc:", "Cổng:", "Độ phủ:")
NOT_FINDINGS = ("Kết luận", "Tóm tắt", "Nguồn và độ phủ")
REF_RE = re.compile(r"`([^`]+?):(\d+)(?:-(\d+))?`")
BARE_NAMES = frozenset(("makefile", "dockerfile", "rakefile", "gemfile", "procfile", "license", "cmakelists.txt"))

def looks_like_path(value):
    # A citation path: dotted or slashed or dotfile. `12` of `12:30` and plain words are not paths.
    name = value.strip()
    if not name or "``" in name:
        return False
    if "/" in name or "\\" in name:
        return True
    base = name.rsplit("/", 1)[-1].lower()
    if base in BARE_NAMES:
        return True
    if "." in name:
        return True
    return False


def sections(text):
    sections = {}
    current = None
    for line in text.splitlines():
        heading = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
        if heading:
            current = heading.group(1)
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line)
    return sections


def label_value(text, label):
    for line in text.splitlines():
        stripped = line.strip().lstrip("-* ").strip()
        if stripped.startswith(label):
            return stripped[len(label):].strip()
    return None


def _resolve_ref(root, path, candidates):
    """A repo path, or the one diff file or rule file whose path ends with the cited path."""
    normalized = path.replace("\\", "/")
    if os.path.isfile(os.path.join(root, normalized)):
        return normalized
    exact = [item for item in candidates if item == normalized]
    deeper = [item for item in candidates if item != normalized and item.endswith("/" + normalized)]
    # A bare-basename cite means the repo-relative path, not itself: when exactly one
    # candidate path ends with it, that path is the resolution. Two or more deeper hits
    # are ambiguous, so only then does the exact string stand as its own key.
    if len(deeper) == 1:
        return deeper[0]
    if not deeper and len(exact) == 1:
        return exact[0]
    return None


def _folder(value):
    """A config folder as `dir/`, with no leading `./`."""
    value = value.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value.rstrip("/") + "/" if value.strip("/") else ""


def _line_count(root, path):
    with open(os.path.join(root, path), encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def _mentions(text, name):
    # A whole name, so `a.ts` does not match inside `a.tsx`. A name may hold a space.
    return re.search(r"(?<![\w./-])" + re.escape(name) + r"(?![\w./-])", text) is not None


def _covered(path, coverage, diff_files):
    tokens = re.split(r"[\s,·;`()]+", coverage)
    if _mentions(coverage, path) or any(token.endswith("/") and path.startswith(token) for token in tokens):
        return True
    # A bare file name covers a file only when no other diff file has that name.
    name = os.path.basename(path)
    return _mentions(coverage, name) and sum(os.path.basename(item) == name for item in diff_files) == 1


def _reference_roots(scope):
    """Folders a report may quote without a warning: spec folders and the legacy-rewrite sources."""
    roots = [_folder(folder) for folder in scope["spec_dirs"]]
    source = scope["legacy"].get("source", "")
    roots.append(_folder(source.split("{", 1)[0]))
    # cr is a file path template, as works/screens/{SID}.yaml: its folder is the part before the last `/`.
    cr = scope["legacy"].get("cr", "").split("{", 1)[0].replace("\\", "/")
    roots.append(_folder(cr.rsplit("/", 1)[0] if "/" in cr else ""))
    return [root for root in roots if root]

def _import_context(root, diff_files):
    """Repo files a diff file imports — legitimate context a lens may cite without a warning."""
    pattern = re.compile(r'import[^;"\']*["\']([^"\']+)["\']')
    context = set()
    for path in diff_files:
        full = os.path.join(root, path)
        if not os.path.isfile(full):
            continue
        try:
            with open(full, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        base = os.path.dirname(path)
        for spec in pattern.findall(text):
            spec = spec.replace("\\", "/")
            if spec.startswith("."):
                resolved = os.path.normpath(os.path.join(base, spec)).replace("\\", "/")
            else:
                resolved = spec.lstrip("/")
            if os.path.isfile(os.path.join(root, resolved)):
                context.add(resolved)
    return context

def check(root, report_text, files):
    """Return (errors, warnings) for the report against the changed files."""
    errors = []
    warnings = []
    scope = project_config.resolve(root, files, "review")
    diff_files = scope["files"]
    known = set(diff_files) | {item["path"] for item in scope["read"]}
    roots = _reference_roots(scope)
    context = _import_context(root, diff_files)
    parts = sections(report_text)

    verdict = None
    body = [line.strip() for line in parts.get("Kết luận", []) if line.strip()]
    if not body:
        errors.append("missing `## Kết luận` with a verdict sentence")
    else:
        verdict = next((word for word in VERDICTS if body[0].startswith(word)), None)
        if not verdict:
            errors.append("the first sentence of Kết luận must start with one of: %s" % ", ".join(VERDICTS))

    findings = "\n".join("\n".join(lines) for name, lines in parts.items() if name not in NOT_FINDINGS).lower()
    used = {level for level in LEVELS if level in findings}
    if verdict == "Đưa được" and used & {"nên sửa trước", "nên sửa trong lượt này"}:
        errors.append("verdict `Đưa được` while a finding says %s" % " / ".join(sorted(used - {"có thể để sau"})))
    if verdict == "Sửa rồi hãy đưa" and "nên sửa trước" in used:
        errors.append("verdict `Sửa rồi hãy đưa` while a finding says `nên sửa trước`; use `Không đưa lên`")
    if verdict == "Sửa rồi hãy đưa" and "nên sửa trong lượt này" not in used:
        errors.append("verdict `Sửa rồi hãy đưa` with no finding that says `nên sửa trong lượt này`")
    if verdict == "Không đưa lên" and "nên sửa trước" not in used:
        errors.append("verdict `Không đưa lên` with no finding that says `nên sửa trước`")

    for label in SCOPE_LABELS:
        value = label_value(report_text, label)
        if not value:
            errors.append("missing `%s` with a value under `## Nguồn và độ phủ`" % label)

    coverage = label_value(report_text, "Độ phủ:") or ""
    if coverage:
        # A file the diff deleted, or the old name of a renamed file, has nothing left to read.
        missing = [path for path in diff_files
                   if os.path.exists(os.path.join(root, path)) and not _covered(path, coverage, diff_files)]
        if missing:
            errors.append("Độ phủ does not name: %s" % ", ".join(missing))

    for match in REF_RE.finditer(report_text):
        path, start, end = match.group(1), int(match.group(2)), match.group(3)
        if not looks_like_path(path):
            continue
        resolved = _resolve_ref(root, path, diff_files + [item["path"] for item in scope["read"]])
        if not resolved:
            errors.append("`%s:%d` names a file that is not in the repo or the diff" % (path, start))
            continue
        last = int(end) if end else start
        if not os.path.isfile(os.path.join(root, resolved)):
            # A file the diff deleted: its old lines cannot be counted here.
            warnings.append("`%s:%d` names a file the diff deleted: check the line at BASE" % (resolved, start))
            continue
        count = _line_count(root, resolved)
        if start < 1 or last > count or last < start:
            errors.append("`%s:%s` is outside the file (%d lines)" % (path, start if not end else "%d-%s" % (start, end), count))
        elif resolved not in known and resolved not in context and not any(resolved.startswith(folder) for folder in roots):
            warnings.append("`%s:%d` is outside the diff: check it is a caller the diff breaks or a file the diff imports" % (resolved, start))
    return errors, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check a fe-kit review-diff report.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--report", required=True)
    project_config.add_source_arguments(parser)
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        with open(args.report, encoding="utf-8") as handle:
            text = handle.read()
        files = project_config.files_from_args(root, args)
        errors, warnings = check(root, text, files)
    except (OSError, project_config.ConfigError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2
    for line in errors:
        print("x " + line)
    for line in warnings:
        print("! " + line)
    print("review_check: %s (%d errors, %d warnings)" % ("FAIL" if errors else "OK", len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
