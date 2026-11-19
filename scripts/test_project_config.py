"""Tests for scripts/project_config.py. Run: python3 scripts/test_project_config.py (exit code = failures).

Each case builds a small repo in a temp folder, then checks what the script tells the agent to read.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "project_config.py")
sys.path.insert(0, HERE)
import project_config

TMP = tempfile.mkdtemp(prefix="fe-kit-config-test-")
FAILURES = [0]
TOTAL = [0]


def repo(name, files):
    root = os.path.join(TMP, name)
    for path, text in files.items():
        full = os.path.join(root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    os.makedirs(root, exist_ok=True)
    return root


def run(root, *args):
    result = subprocess.run([sys.executable, "-I", SCRIPT, "--root", root] + list(args),
                            capture_output=True, text=True, encoding="utf-8")
    return result.returncode, result.stdout, result.stderr


def reads(root, files, mode="all"):
    return [item["path"] for item in project_config.resolve(root, files, mode)["read"]]


def check(name, got, want):
    TOTAL[0] += 1
    ok = got == want
    FAILURES[0] += not ok
    print(("OK  " if ok else "FAIL"), name + ("" if ok else "\n      got:  %r\n      want: %r" % (got, want)))


def glob_cases():
    table = [
        ("src/**", "src/a/b.tsx", True),
        ("src/**", "lib/a.tsx", False),
        ("**/*.tsx", "a.tsx", True),
        ("**/*.tsx", "src/x/a.tsx", True),
        ("src/*.tsx", "src/x/a.tsx", False),
        ("src/{pages,routes}/**", "src/routes/a.tsx", True),
        ("src/{pages,routes}/**", "src/hooks/a.ts", False),
        ("src/**/*{export,csv}*", "src/x/order-csv.ts", True),
        ("a?.ts", "ab.ts", True),
        ("a?.ts", "a/.ts", False),
        ("src/a.ts", "src/a.ts", True),
        ("src/a.ts", "src/a_ts", False),
    ]
    for pattern, path, want in table:
        check("glob %s ~ %s" % (pattern, path), project_config.matches(pattern, path), want)


def fallback_cases():
    root = repo("none", {"src/a.tsx": "x"})
    check("no config, no rules: nothing to read", reads(root, ["src/a.tsx"]), [])
    code, out, _ = run(root, "--files", "src/a.tsx")
    check("no config: exit 0 and says only fe-kit rules apply",
          (code, "read: none" in out, "config: none" in out, "warn:" in out), (0, True, True, False))

    root = repo("nested", {
        "AGENTS.md": "root", "CLAUDE.md": "root",
        "app/AGENTS.md": "app", "app/rules/2-forms.md": "f", "app/rules/1-layout.md": "l",
        "app/rules/note.txt": "skip", "app/src/pages/AGENTS.md": "pages",
        "other/AGENTS.md": "other", "REVIEW_CHECKLIST.md": "L1",
    })
    check("no config: root, then each parent folder, rules/*.md sorted, sibling folders skipped",
          reads(root, ["app/src/pages/a.tsx"], "author"),
          ["AGENTS.md", "CLAUDE.md", "app/AGENTS.md", "app/rules/1-layout.md", "app/rules/2-forms.md",
           "app/src/pages/AGENTS.md"])
    check("no config, review mode: root REVIEW_CHECKLIST.md is kept",
          reads(root, ["app/src/pages/a.tsx"], "review")[-1], "REVIEW_CHECKLIST.md")
    check("no config, author mode: no REVIEW_CHECKLIST.md",
          "REVIEW_CHECKLIST.md" in reads(root, ["app/src/pages/a.tsx"], "author"), False)
    check("windows path is normalized",
          reads(root, ["app\\src\\pages\\a.tsx"], "author")[-1], "app/src/pages/AGENTS.md")


def config_cases():
    root = repo("cfg", {
        ".fe-kit/config.yaml": (
            "version: 1\n"
            "rules:\n"
            "  - glob: \"web/src/{pages,routes}/**\"\n"
            "    read: [web/rules/forms.md, web/rules/layout.md]\n"
            "  - glob: \"web/src/components/**\"\n"
            "    read:\n"
            "      - web/rules/compose.md\n"
            "      - web/rules/forms.md\n"
            "  - glob: \"api/**\"\n"
            "    read: [api/rules.md]\n"
            "always_read: [web/rules/CARD.md]\n"
            "spec_dirs: [works/design]\n"
            "gate:\n"
            "  - npm run typecheck\n"
            "exclude: [\"web/src/routeTree.gen.ts\", \"**/package-lock.json\"]\n"
            "legacy:\n"
            "  source: dev/\n"
        ),
        "web/rules/CARD.md": "c", "web/rules/forms.md": "f", "web/rules/layout.md": "l",
        "web/rules/compose.md": "c", "api/rules.md": "a", "AGENTS.md": "not read with a config",
    })
    result = project_config.resolve(root, ["web/src/pages/a.tsx", "web/src/components/b.tsx",
                                           "web/src/routeTree.gen.ts", "web/package-lock.json"], "author")
    check("config: always_read first, then each matching rule once, in config order",
          [item["path"] for item in result["read"]],
          ["web/rules/CARD.md", "web/rules/forms.md", "web/rules/layout.md", "web/rules/compose.md"])
    check("config: excluded files are skipped and not reviewed",
          ([item["file"] for item in result["skipped"]], result["files"]),
          (["web/src/routeTree.gen.ts", "web/package-lock.json"], ["web/src/pages/a.tsx", "web/src/components/b.tsx"]))
    check("config: spec_dirs, gate, legacy come from the file",
          (result["spec_dirs"], result["gate"], result["legacy"]), (["works/design"], ["npm run typecheck"], {"source": "dev/"}))
    check("config: AGENTS.md is not searched when a config exists", "AGENTS.md" in reads(root, ["web/src/pages/a.tsx"]), False)
    check("config: a rule whose glob matches nothing is not read", "api/rules.md" in reads(root, ["web/src/pages/a.tsx"]), False)
    code, out, _ = run(root, "--files", "web/src/pages/a.tsx", "--mode", "review")
    check("config CLI: each file to review has a `file:` line", ("file: web/src/pages/a.tsx" in out), True)
    check("config CLI: text lines", (code, "config: .fe-kit/config.yaml" in out,"read: web/rules/forms.md  (rules: web/src/{pages,routes}/**)" in out,
                                    "gate: npm run typecheck" in out, "legacy.source: dev/" in out, "spec_dirs: works/design" in out),
          (0, True, True, True, True, True))
    code, out, _ = run(root, "--files", "web/src/pages/a.tsx", "--json")
    check("config CLI: --json is valid JSON", (code, json.loads(out)["config"]), (0, ".fe-kit/config.yaml"))

    root = repo("defaults", {".fe-kit/config.yaml": "rules: []\n"})
    result = project_config.resolve(root, ["a.tsx"])
    check("config: missing keys use defaults", (result["spec_dirs"], result["gate"], result["warnings"]),
          (["docs", "specs", ".scratch"], [], []))

    root = repo("missing", {".fe-kit/config.yaml": "always_read: [gone.md]\nmystery: 1\n"})
    code, out, _ = run(root, "--files", "a.tsx")
    check("config: a missing rule file and an unknown key warn, exit 0",
          (code, "warn: gone.md does not exist (always_read)" in out, "warn: unknown key `mystery`" in out), (0, True, True))


def error_cases():
    bad = [
        ("broken yaml", "rules: [a\n", "line 1"),
        ("unquoted glob", "exclude: **/x\n", "line 1"),
        ("wrong version", "version: 2\n", "version 2"),
        ("rules not a list", "rules: x\n", "`rules`"),
        ("rule without read", "rules:\n  - glob: \"a/**\"\n", "rules[0]"),
        ("read not strings", "rules:\n  - glob: a\n    read: [1]\n", "rules[0].read"),
        ("legacy not mapping", "legacy: [a]\n", "`legacy`"),
        ("top level list", "- a\n", "mapping"),
        ("glob with open brace", "exclude: [\"a/{b\"]\n", "no `}`"),
    ]
    for name, text, needle in bad:
        root = repo("bad-" + name.replace(" ", "-"), {".fe-kit/config.yaml": text})
        code, _, err = run(root, "--files", "a.tsx")
        check("error: %s -> exit 2 and names the problem" % name, (code, needle in err), (2, True))


def preset_cases():
    root = repo("preset", {
        ".fe-kit/config.yaml": "presets: [legacy-rewrite, ./tools/team, missing-one]\n",
        "tools/team/review.md": "r", "tools/team/design.md": "d",
    })
    result = project_config.resolve(root, ["a.tsx"], "review")
    paths = [item["path"] for item in result["read"]]
    check("preset: built-in review.md comes from the plugin",
          paths[0].endswith("presets/legacy-rewrite/review.md"), True)
    check("preset: a ./ preset is read from the repo", paths[1:], ["tools/team/review.md"])
    check("preset: a missing preset warns", any("preset `missing-one` not found" in item for item in result["warnings"]), True)
    author = [item["path"] for item in project_config.resolve(root, ["a.tsx"], "author")["read"]]
    check("preset: author mode reads design.md only",
          [path.rsplit("/", 1)[-1] for path in author], ["design.md", "design.md"])


def git_cases():
    root = repo("git", {"src/a.tsx": "1\n", "src/b.tsx": "1\n", "AGENTS.md": "x"})
    def git(*args):
        subprocess.run(["git", "-C", root] + list(args), capture_output=True, check=True)
    git("init", "-q")
    git("-c", "user.email=t@example.invalid", "-c", "user.name=t", "add", ".")
    git("-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "one")
    with open(os.path.join(root, "src", "a.tsx"), "w", encoding="utf-8") as handle:
        handle.write("2\n")
    git("-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qam", "two")
    with open(os.path.join(root, "src", "b.tsx"), "w", encoding="utf-8") as handle:
        handle.write("2\n")
    with open(os.path.join(root, "src", "new.tsx"), "w", encoding="utf-8") as handle:
        handle.write("n\n")
    check("git: --diff range lists the committed change", project_config.changed_files(root, "HEAD~1..HEAD"), ["src/a.tsx"])
    check("git: no source lists the working tree and untracked files",
          project_config.changed_files(root), ["src/b.tsx", "src/new.tsx"])
    git("mv", "src/a.tsx", "src/renamed.tsx")
    git("-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "rename")
    check("git: a renamed file is listed under both names",
          project_config.changed_files(root, "HEAD~1..HEAD"), ["src/a.tsx", "src/renamed.tsx"])
    git("reset", "-q", "--soft", "HEAD~1")
    git("mv", "src/renamed.tsx", "src/a.tsx")
    check("git: --diff <sha> with no `..` reaches the working tree and new files",
          project_config.changed_files(root, "HEAD~1"), ["src/a.tsx", "src/b.tsx", "src/new.tsx"])
    git("add", "src/b.tsx")
    check("git: --staged lists the index", project_config.changed_files(root, staged=True), ["src/b.tsx"])
    code, _, err = run(root, "--diff", "nope..HEAD")
    check("git: a bad range exits 2", (code, "git diff" in err), (2, True))

    # One package of a diff: --files with --diff keeps the package, and names a file outside the diff.
    code, out, err = run(root, "--diff", "HEAD~1..HEAD", "--files", "src/a.tsx", "--mode", "review")
    check("git: --files with --diff reads the package", (code, "read: AGENTS.md" in out), (0, True))
    code, _, err = run(root, "--diff", "HEAD~1..HEAD", "--files", "src/b.tsx")
    check("git: --files outside the diff exits 2 and names the file", (code, "src/b.tsx" in err), (2, True))

    # A non-ASCII name with git's default quotepath, and a review record that is never code to review.
    git("config", "core.quotepath", "true")
    os.makedirs(os.path.join(root, ".fe-kit", "reviews"), exist_ok=True)
    for name in (os.path.join("src", "màn.tsx"), os.path.join(".fe-kit", "reviews", "main.md")):
        with open(os.path.join(root, name), "w", encoding="utf-8") as handle:
            handle.write("x\n")
    files = project_config.changed_files(root)
    check("git: a non-ASCII path comes back unquoted", "src/màn.tsx" in files, True)
    result = project_config.resolve(root, files, "review")
    check("git: .fe-kit/reviews is skipped with no config",
          ([s["file"] for s in result["skipped"]], ".fe-kit/reviews/main.md" in result["files"]),
          ([".fe-kit/reviews/main.md"], False))

    # root is a folder inside the repo: tracked and untracked paths share one base.
    web = os.path.join(root, "web")
    os.makedirs(os.path.join(web, "src"), exist_ok=True)
    with open(os.path.join(web, "src", "tracked.tsx"), "w", encoding="utf-8") as handle:
        handle.write("1\n")
    git("add", "web/src/tracked.tsx")
    git("-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-qm", "web")
    with open(os.path.join(web, "src", "tracked.tsx"), "w", encoding="utf-8") as handle:
        handle.write("2\n")
    with open(os.path.join(web, "src", "new.tsx"), "w", encoding="utf-8") as handle:
        handle.write("n\n")
    check("git: a sub-folder root lists both kinds relative to itself",
          project_config.changed_files(web), ["src/new.tsx", "src/tracked.tsx"])

    if os.name == "nt":
        other = "C:/x/a.tsx" if not root[:1].upper() == "C" else "D:/x/a.tsx"
        code, _, err = run(root, "--files", other)
        check("a path on another drive exits 2 with a message", (code, "another drive" in err), (2, True))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        glob_cases()
        fallback_cases()
        config_cases()
        error_cases()
        preset_cases()
        git_cases()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print("cases: %d, failures: %d" % (TOTAL[0], FAILURES[0]))
    sys.exit(FAILURES[0])
