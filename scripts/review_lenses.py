"""Split a diff review into lenses: one fresh reviewer per lens, in parallel.

Run: python3 scripts/review_lenses.py list [--diff BASE..HEAD]
     python3 scripts/review_lenses.py items <lens>

list: print each lens and the checklist items it owns. One lens goes to one reviewer.
items: print the item codes of one lens, comma-separated, for a task brief.

Each item of `references/REVIEW_CHECKLIST.md` and `references/review-checks.md` sits in exactly
one lens, so six lens reports cover the whole checklist with no item read twice and none missed.
A lens reviewer may still report anything it sees; the split only guarantees coverage.
"""
import argparse
import re
import sys

LENSES = [
    {
        "name": "hygiene",
        "title": "Vệ sinh diff",
        "items": ["S1", "S2", "S3", "S4", "S5", "S6", "F1", "F11"],
    },
    {
        "name": "correctness",
        "title": "Đúng biên và luồng",
        "items": ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "F9", "F12", "F13", "F16", "F19"],
    },
    {
        "name": "contract",
        "title": "Hợp đồng, caller, spec, test",
        "items": ["C8", "F17", "F18", "F20"],
    },
    {
        "name": "structure",
        "title": "Kiến trúc và dùng lại",
        "items": ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9",
                  "F2", "F3", "F4", "F5", "F6", "F7", "F14", "F22", "F23"],
    },
    {
        "name": "naming",
        "title": "Tên và mở rộng",
        "items": ["N1", "N2", "N3", "N4", "N5", "E1", "E2", "E3", "E4", "E5", "E6",
                  "F8", "F15", "F21"],
    },
    {
        "name": "performance",
        "title": "Tải và hiệu năng",
        "items": ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "F10"],
    },
    {
        "name": "probe",
        "title": "Input xấu ở mọi boundary (pass 2)",
        "items": [],
        "brief": (
            "For every exported function in the diff, apply {undefined, null, \"\", \" \","
            " NaN, -1, 0} to each parameter and each field of each object parameter."
            " Report every case that silently accepts an invalid input, throws where the"
            " signature promises a typed result, returns a sentinel a caller cannot"
            " distinguish from a real value, or applies a default the caller never asked for."
        ),
    },
    {
        "name": "invariant",
        "title": "Invariant giữa các hàm (pass 2)",
        "items": [],
        "brief": (
            "List every function pair A -> B inside the diff where B reads a value A"
            " validates, computes, or owns. For each pair, write the invariant in one line"
            " (A promises X; B depends on X). Report every pair where the promise is"
            " narrower than the dependency — A checks fewer fields than B throws on,"
            " a validator that misses a field the consumer dereferences, or a Result/flag"
            " that does not cover a path the callee still takes."
        ),
    },
]

def by_name(name):
    for lens in LENSES:
        if lens["name"] == name:
            return lens
    raise KeyError(name)

def all_items():
    return [item for lens in LENSES for item in lens["items"]]

def coverage_gap(known_items):
    """Items the checklists own that no lens covers, and lens items the checklists lack."""
    owned = set(all_items())
    return sorted(set(known_items) - owned), sorted(owned - set(known_items))

def main(argv=None):
    parser = argparse.ArgumentParser(description="List the review lenses, or the items of one lens.")
    commands = parser.add_subparsers(dest="command", required=True)
    list_cmd = commands.add_parser("list")
    list_cmd.add_argument("--diff", default=None)
    items_cmd = commands.add_parser("items")
    items_cmd.add_argument("lens")
    brief_cmd = commands.add_parser("brief")
    brief_cmd.add_argument("lens")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            if args.diff:
                print("diff: %s" % args.diff)
            for number, lens in enumerate(LENSES, start=1):
                print("lens %d: %s (%s) — items %s"
                      % (number, lens["name"], lens["title"], " ".join(lens["items"])))
            print("lenses: %d" % len(LENSES))
            return 0
        if args.command == "brief":
            lens = by_name(args.lens)
            print(lens.get("brief") or lens["title"])
            return 0
        lens = by_name(args.lens)
        print(",".join(lens["items"]))
        return 0
    except KeyError:
        sys.stderr.write("error: unknown lens %s; one of %s\n"
                         % (args.lens, ", ".join(lens["name"] for lens in LENSES)))
        return 2

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
