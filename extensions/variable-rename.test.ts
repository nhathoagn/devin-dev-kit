// Run: npx tsx extensions/variable-rename.test.ts
// Variable renames are behavior changes, not wording/style — every call site,
// prop name, and destructured key could now point at something else.
// These cases assert the gate denies them; pure copy changes still pass.

let failures = 0;

function check(name: string, actual: unknown, expected: unknown) {
  const pass = actual === expected;
  if (!pass) {
    failures += 1;
  }
  console.log(`${pass ? "PASS" : "FAIL"} ${name}: ${JSON.stringify(actual)} (expected ${JSON.stringify(expected)})`);
}

// Same token-diff the gate runs: identifiers changed => deny.
// Import-free reimplementation of wording.wording_only's decision for these cases,
// kept tiny on purpose — the real gate is tested in scripts/test_wording.py.
function isRename(before: string, after: string): boolean {
  const ids = (s: string) =>
    (s.replace(/'[^']*'|"[^"]*"|`[^`]*`/g, "").match(/\b[A-Za-z_$][A-Za-z0-9_$]*\b/g) ?? []);
  const a = ids(before);
  const b = ids(after);
  if (a.length !== b.length) return false;
  return a.some((id, i) => id !== b[i]);
}

const renameCases: [string, string, string][] = [
  ["const rename", "const data = fetchOrders();", "const orders = fetchOrders();"],
  ["let rename", "let tmp = 0;", "let count = 0;"],
  ["var rename", "var t = 1;", "var total = 1;"],
  ["generic name still gated", "const data = 1;", "const info = 1;"],
  // Param renames
  ["function param rename", "function get(d) { return d; }", "function get(item) { return item; }"],
  ["arrow param rename", "const f = (x) => x + 1;", "const f = (n) => n + 1;"],
  // Pattern renames
  ["destructured key rename", "const { data } = res;", "const { orders } = res;"],
  ["for-of variable rename", "for (const d of list) { sum(d); }", "for (const item of list) { sum(item); }"],
  ["catch binding rename", "try { run(); } catch (e) { log(e); }", "try { run(); } catch (err) { log(err); }"],
  // Use-site renames
  ["identifier usage rename", "console.log(data);", "console.log(orders);"],
  ["member access rename", "const x = res.data;", "const x = res.orders;"],
  ["jsx prop name rename", "const x = <List data={rows} />;", "const x = <List items={rows} />;"],
  ["jsx handler value rename", "const x = <B onClick={save} />;", "const x = <B onClick={submit} />;"],
  ["declaration name rename", "function calc() {}", "function computeTotal() {}"],
  ["class name rename", "class Data {}", "class OrderRow {}"],
  // Mixed: rename rides along a copy change — still a rename.
  ["rename plus copy change", 'const buttonLabel = "Save";', 'const saveLabel = "Store";'],
];

for (const [name, before, after] of renameCases) {
  check(name, isRename(before, after), true);
}

const copyCases: [string, string, string][] = [
  ["copy named const is copy", "const buttonLabel = 'Save';", "const buttonLabel = 'Store';"],
  ["copy call is copy", "toast.success('Saved');", "toast.success('Done');"],
];

for (const [name, before, after] of copyCases) {
  check(name, isRename(before, after), false);
}

console.log(failures === 0 ? "\nAll checks passed" : `\n${failures} check(s) FAILED`);
process.exit(failures === 0 ? 0 : 1);
