"""Unit matrix for scripts/yaml_subset.py.

Run: python3 scripts/test_yaml_subset.py
The exit code is the number of failures. When PyYAML is installed, each valid case is also
compared with `yaml.safe_load`, so the subset never reads a value differently from real YAML.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml_subset

try:
    import yaml as pyyaml
except ImportError:
    pyyaml = None

VALID = [
    ("empty document", "", None),
    ("comment only", "# nothing\n", None),
    ("flat mapping", "version: 1\nname: fe-kit\n", {"version": 1, "name": "fe-kit"}),
    ("booleans and null", "a: true\nb: no\nc: null\nd: ~\ne:\n", {"a": True, "b": False, "c": None, "d": None, "e": None}),
    ("quoted keeps type", "a: \"1\"\nb: 'true'\n", {"a": "1", "b": "true"}),
    ("double-quoted escape", 'a: "x\\"y"\n', {"a": 'x"y'}),
    ("single-quoted escape", "a: 'it''s'\n", {"a": "it's"}),
    ("trailing comment", "a: b # note\nc: \"d # not a comment\"\n", {"a": "b", "c": "d # not a comment"}),
    ("hash inside plain value", "a: b#c\n", {"a": "b#c"}),
    ("flow list", 'a: [x, "y z", \'w\']\n', {"a": ["x", "y z", "w"]}),
    ("empty flow list", "a: []\n", {"a": []}),
    ("flow list with glob quoted", 'a: ["**/x.ts", "src/{a,b}/**"]\n', {"a": ["**/x.ts", "src/{a,b}/**"]}),
    ("block list indented", "a:\n  - x\n  - y\n", {"a": ["x", "y"]}),
    ("block list at key indent", "a:\n- x\n- y\nb: 1\n", {"a": ["x", "y"], "b": 1}),
    ("list of mappings", "rules:\n  - glob: \"src/**\"\n    read: [a.md, b.md]\n  - glob: \"lib/**\"\n    read:\n      - c.md\n",
     {"rules": [{"glob": "src/**", "read": ["a.md", "b.md"]}, {"glob": "lib/**", "read": ["c.md"]}]}),
    ("nested mapping", "legacy:\n  source: dev/\n  cr: \"works/{SID}.yaml\"\n", {"legacy": {"source": "dev/", "cr": "works/{SID}.yaml"}}),
    ("path plain value", "a: ./tools/fe-preset\n", {"a": "./tools/fe-preset"}),
    ("url plain value", "a: http://x/y\n", {"a": "http://x/y"}),
    ("document marker", "---\na: 1\n", {"a": 1}),
    ("crlf line ends", "a: 1\r\nb: 2\r\n", {"a": 1, "b": 2}),
    ("blank lines and comments between", "a:\n\n  # c\n  - x\n\nb: 2\n", {"a": ["x"], "b": 2}),
    ("top level list", "- a\n- b\n", ["a", "b"]),
    ("list item empty then block", "a:\n  -\n    b: 1\n", {"a": [{"b": 1}]}),
    ("unicode value", "a: \"luật dự án\"\n", {"a": "luật dự án"}),
    ("YAML 1.1 case forms", "a: True\nb: FALSE\nc: NULL\nd: Null\n", {"a": True, "b": False, "c": None, "d": None}),
    ("mixed case stays a string", "a: tRUE\nb: NuLL\n", {"a": "tRUE", "b": "NuLL"}),
    ("zero alone is a number", "a: 0\nb: -7\n", {"a": 0, "b": -7}),
]

INVALID = [
    ("tab indent", "a:\n\t- x\n", 2),
    ("unquoted alias start", "a: **/x.ts\n", 1),
    ("unquoted anchor", "a: &x 1\n", 1),
    ("flow mapping", "a: {b: 1}\n", 1),
    ("block scalar", "a: |\n  text\n", 1),
    ("colon in plain value", "a: b: c\n", 1),
    ("duplicate key", "a: 1\na: 2\n", 2),
    ("unclosed quote", "a: \"x\n", 1),
    ("text after quote", "a: \"x\" y\n", 1),
    ("bad indent", "a: 1\n  b: 2\n", 2),
    ("item where key expected", "a: 1\n- x\n", 2),
    ("flow list not closed", "a: [x, y\n", 1),
    ("flow list unquoted glob", "a: [**/x]\n", 1),
    ("not a key", "just text\n", 1),
    ("two documents", "a: 1\n---\nb: 2\n", 2),
    ("first line indented", "  a: 1\n", 1),
    ("leading zero number", "a: 0777\n", 1),
    ("brace in a flow item", "a: [src/{x,y}/**]\n", 1),
    ("colon in a flow item", "a: [x: y]\n", 1),
]

# The error names the quoted value to write, so the fix is one copy.
HINTS = [
    ("glob value", "exclude: **/x.ts\n", 'write "**/x.ts"'),
    ("glob list item", "exclude: [**/x.ts, b]\n", 'write "**/x.ts"'),
    ("colon value", "a: b: c\n", 'write "b: c"'),
    ("tab indent", "a:\n\t- x\n", "use spaces for indentation"),
    ("tab before the first key", "\ta: b\n", "use spaces for indentation"),
    ("leading zero", "a: 0777\n", 'write "0777"'),
]


def main():
    failures = 0
    for name, text, want in VALID:
        try:
            got = yaml_subset.load(text)
        except yaml_subset.YamlError as exc:
            got = "error: %s" % exc
        ok = got == want
        if ok and pyyaml is not None:
            ok = pyyaml.safe_load(text) == want
            if not ok:
                got = "pyyaml differs: %r" % (pyyaml.safe_load(text),)
        failures += not ok
        print(("OK  " if ok else "FAIL"), name + ("" if ok else "  (got %r)" % (got,)))
    for name, text, line in INVALID:
        try:
            yaml_subset.load(text)
            got = "no error"
        except yaml_subset.YamlError as exc:
            got = exc.line
        ok = got == line
        failures += not ok
        print(("OK  " if ok else "FAIL"), "error: " + name + ("" if ok else "  (got %r, want line %d)" % (got, line)))
    for name, text, hint in HINTS:
        try:
            yaml_subset.load(text)
            got = "no error"
        except yaml_subset.YamlError as exc:
            got = str(exc)
        ok = hint in got
        failures += not ok
        print(("OK  " if ok else "FAIL"), "hint: " + name + ("" if ok else "  (got %r)" % got))
    print("cases: %d, failures: %d, pyyaml cross-check: %s"
          % (len(VALID) + len(INVALID) + len(HINTS), failures, "on" if pyyaml else "off"))
    return failures


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
