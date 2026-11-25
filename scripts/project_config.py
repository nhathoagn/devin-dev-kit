"""Tell an agent which project rules to read for a set of changed files.

Run: python3 scripts/project_config.py --root <repo> [--files a.tsx b.ts] [--diff BASE..HEAD | --staged]
                                       [--mode review|author|all] [--json]

The repo may have `.fe-kit/config.yaml`. It is optional. With no config, the script searches
AGENTS.md, CLAUDE.md, and `rules/` folders from each file up to the repo root, and a root
REVIEW_CHECKLIST.md on a review. Exit 0 prints the result, warnings included. Exit 2 is a config
that cannot be read, or a git command that failed.
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml_subset

CONFIG_PATH = ".fe-kit/config.yaml"
DEFAULT_SPEC_DIRS = ["docs", "specs", ".scratch"]
LIST_KEYS = ("presets", "always_read", "spec_dirs", "gate", "exclude", "scope")
KNOWN_KEYS = {"version", "rules", "legacy", "handoff"} | set(LIST_KEYS)
HANDOFF_MODES = ("required", "off")
PRESET_FILES = {"review": ["review.md"], "author": ["design.md"], "all": ["design.md", "review.md"]}
RULE_NAMES = ("AGENTS.md", "CLAUDE.md")
MODES = ("review", "author", "all")
# fe-kit's own review records are not code to review.
ALWAYS_EXCLUDE = (".fe-kit/reviews/**",)


class ConfigError(ValueError):
    pass


def plugin_dir():
    return os.environ.get("FE_ARCH_ROOT") or os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def glob_regex(pattern):
    """Turn a glob with `*`, `**`, `?`, and `{a,b}` into a regex for a repo-relative posix path."""
    out = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**/", index):
            out.append("(?:.*/)?")
            index += 3
            continue
        if pattern.startswith("**", index):
            out.append(".*")
            index += 2
            continue
        if char == "*":
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        elif char == "{":
            end = pattern.find("}", index)
            if end < 0:
                raise ConfigError("glob `%s` has `{` with no `}`" % pattern)
            out.append("(?:" + "|".join(re.escape(part) for part in pattern[index + 1:end].split(",")) + ")")
            index = end
        else:
            out.append(re.escape(char))
        index += 1
    return re.compile("^" + "".join(out) + "$")


def matches(pattern, path):
    return bool(glob_regex(pattern).match(path))


def _as_list(value, where):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ConfigError("`%s` must be a list of strings" % where)


def load_config(root):
    """Return (config, warnings). Config is None when the repo has no config file."""
    path = os.path.join(root, CONFIG_PATH)
    if not os.path.isfile(path):
        return None, []
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError("%s cannot be read: %s" % (CONFIG_PATH, exc))
    return parse_config(text)


def parse_config(text):
    """Return (config, warnings) for the text of a config file."""
    try:
        data = yaml_subset.load(text)
    except yaml_subset.YamlError as exc:
        raise ConfigError("%s %s" % (CONFIG_PATH, exc))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError("%s must be a mapping of keys" % CONFIG_PATH)
    warnings = ["unknown key `%s` in %s" % (key, CONFIG_PATH) for key in data if key not in KNOWN_KEYS]
    version = data.get("version", 1)
    if version != 1:
        raise ConfigError("%s: version %r is not supported, use 1" % (CONFIG_PATH, version))
    config = {key: _as_list(data.get(key), key) for key in LIST_KEYS}
    if "spec_dirs" not in data:
        config["spec_dirs"] = list(DEFAULT_SPEC_DIRS)
    rules = data.get("rules") or []
    if not isinstance(rules, list):
        raise ConfigError("`rules` must be a list of `glob` and `read` entries")
    config["rules"] = []
    for number, entry in enumerate(rules):
        if not isinstance(entry, dict) or "glob" not in entry or "read" not in entry:
            raise ConfigError("`rules[%d]` needs `glob` and `read`" % number)
        globs = _as_list(entry["glob"], "rules[%d].glob" % number)
        for pattern in globs:
            glob_regex(pattern)
        config["rules"].append({"glob": globs, "read": _as_list(entry["read"], "rules[%d].read" % number)})
    legacy = data.get("legacy") or {}
    if not isinstance(legacy, dict) or not all(isinstance(value, str) for value in legacy.values()):
        raise ConfigError("`legacy` must be a mapping of strings")
    config["legacy"] = legacy
    handoff = data.get("handoff", "required")
    if handoff is True:
        handoff = "required"
    elif handoff is False:
        handoff = "off"
    if handoff not in HANDOFF_MODES:
        raise ConfigError("`handoff` must be `required` or `off`")
    config["handoff"] = handoff
    for pattern in config["exclude"] + config["scope"]:
        glob_regex(pattern)
    return config, warnings


def exclude_hit(config, path):
    """The `exclude` pattern that `path` (repo-relative) matches, or None. `config` may be None."""
    patterns = (config["exclude"] if config else []) + list(ALWAYS_EXCLUDE)
    return next((pattern for pattern in patterns if matches(pattern, path)), None)


def normalize(root, path):
    path = path.replace("\\", "/")
    if os.path.isabs(path):
        try:
            path = os.path.relpath(path, root).replace("\\", "/")
        except ValueError:
            raise ConfigError("%s is on another drive than the repo root %s" % (path, root))
    while path.startswith("./"):
        path = path[2:]
    return path


def changed_files(root, diff=None, staged=False):
    def git(*args):
        # quotepath=off: git would print a non-ASCII path in quotes with octal escapes.
        result = subprocess.run(["git", "-C", root, "-c", "core.quotepath=off"] + list(args), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", check=False)
        if result.returncode != 0:
            raise ConfigError("git %s failed: %s" % (" ".join(args), result.stderr.strip()))
        return [line for line in result.stdout.splitlines() if line.strip()]

    # --relative: paths relative to root, like ls-files, also when root is a folder inside the repo.
    # --no-renames: a renamed file is listed under its old and its new name, so a report may cite either.
    if diff and ".." in diff:
        return git("diff", "--name-only", "--no-renames", "--relative", diff)
    if diff:
        # One commit with no `..`: that commit against the working tree, new files included, as `git diff <sha>`.
        files = git("diff", "--name-only", "--no-renames", "--relative", diff) + git("ls-files", "--others", "--exclude-standard")
        return sorted(set(files))
    if staged:
        return git("diff", "--name-only", "--no-renames", "--relative", "--cached")
    files = git("diff", "--name-only", "--no-renames", "--relative", "HEAD") + git("ls-files", "--others", "--exclude-standard")
    return sorted(set(files))


def add_source_arguments(parser):
    """--files, --diff, and --staged, shared by the fe-kit review scripts."""
    parser.add_argument("--files", nargs="+", help="these files; with --diff or --staged, a part of that diff")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--diff", metavar="RANGE")
    source.add_argument("--staged", action="store_true")


def files_from_args(root, args):
    """The files to work on. --files with --diff keeps one package of that diff."""
    if not args.files:
        return changed_files(root, args.diff, args.staged)
    if not (args.diff or args.staged):
        return args.files
    in_diff = set(changed_files(root, args.diff, args.staged))
    files = [normalize(os.path.abspath(root), path) for path in args.files]
    outside = [path for path in files if path not in in_diff]
    if outside:
        raise ConfigError("--files names files that are not in the diff: %s" % ", ".join(outside))
    return files


def _preset_dir(root, name):
    if name.startswith(("./", "../")) or os.path.isabs(name):
        return os.path.normpath(os.path.join(root, name)), False
    return os.path.join(plugin_dir(), "presets", name), True


def _discover(root, files):
    """Rule files a repo keeps in the usual places, from the root down to each file's folder."""
    found = []
    folders = {""}
    for path in files:
        parts = path.split("/")[:-1]
        for depth in range(len(parts) + 1):
            folders.add("/".join(parts[:depth]))
    for folder in sorted(folders, key=lambda item: (item.count("/") if item else -1, item)):
        for name in RULE_NAMES:
            candidate = "/".join(part for part in (folder, name) if part)
            if os.path.isfile(os.path.join(root, candidate)):
                found.append((candidate, "found in %s" % (folder or "repo root")))
        rules_dir = "/".join(part for part in (folder, "rules") if part)
        full = os.path.join(root, rules_dir)
        if os.path.isdir(full):
            for name in sorted(os.listdir(full)):
                if name.endswith(".md") and os.path.isfile(os.path.join(full, name)):
                    found.append((rules_dir + "/" + name, "found in %s" % rules_dir))
    return found


