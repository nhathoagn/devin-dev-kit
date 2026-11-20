"""Tests for scripts/handoff.py. Run: python3 scripts/test_handoff.py (exit code = failures).

Each case builds a small git repo, stages a source file, and checks the pre-commit handoff gate.
"""
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import handoff
import project_config

TMP = tempfile.mkdtemp(prefix="handoff-test-")
GOOD = """# Handoff
## 1. Logic
The form keeps one draft and posts it.
## 2. Implementation
- `src/a.tsx` reads the draft.
## 3. Decisions
Reuse the existing hook.
## 4. Debug without AI
Run `npm test`; open `src/a.tsx:1`.
## 5. Risks
None verified.
## 6. Q&A
- Q: What holds the draft? A: the hook.
"""

def repo(name="repo"):
    root = os.path.join(TMP, name)
    os.makedirs(os.path.join(root, "src"), exist_ok=True)
    subprocess.run(["git", "init", "-q", root], check=True)
    subprocess.run(["git", "-C", root, "config", "user.name", "Tester"], check=True)
    with open(os.path.join(root, "src", "a.tsx"), "w", encoding="utf-8") as handle:
        handle.write("export const a = 1;\n")
    subprocess.run(["git", "-C", root, "add", "-A"], check=True)
    return root

def write(root, text):
    path = os.path.join(root, ".fe-kit", "handoff.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)

def main():
    failures = 0
    def check(name, got, want):
        nonlocal failures
        failures += got != want
        print(("OK  " if got == want else "FAIL"), "%-52s %s" % (name, got))

    root = repo()
    check("no handoff is blocked", any("missing" in item for item in handoff.problems(root)), True)
    write(root, "# Handoff\n## 1. Logic\nx\n")
    found = handoff.problems(root)
    check("missing sections are named", sum("section" in item for item in found) >= 4, True)
    check("an unnamed file is named", any("src/a.tsx" in item for item in found), True)

    write(root, GOOD)
    check("complete handoff without approval still blocks", len(handoff.problems(root)), 2)
    check("approve accepts a complete handoff", handoff.approve(root, "Tester"), [])
    check("approved handoff passes", handoff.problems(root), [])

    time.sleep(1.1)
    with open(os.path.join(root, "src", "a.tsx"), "w", encoding="utf-8") as handle:
        handle.write("export const a = 2;\n")
    subprocess.run(["git", "-C", root, "add", "-A"], check=True)
    check("an edit after approval is stale", any("older" in item for item in handoff.problems(root)), True)

    empty = repo("empty")
    write(empty, "# Handoff\n")
    check("approve refuses an incomplete handoff", len(handoff.approve(empty, "Tester")) > 0, True)

    docs = repo("docs")
    with open(os.path.join(docs, "README.md"), "w", encoding="utf-8") as handle:
        handle.write("docs\n")
    subprocess.run(["git", "-C", docs, "rm", "--cached", "src/a.tsx"], check=True)
    subprocess.run(["git", "-C", docs, "add", "README.md"], check=True)
    check("a docs-only change needs no handoff", handoff.problems(docs), [])

    check("a file list override checks those files", any("src/a.tsx" in item for item in handoff.problems(root, ["src/a.tsx"])), True)

    settings = repo("settings")
    os.makedirs(os.path.join(settings, ".fe-kit"), exist_ok=True)
    with open(os.path.join(settings, ".fe-kit", "config.yaml"), "w", encoding="utf-8") as handle:
        handle.write('handoff: "off"\n')
    config, _ = project_config.load_config(settings)
    check("quoted off turns the gate off", config["handoff"], "off")
    with open(os.path.join(settings, ".fe-kit", "config.yaml"), "w", encoding="utf-8") as handle:
        handle.write("handoff: off\n")
    config, _ = project_config.load_config(settings)
    check("unquoted off is a YAML boolean and still turns it off", config["handoff"], "off")
    with open(os.path.join(settings, ".fe-kit", "config.yaml"), "w", encoding="utf-8") as handle:
        handle.write('handoff: "sometimes"\n')
    try:
        project_config.load_config(settings)
        check("an unknown handoff mode is rejected", "allow", "deny")
    except project_config.ConfigError:
        check("an unknown handoff mode is rejected", "deny", "deny")

    print("cases: %d, failures: %d" % (13, failures))
    return failures

if __name__ == "__main__":
    sys.exit(main())
