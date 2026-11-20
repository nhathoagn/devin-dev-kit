"""Check that every place that names the plugin version names the same one.

Run: python3 scripts/test_versions.py (exit code = number of mismatches).
A marketplace version behind plugin.json makes `/plugin install` keep the old build.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_json(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return json.load(handle)


def versions():
    marketplace = read_json(".claude-plugin/marketplace.json")
    found = [
        (".claude-plugin/plugin.json", read_json(".claude-plugin/plugin.json")["version"]),
        (".devin-plugin/plugin.json", read_json(".devin-plugin/plugin.json")["version"]),
        ("package.json", read_json("package.json")["version"]),
        (".claude-plugin/marketplace.json metadata", marketplace["metadata"]["version"]),
    ]
    found += [(".claude-plugin/marketplace.json plugins[%s]" % item["name"], item["version"])
              for item in marketplace["plugins"] if item["name"] == "fe-kit"]
    with open(os.path.join(ROOT, "skills", "fe-kit", "CHANGELOG.md"), encoding="utf-8") as handle:
        heading = re.search(r"^## (\d+\.\d+\.\d+)\s*$", handle.read(), re.M)
    found.append(("skills/fe-kit/CHANGELOG.md first heading", heading.group(1) if heading else "none"))
    return found


if __name__ == "__main__":
    found = versions()
    want = found[0][1]
    failures = 0
    for place, version in found:
        ok = version == want
        failures += not ok
        print(("OK  " if ok else "FAIL"), "%-50s %s" % (place, version) + ("" if ok else "  (want %s)" % want))
    print("cases: %d, failures: %d" % (len(found), failures))
    sys.exit(failures)