def resolve(root, files, mode="all"):
    """Return what to read for `files` under `root`. Raises ConfigError for a bad config."""
    if mode not in MODES:
        raise ConfigError("mode must be one of %s" % ", ".join(MODES))
    root = os.path.abspath(root)
    config, warnings = load_config(root)
    files = [normalize(root, path) for path in files]
    result = {"config": CONFIG_PATH if config else None, "mode": mode, "files": [], "skipped": [],
              "read": [], "spec_dirs": list(DEFAULT_SPEC_DIRS), "gate": [], "legacy": {}, "warnings": warnings}
    reads = []
    for path in files:
        hit = exclude_hit(config, path)
        if hit:
            result["skipped"].append({"file": path, "exclude": hit})
        else:
            result["files"].append(path)
    if config is None:
        reads.extend(_discover(root, result["files"]))
    else:
        reads.extend((path, "always_read") for path in config["always_read"])
        for entry in config["rules"]:
            hits = [pattern for pattern in entry["glob"] if any(matches(pattern, path) for path in result["files"])]
            if hits:
                reads.extend((path, "rules: %s" % hits[0]) for path in entry["read"])
        for name in config["presets"]:
            folder, builtin = _preset_dir(root, name)
            if not os.path.isdir(folder):
                warnings.append("preset `%s` not found at %s" % (name, folder))
                continue
            for filename in PRESET_FILES[mode]:
                full = os.path.join(folder, filename)
                if os.path.isfile(full):
                    shown = full.replace("\\", "/") if builtin else normalize(root, full)
                    reads.append((shown, "preset %s" % name))
        result["spec_dirs"] = config["spec_dirs"]
        result["gate"] = config["gate"]
        result["legacy"] = config["legacy"]
    if mode in ("review", "all") and os.path.isfile(os.path.join(root, "REVIEW_CHECKLIST.md")):
        reads.append(("REVIEW_CHECKLIST.md", "repo checklist"))
    seen = set()
    for path, why in reads:
        if path in seen:
            continue
        seen.add(path)
        target = path if os.path.isabs(path) else os.path.join(root, path)
        if not os.path.isfile(target):
            warnings.append("%s does not exist (%s)" % (path, why))
            continue
        result["read"].append({"path": path, "why": why})
    return result


def format_text(result):
    lines = ["config: %s" % (result["config"] or "none (searched AGENTS.md, CLAUDE.md, rules/)"),
             "mode: %s" % result["mode"]]
    lines += ["read: %s  (%s)" % (item["path"], item["why"]) for item in result["read"]]
    if not result["read"]:
        lines.append("read: none (only the fe-kit rules apply)")
    lines += ["file: %s" % path for path in result["files"]]
    lines += ["skip: %s  (exclude: %s)" % (item["file"], item["exclude"]) for item in result["skipped"]]
    lines.append("spec_dirs: %s" % " ".join(result["spec_dirs"]))
    lines += ["gate: %s" % command for command in result["gate"]] or ["gate: none"]
    lines += ["legacy.%s: %s" % (key, value) for key, value in sorted(result["legacy"].items())]
    lines += ["warn: %s" % warning for warning in result["warnings"]]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Project rules to read for changed files.")
    parser.add_argument("--root", default=".")
    add_source_arguments(parser)
    parser.add_argument("--mode", choices=MODES, default="all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = resolve(args.root, files_from_args(args.root, args), args.mode)
    except ConfigError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else format_text(result))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
