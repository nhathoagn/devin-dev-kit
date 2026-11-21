"""Variable-rename changes are behavior changes, not wording/style.

A renamed identifier is a changed token — every call site, prop name, and
destructured key could now point at something else. The gate must deny them
all (False = gated), including renames that only touch one declaration.

Run: python3 scripts/test_variable_rename.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import wording  # noqa: E402

CASES = [
    # Declaration renames — all gated.
    ("const rename", "const data = fetchOrders();\n", "const orders = fetchOrders();\n", False),
    ("let rename", "let tmp = 0;\n", "let count = 0;\n", False),
    ("var rename", "var t = 1;\n", "var total = 1;\n", False),
    ("generic name still gated", "const data = 1;\n", "const info = 1;\n", False),
    ("function param rename",
     "function get(d) { return d; }\n",
     "function get(item) { return item; }\n", False),
    ("arrow param rename", "const f = (x) => x + 1;\n", "const f = (n) => n + 1;\n", False),
    ("destructured key rename",
     "const { data } = res;\n",
     "const { orders } = res;\n", False),
    ("for-of variable rename",
     "for (const d of list) { sum(d); }\n",
     "for (const item of list) { sum(item); }\n", False),
    ("catch binding rename",
     "try { run(); } catch (e) { log(e); }\n",
     "try { run(); } catch (err) { log(err); }\n", False),

    # Rename at use sites — gated too.
    ("identifier usage rename",
     "console.log(data);\n",
     "console.log(orders);\n", False),
    ("member access rename",
     "const x = res.data;\n",
     "const x = res.orders;\n", False),
    ("jsx prop name rename",
     "const x = <List data={rows} />;\n",
     "const x = <List items={rows} />;\n", False),
    ("jsx handler value rename",
     "const x = <B onClick={save} />;\n",
     "const x = <B onClick={submit} />;\n", False),
    ("declaration name rename",
     "function calc() {}\n",
     "function computeTotal() {}\n", False),
    ("class name rename", "class Data {}\n", "class OrderRow {}\n", False),

    # Mixed: rename rides along a real copy change — still gated.
    ("rename plus copy change",
     'const buttonLabel = "Save";\n',
     'const saveLabel = "Store";\n', False),

    # Controls: pure copy/style still passes.
    ("copy named const is copy",
     "const buttonLabel = 'Save';\n",
     "const buttonLabel = 'Store';\n", True),
    ("copy call is copy",
     "toast.success('Saved');\n",
     "toast.success('Done');\n", True),
]


def main():
    failures = 0
    for name, old, new, expected in CASES:
        actual = wording.wording_only(old, new)
        ok = actual == expected
        if not ok:
            failures += 1
        print("%s  %-14s %s" % ("OK  " if ok else "FAIL", "allow" if expected else "deny", name))
    print("cases: %d, failures: %d" % (len(CASES), failures))
    return failures


if __name__ == "__main__":
    sys.exit(main())
