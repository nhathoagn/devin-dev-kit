"""Split a diff review into lenses: one fresh reviewer per lens, in parallel.

Each lens carries a `pass` field. Pass 1 lenses grade the diff itself: the eight
checklist lenses plus `audit` (which applies `references/audit.md`). Pass 2
lenses — `probe` and `invariant` — run only when a fix adds a new contract
surface (a guard, validator, `Result` type, or signature); `correctness` and
`contract` run in both passes (pass `[1, 2]`). The `invariants` lenses —
`coverage` and `regression` — belong to a different playbook
(playbooks/review-invariants.md), used when the diff adds or changes tested
behaviour. Lenses with no checklist items answer a question about the diff or
the test suite, not a catalogue of defects.

Run: python3 scripts/review_lenses.py list [--pass 1|2|invariants] [--diff BASE..HEAD]
     python3 scripts/review_lenses.py items <lens>
     python3 scripts/review_lenses.py brief <lens>

list: print each lens of one pass (all lenses without --pass) and the checklist
items it owns. One lens goes to one reviewer.
items: print the item codes of one lens, comma-separated, for a task brief.
brief: print the task brief of a no-item lens (audit, probe, coverage,
regression, invariant).

Each item of `references/REVIEW_CHECKLIST.md` and `references/review-checks.md`
sits in exactly one lens, so the eight item lenses cover the whole checklist with
no item read twice and none missed (the `L1`-`L3` placeholder rows of the repo
rules table are excluded by design — they are filled per-repo, not owned here).
A lens reviewer may still report anything it sees; the split only guarantees coverage.
"""
import argparse
import re
import sys

LENSES = [
    {
        "name": "hygiene",
        "title": "Vệ sinh diff",
        "pass": 1,
        "items": ["S1", "S2", "S3", "S4", "S5", "S6", "R1", "R2", "R3", "R4",
                  "R5", "R6", "R7", "R8", "DOC1", "DOC2", "DOC3", "DOC4", "DOC5",
                  "F1", "F11"],
    },
    {
        "name": "correctness",
        "title": "Đúng biên và luồng",
        "pass": [1, 2],
        "items": ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "F9", "F12", "F13", "F16", "F19", "F25"],
    },
    {
        "name": "contract",
        "title": "Hợp đồng, caller, spec, test",
        "pass": [1, 2],
        "items": ["C8", "TY1", "TY2", "TY3", "TY4", "TY5", "TY6", "TY7", "TY8", "TY9",
                  "F17", "F18", "F20"],
    },
    {
        "name": "security",
        "title": "Bảo mật và input ngoài",
        "pass": 1,
        "items": ["SEC1", "SEC2", "SEC3", "SEC4", "SEC5", "SEC6", "SEC7", "SEC8",
                  "SEC9", "SEC10"],
    },
    {
        "name": "tests",
        "title": "Chất lượng test",
        "pass": 1,
        "items": ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10", "T11"],
    },
    {
        "name": "structure",
        "title": "Kiến trúc và dùng lại",
        "pass": 1,
        "items": ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9",
                  "F2", "F3", "F4", "F5", "F6", "F7", "F14", "F22", "F23", "F24"],
    },
    {
        "name": "naming",
        "title": "Tên và mở rộng",
        "pass": 1,
        "items": ["N1", "N2", "N3", "N4", "N5", "E1", "E2", "E3", "E4", "E5", "E6",
                  "F8", "F15", "F21"],
    },
    {
        "name": "performance",
        "title": "Tải và hiệu năng",
        "pass": 1,
        "items": ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "F10"],
    },
    {
        "name": "audit",
        "title": "Audit tech-lead: flow, lỗi, mở rộng",
        "pass": 1,
        "items": [],
        "brief": (
            "Apply `references/audit.md` to the diff. Run every lens in it that the"
            " checklist does not already cover: Architecture (a cross-feature import,"
            " a component calling the HTTP client, an opt-in no other caller uses, a"
            " removed export still alive or a new export with no caller), Operational"
            " flow (write the state transitions, then check double submit, two tabs,"
            " a late reply, reload or back, a lock reused from cache), Error handling"
            " (a dropped catch, one error class shown in two places, a mutation with"
            " no retry policy, a component checking `status === 500`), Extension"
            " (name the next likely change — a new status, field, or screen of the"
            " same kind — and count the files it must touch; a hand-kept list it"
            " must join is a finding). Skip the Reuse and Performance-and-load"
            " lenses: the checklist covers them. Report every judgement bullet that"
            " is true (`a.b().c()` walks, a component that only forwards, a"
            " component ignoring most of what it extends). A judgement finding"
            " carries `có thể để sau`; a real defect (a swallowed error, a double"
            " submit) carries its own level. Do not score the Fowler list. A lens"
            " with nothing wrong is omitted, not declared clean."
        ),
    },
    {
        "name": "probe",
        "title": "Input xấu ở mọi boundary (pass 2)",
        "pass": 2,
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
        "name": "coverage",
        "title": "Bất biến nào chưa có test (chế độ invariants)",
        "pass": "invariants",
        "items": [],
        "brief": (
            "Enumerate every invariant the diff must hold — stock never goes negative,"
            " one settled payload deducts once, money stays a safe integer, a rejected"
            " order moves nothing, same input yields the same key, a different payload on"
            " the same id is a conflict. For each invariant name the exact test that would"
            " fail if it broke. When no test exists, write NO TEST and give the smallest"
            " input that breaks it, then run that input. An invariant with neither a test"
            " nor a run is not reported as covered."
        ),
    },
    {
        "name": "regression",
        "title": "Bản sửa trước có phá bất biến không (chế độ invariants)",
        "pass": "invariants",
        "items": [],
        "brief": (
            "Compare the diff with the version it replaces. List every invariant the older"
            " version held that this one no longer holds, each with one input and the"
            " observed result on both sides. Do not list old defects the diff fixes; the"
            " question is what was lost. A behaviour that was deliberately tightened is"
            " listed separately as accepted, with the caller cost named."
        ),
    },
    {
        "name": "invariant",
        "title": "Invariant giữa các hàm (pass 2)",
        "pass": 2,
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

def _lens_passes(lens):
    value = lens.get("pass", 1)
    values = value if isinstance(value, list) else [value]
    return [str(item) for item in values]

def main(argv=None):
    parser = argparse.ArgumentParser(description="List the review lenses, or the items of one lens.")
    commands = parser.add_subparsers(dest="command", required=True)
    list_cmd = commands.add_parser("list")
    list_cmd.add_argument("--diff", default=None)
    list_cmd.add_argument(
        "--pass", dest="lens_pass", default="1",
        choices=["1", "2", "invariants", "all"],
        help="which pass the fan-out spawns; default 1",
    )
    items_cmd = commands.add_parser("items")
    items_cmd.add_argument("lens")
    brief_cmd = commands.add_parser("brief")
    brief_cmd.add_argument("lens")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            if args.diff:
                print("diff: %s" % args.diff)
            lenses = [lens for lens in LENSES
                      if args.lens_pass == "all" or args.lens_pass in _lens_passes(lens)]
            for number, lens in enumerate(lenses, start=1):
                items_text = " ".join(lens["items"]) or "-"
                print("lens %d: %s (%s, pass %s) — items %s"
                      % (number, lens["name"], lens["title"],
                         "+".join(_lens_passes(lens)), items_text))
            print("lenses: %d" % len(lenses))
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
