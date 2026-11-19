"""Split a large diff into review packages, and merge the package reports into one report.

Run: python3 scripts/review_packages.py split --root <repo> [--diff BASE..HEAD | --staged] [--max 15] [--json]
     python3 scripts/review_packages.py merge --out <report.md> <package-1.md> <package-2.md> ...

split: a diff of more than 10 files gets one package per group of at most `--max` files. Files of one
folder stay in one package when they fit. Each package goes to its own reviewer, in parallel.
merge: joins the package reports without judgement: the worst verdict, every finding, the summed counts,
and the union of the rules read. The author runs it, so the author still writes no verdict.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project_config
import review_check

SPLIT_ABOVE = 10
DEFAULT_MAX = 15
COUNT_LABELS = ("Việc chặn đưa lên", "Việc nên sửa trong lượt này", "Việc có thể để sau")


def split(files, maximum=DEFAULT_MAX):
    """Return a list of packages, each a list of files, in path order."""
    if maximum < 1:
        raise ValueError("--max must be 1 or more")
    files = sorted(files)
    if len(files) <= SPLIT_ABOVE:
        return [files] if files else []
    groups = {}
    for path in files:
        groups.setdefault(os.path.dirname(path), []).append(path)
    packages = []
    current = []
    for folder in sorted(groups):
        group = groups[folder]
        if current and len(current) + len(group) > maximum:
            packages.append(current)
            current = []
        while len(group) > maximum:
            packages.append(group[:maximum])
            group = group[maximum:]
        current += group
    if current:
        packages.append(current)
    return packages


def _strip_verdict(sentence):
    for word in review_check.VERDICTS:
        if sentence.startswith(word):
            return sentence[len(word):].lstrip(" .")
    return sentence


def _join(lines):
    return "\n".join(lines).strip()


def merge(reports):
    """Return one report from the package reports, in package order."""
    parsed = [review_check.sections(text) for text in reports]
    verdicts = []
    conclusions = []
    for number, (text, parts) in enumerate(zip(reports, parsed), start=1):
        body = [line.strip() for line in parts.get("Kết luận", []) if line.strip()]
        first = body[0] if body else ""
        verdict = next((word for word in review_check.VERDICTS if first.startswith(word)), None)
        if verdict is None:
            raise ValueError("package %d has no verdict sentence under Kết luận" % number)
        verdicts.append(verdict)
        rest = _strip_verdict(" ".join(body))
        if rest:
            conclusions.append("Gói %d: %s" % (number, rest))
    worst = min(verdicts, key=review_check.VERDICTS.index)

    out = ["# Kết quả review", "", "## Kết luận", "", " ".join([worst + "."] + conclusions), ""]
    for name in ("Việc cần sửa", "Để yên"):
        blocks = [_join(parts.get(name, [])) for parts in parsed]
        blocks = [block for block in blocks if block]
        if blocks:
            out += ["## " + name, "", "\n\n".join(blocks), ""]

    totals = [0, 0, 0]
    for parts in parsed:
        summary = _join(parts.get("Tóm tắt", []))
        for index, label in enumerate(COUNT_LABELS):
            match = re.search(re.escape(label) + r":\s*(\d+)", summary)
            totals[index] += int(match.group(1)) if match else 0
    out += ["## Tóm tắt", "", " ".join("%s: %d." % (label, total) for label, total in zip(COUNT_LABELS, totals)), ""]

    rules = []
    gates = []
    coverage = []
    for text in reports:
        for item in re.split(r",\s*", review_check.label_value(text, "Luật đã đọc:") or ""):
            if item and item not in rules:
                rules.append(item)
        gate = review_check.label_value(text, "Cổng:")
        if gate and gate not in gates:
            gates.append(gate)
        cover = review_check.label_value(text, "Độ phủ:")
        if cover:
            coverage.append(cover)
    out += ["## Nguồn và độ phủ", "",
            "Luật đã đọc: " + (", ".join(rules) or "không có luật dự án"),
            "Cổng: " + (" · ".join(gates) or "chưa chạy (task không gửi kết quả)"),
            "Độ phủ: " + " · ".join(coverage), ""]
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Split a diff into review packages, or merge their reports.")
    commands = parser.add_subparsers(dest="command", required=True)
    split_cmd = commands.add_parser("split")
    split_cmd.add_argument("--root", default=".")
    project_config.add_source_arguments(split_cmd)
    split_cmd.add_argument("--max", type=int, default=DEFAULT_MAX)
    split_cmd.add_argument("--json", action="store_true")
    merge_cmd = commands.add_parser("merge")
    merge_cmd.add_argument("--out", required=True)
    merge_cmd.add_argument("reports", nargs="+")
    args = parser.parse_args(argv)
    try:
        if args.command == "split":
            root = os.path.abspath(args.root)
            files = project_config.files_from_args(root, args)
            kept = project_config.resolve(root, files, "review")["files"]
            packages = split(kept, args.max)
            if args.json:
                print(json.dumps([{"no": number, "files": package} for number, package in enumerate(packages, start=1)],
                                 ensure_ascii=False, indent=2))
            else:
                for number, package in enumerate(packages, start=1):
                    print("package %d (%d files): --files %s" % (number, len(package), " ".join(package)))
                print("packages: %d, files: %d" % (len(packages), len(kept)))
            return 0
        texts = []
        for path in args.reports:
            with open(path, encoding="utf-8") as handle:
                texts.append(handle.read())
        merged = merge(texts)
        with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(merged)
        print("merged %d reports into %s" % (len(texts), args.out))
        return 0
    except (OSError, ValueError, project_config.ConfigError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
