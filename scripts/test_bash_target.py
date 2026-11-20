"""Tests for scripts/bash_target.py. Run: python3 scripts/test_bash_target.py (exit code = failures).

Each case is one shell command and the target the gate must see, or "" when the command writes no
frontend file. The folder is the repo itself; a temp path is never a target.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("bash_target", os.path.join(HERE, "bash_target.py"))
bash_target = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bash_target)

CASES = [
    ("redirect to a frontend file", "printf x > src/A.tsx", "src/A.tsx"),
    ("redirect to a quoted frontend file", 'printf x > "src/A.tsx"', "src/A.tsx"),
    ("tee appends to a frontend file", "tee -a src/A.tsx", "src/A.tsx"),
    ("cp into a folder", "cp src/App.tsx components/button/", "components/button/App.tsx"),
    ("mv with a target folder", "mv -t dest/ src/App.tsx", "dest/App.tsx"),
    ("cp with a frontend destination", "cp src/App.tsx dest/B.tsx", "dest/B.tsx"),
    ("sed -i with a pipe script", "sed -i 's|foo|bar|' src/App.tsx", "src/App.tsx"),
    ("sed -i with two scripts", "sed -i -e 's/a/b/;s/c/d/' src/App.tsx", "src/App.tsx"),
    ("perl -i", "perl -pi -e 's|x|y|' src/App.tsx", "src/App.tsx"),
    ("declaration echo", 'echo "Runtime owner: A" "Decision: reuse"', ""),
    ("redirect text inside a label value", 'echo "Trigger: click Save > B.tsx" "Decision: reuse"', ""),
    ("grep for a write call", 'grep -rn "writeFileSync(\'src/App.tsx\')" scripts/', ""),
    ("commit message with a redirect", 'git commit -m "redirect stderr > src/App.tsx"', ""),
    ("git add of two python files", "git add scripts/fe-gate.py scripts/test_fe_gate.py", ""),
    ("git add of two tsx files", "git add src/A.tsx src/B.tsx", ""),
    ("the plugin test suite", "python3 -I scripts/test_fe_gate.py", ""),
    ("a node test file", "node --test extensions/fe-gate.test.ts", ""),
    ("a write to a temp folder", "printf x > /tmp/out.mjs", ""),
]

def run():
    failures = 0
    for name, command, want in CASES:
        got = bash_target.write_target(command, HERE)
        ok = got == want
        failures += not ok
        print(("OK  " if ok else "FAIL"), "%-42s %r%s" % (name, got, "" if ok else "  (want %r)" % want))
    print("cases: %d, failures: %d" % (len(CASES), failures))
    return failures

if __name__ == "__main__":
    sys.exit(run())
