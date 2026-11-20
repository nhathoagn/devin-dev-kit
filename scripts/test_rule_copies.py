"""Check that a rule sentence lives in one file.

Run: python3 scripts/test_rule_copies.py (exit code = number of copies).
A rule copied into a second file drifts: the next fix edits one copy and the agent still reads the other.
The hook injects rules/*.md on every request, so the skill points at them and does not repeat them.
Checked pairs: rules/*.md -> every skill file but CHANGELOG.md and evals/, and skills/fe-kit/SKILL.md -> its playbooks.
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_WORDS = 8


def sentences(path):
    with open(path, encoding="utf-8") as handle:
        text = re.sub(r"^---\n.*?\n---\n", "", handle.read(), count=1, flags=re.S)
    found = {}
    for number, line in enumerate(text.splitlines(), start=1):
        for sentence in re.split(r"(?<=[.!?])\s+", line.strip(" -|")):
            sentence = sentence.strip()
            if len(sentence.split()) >= MIN_WORDS:
                found.setdefault(sentence, number)
    return found


def rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def copies(sources, targets):
    out = []
    for source in sources:
        for sentence, line in sentences(source).items():
            for target in targets:
                hit = sentences(target).get(sentence)
                if hit and target != source:
                    out.append("%s:%d copied to %s:%d :: %s" % (rel(source), line, rel(target), hit, sentence[:90]))
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    rules = sorted(glob.glob(os.path.join(ROOT, "rules", "*.md")))
    # CHANGELOG and evals quote old rules as history and test input, not as rules an agent follows.
    skill_files = sorted(path for path in glob.glob(os.path.join(ROOT, "skills", "**", "*.md"), recursive=True)
                         if os.path.basename(path) != "CHANGELOG.md" and "evals" not in path.replace("\\", "/").split("/"))
    skill = os.path.join(ROOT, "skills", "fe-kit", "SKILL.md")
    playbooks = sorted(glob.glob(os.path.join(ROOT, "skills", "fe-kit", "playbooks", "*.md")))
    found = copies(rules, skill_files) + copies([skill], playbooks)
    for line in found:
        print("FAIL " + line)
    print("files: %d, copies: %d" % (len(rules) + len(skill_files), len(found)))
    sys.exit(len(found))
