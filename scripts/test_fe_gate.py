"""Tests for scripts/fe-gate.py. Run: python scripts/test_fe_gate.py (exit code = number of failures).

Each case writes a small transcript and a source file, sends one hook payload to the gate as UTF-8
bytes, and checks the decision: allow, deny, or deny+bug (deny that also asks for Trigger:, Expected:,
Actual:). `FE_GATE_NO_FLUSH=1` keeps the deny path fast; the late-write case removes it.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "fe-gate.py")
TMP = tempfile.mkdtemp(prefix="fe-gate-test-")
ENV = dict(os.environ, FE_ARCH_ROOT=os.path.dirname(HERE), FE_GATE_NO_FLUSH="1",
           FE_GATE_STATE_DIR=os.path.join(TMP, "state"))

def U(text, **extra):
    return dict({"type": "user", "message": {"role": "user", "content": text}}, **extra)

def A(blocks):
    return {"type": "assistant", "message": {"role": "assistant", "content": blocks}}

def T(text):
    return [{"type": "text", "text": text}]

def THINK(text):
    return [{"type": "thinking", "thinking": text}]

def write_transcript(name, entries):
    path = os.path.join(TMP, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path

def call_gate(payload, env=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    result = subprocess.run([sys.executable, "-I", GATE], input=data, capture_output=True, env=env or ENV)
    return result.stdout.decode("utf-8")

def decision(output):
    if '"deny"' not in output:
        return "allow"
    return "deny+bug" if "Trigger:" in output else "deny"

def pre_tool(entries, tool=None, extra=None, source=None):
    transcript = write_transcript("main.jsonl", entries)
    name, tool_input = tool or ("Write", {"file_path": "src/B.tsx", "content": "x"})
    if name in ("Edit", "MultiEdit") and isinstance(tool_input.get("file_path"), str):
        target = os.path.join(TMP, tool_input["file_path"])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if source is None:
            if name == "Edit":
                source = tool_input.get("old_string", "")
            else:
                edits = tool_input.get("edits") or []
                source = "\n".join(edit.get("old_string", "") for edit in edits if isinstance(edit, dict))
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(source)
    payload = {"hook_event_name": "PreToolUse", "tool_name": name, "tool_input": tool_input,
               "transcript_path": transcript, "cwd": TMP}
    payload.update(extra or {})
    return decision(call_gate(payload))

def E(old, new, path="src/components/confirm/confirm-dialog.tsx"):
    return ("Edit", {"file_path": path, "old_string": old, "new_string": new})

def chat(user, blocks):
    return [U(user), A(blocks)]

OK = "Runtime owner: OrderForm\nDecision: extend\n"
REPRO = "Trigger: click Save\nExpected: 10\nActual: 0\n"

STASH_USER = "đang lỗi tôi không apply stash mới nhất đc"
SUMMARY = THINK("Stash apply đang gây conflict ở `ConfirmDialog` (dòng 120–151 có marker); tôi sẽ giữ footer upstream và dùng lại `toHalfKanaNode` từ stash để gỡ conflict này.")
BLOCK = """                            {visible.confirmText ?? t('labels.button.OK')}
                        </AlertDialogAction>
                    ) : null}
=======
                <AlertDialogFooter className="gap-2 border-t border-border bg-muted px-4 py-2.5 sm:gap-2">
                        {/* @cr CR-half-width-kana: button text shows katakana in half-width. */}
                        {toHalfKanaNode(visible.confirmText ?? t('labels.button.OK'))}
                    </AlertDialogAction>
>>>>>>> Stashed changes"""
COMBINED = """                            {/* @cr CR-half-width-kana: button text shows katakana in half-width. */}
                            {toHalfKanaNode(visible.confirmText ?? t('labels.button.OK'))}
                        </AlertDialogAction>
                    ) : null}"""
WIDTH = """<<<<<<< HEAD
                    'gap-0 overflow-hidden p-0 sm:w-max sm:min-w-sm sm:max-w-2xl',
=======
                    'gap-0 overflow-hidden rounded-xl border-0 p-0 shadow-md sm:max-w-[27rem]',
>>>>>>> develop"""
WIDTH_MERGED = "                    'gap-0 overflow-hidden rounded-xl border-0 p-0 shadow-md sm:w-max sm:min-w-sm sm:max-w-[27rem]',"
M2 = "<<<<<<< HEAD\n  <A x={1} />\n=======\n  <A x={2} />\n>>>>>>> develop"
D3 = "<<<<<<< HEAD\n  <A x={1} />\n||||||| base\n  <A x={0} />\n=======\n  <A x={2} />\n>>>>>>> develop"
NEW_CODE = "                            {toHalfKanaNode(visible.confirmText ?? props.label ?? 'OK')}"

# (name, transcript entries, tool or None, expected)
CASES = [
    # Label formats.
    ("plain labels", chat("add field", T(OK)), None, "allow"),
    ("bold, colon outside", chat("add field", T("**Runtime owner**: OrderForm\n**Decision**: extend")), None, "allow"),
    ("bold, colon inside", chat("add field", T("**Runtime owner:** OrderForm\n**Decision:** extend")), None, "allow"),
    ("italic labels", chat("add field", T("_Runtime owner_: OrderForm\n_Decision_: extend")), None, "allow"),
    ("lowercase reuse decision", chat("add field", T("Runtime owner: OrderForm\nReuse decision: extend")), None, "allow"),
    ("Runtime Owner capital", chat("add field", T("Runtime Owner: OrderForm\nDecision: extend")), None, "allow"),
    ("Decision N/A upper", chat("add field", T("Runtime owner: OrderForm\nDecision: N/A, merge only")), None, "allow"),
    ("Decision Extend capital", chat("add field", T("Runtime owner: OrderForm\nDecision: Extend")), None, "allow"),
    ("full-width colon", chat("add field", T("Runtime owner： OrderForm\nDecision： extend")), None, "allow"),
    ("backquoted values", chat("add field", T("Runtime owner: `OrderForm`\nDecision: `extend`")), None, "allow"),
    ("thinking with labels", chat("add field", THINK(OK)), None, "allow"),
    ("labels written by the user", [U(OK + "thêm cột"), A(T("ok"))], None, "allow"),
    ("decision under a Reuse Decision heading", chat("làm đi sửa ở BE", T("## Architecture\n- Runtime owner: `src/pages/ca3020-seiban-header.tsx:34`.\n\n## Reuse Decision\n- Responsibility: show the label.\n- BE side: **reuse**. The labels come from labelMap.\n- FE side: **reuse** of the rej_reason_name pattern.")), None, "allow"),
    ("decision word outside the Reuse Decision section", chat("add field", T("## Reuse Decision\n- Responsibility: x\n\n## Notes\n- BE side: **reuse**\nRuntime owner: OrderForm")), None, "deny"),
    ("Reuse Decision heading with the template only", chat("add field", T("Runtime owner: OrderForm\n## Reuse Decision\n- Decision: reuse | extend | feature-local | shared")), None, "deny"),
    ("empty labels", chat("add field", T("Runtime owner:\nDecision:")), None, "deny"),
    ("SKILL.md template", chat("add field", T("- Runtime owner:\n- Decision: reuse | extend | feature-local | shared")), None, "deny"),
    ("SKILL.md backquoted template", chat("add field", T("- Runtime owner:\n- Decision: `reuse` | `extend` | `feature-local` | `shared`")), None, "deny"),
    ("table row", chat("add field", T("| Runtime owner: OrderForm | Decision: extend |")), None, "deny"),
    ("empty thinking", chat("add field", THINK("")), None, "deny"),
    ("prose names the fields", chat("add field", T("Write Runtime owner, then Decision, then edit.")), None, "deny"),
    ("no decision word", chat("add field", T("Runtime owner: OrderForm\nDecision: maybe later")), None, "deny"),
    ("labels only in a tool result", [U("thêm cột"), {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": OK}]}}], None, "deny"),
    ("labels only in a meta entry", [U("thêm cột"), U(OK, isMeta=True)], None, "deny"),
    ("labels only in a system-reminder", [U("thêm cột <system-reminder>" + OK + "</system-reminder>")], None, "deny"),
    # Prose and a thinking summary name the owner, but carry no label.
    ("prose owner and decision", chat("đổi đi", T("Tôi xác định chủ sở hữu là AuthenticatedLayout và quyết định tái sử dụng code cũ.")), None, "deny"),
    ("thinking summary without labels", chat("đổi đi", THINK("Hook fe-kit đang chặn, nên tôi xác định chủ sở hữu là `AuthenticatedLayout` và quyết định tái sử dụng code cũ.")), None, "deny"),
    ("labels before a new request", [U("sửa footer"), A(T(OK)), U("đổi đi và liệt kê các trường hợp"), A(T("Tôi chuyển sang hướng 1."))], None, "deny"),
    # A Bash command that writes a frontend file is gated like Write.
    ("bash redirect into .tsx", chat("đổi đi", T("Tôi sửa file.")), ("Bash", {"command": "git show HEAD:src/a.tsx | sed 's/x//' > src/a.tsx && npx prettier --write src/a.tsx"}), "deny"),
    ("bash redirect into .tsx with labels", chat("đổi đi", T(OK)), ("Bash", {"command": "git show HEAD:src/a.tsx | sed 's/x//' > src/a.tsx"}), "allow"),
    ("bash sed -i on .tsx", chat("đổi đi", T("x")), ("Bash", {"command": "sed -i \"62s/a/b/\" tvmk_admin/src/pages/x-columns.tsx"}), "deny"),
    ("bash perl -pi on .jsx", chat("đổi đi", T("x")), ("Bash", {"command": "perl -pi -e 's/a/b/' src/A.jsx"}), "deny"),
    ("bash tee into .vue", chat("đổi đi", T("x")), ("Bash", {"command": "echo x | tee -a src/A.vue"}), "deny"),
    ("bash cp onto .tsx", chat("đổi đi", T("x")), ("Bash", {"command": "cp /c/x/backup.txt src/A.tsx"}), "deny"),
    ("bash node writeFileSync on .tsx", chat("đổi đi", T("x")), ("Bash", {"command": "node -e \"require('fs').writeFileSync('src/A.tsx', s)\""}), "deny"),
    ("bash script into scratchpad", chat("đổi đi", T("x")), ("Bash", {"command": "cat > /c/Users/U/AppData/Local/Temp/claude/s/scratchpad/check.mjs <<'EOF'\nx\nEOF"}), "allow"),
    ("bash redirect into /tmp .js", chat("đổi đi", T("x")), ("Bash", {"command": "echo x > /tmp/run.js"}), "allow"),
    ("bash read-only on .tsx", chat("đổi đi", T("x")), ("Bash", {"command": "grep -n footer src/A.tsx 2>/dev/null; git diff -- src/A.tsx"}), "allow"),
    ("bash stderr redirect", chat("đổi đi", T("x")), ("Bash", {"command": "npx tsc --noEmit 2>&1 | head"}), "allow"),
    ("bash prettier on .tsx", chat("đổi đi", T("x")), ("Bash", {"command": "npx prettier --write src/A.tsx && npx eslint src/A.tsx"}), "allow"),
    ("bash write into .ts stays open", chat("đổi đi", T("x")), ("Bash", {"command": "echo x > src/a.ts"}), "allow"),
    # A script that builds the path in a variable names only the extension.
    ("bash node loop writes variable .tsx paths", chat("đổi đi", T("x")), ("Bash", {"command": "node -e \"for (const f of files.filter(x => x.endsWith('.tsx'))) fs.writeFileSync(f, s)\""}), "deny"),
    ("bash node reads .tsx, writes json", chat("đổi đi", T("x")), ("Bash", {"command": "node -e \"const s = fs.readFileSync('src/A.tsx', 'utf8'); fs.writeFileSync('out.json', s)\""}), "allow"),
    ("bash python Path(...).write_text on .tsx", chat("đổi đi", T("x")), ("Bash", {"command": "python -c \"from pathlib import Path; Path('src/A.tsx').write_text(s)\""}), "deny"),
    ("bash sed -i over a loop variable", chat("đổi đi", T("x")), ("Bash", {"command": "for f in $(cat list.txt | grep columns.tsx); do sed -i 's/a/b/' \"$f\"; done"}), "deny"),
    ("bash variable target", chat("đổi đi", T("x")), ("Bash", {"command": "F=src/A.tsx; echo x > \"$F\""}), "deny"),
    # A relative path after cd into a scratchpad folder is a throwaway file.
    ("bash node edits a script after cd scratchpad", chat("đổi đi", T("x")), ("Bash", {"command": "SP=\"C:/Users/U/AppData/Local/Temp/claude/s/scratchpad\"; cd \"$SP\"; node -e \"let s=fs.readFileSync('hdr.js','utf8'); fs.writeFileSync('hdr.js', s)\""}), "allow"),
    ("bash sed -i on a script after cd scratchpad", chat("đổi đi", T("x")), ("Bash", {"command": "cd /tmp/s; sed -i \"s#'CA30': #'CA31': 'ca30/ca3031/x-columns.tsx',#\" check.js"}), "allow"),
    ("bash cd scratchpad, then cd repo and write .tsx", chat("đổi đi", T("x")), ("Bash", {"command": "cd /tmp/s; node probe.js; cd /d/code/app; sed -i 's/a/b/' src/A.tsx"}), "deny"),
    # Bug mode.
    ("bug, bold repro labels", chat("tổng sai", T(OK + "**Trigger**: click\n**Expected**: 10\n**Actual**: 0")), None, "allow"),
    ("bug, lowercase repro labels", chat("tổng sai", T(OK + "trigger: click\nexpected: 10\nactual: 0")), None, "allow"),
    ("bug, no repro", chat("tổng sai", T(OK)), None, "deny+bug"),
    ("bug, empty Actual", chat("tổng sai", T(OK + "Trigger: click\nExpected: 10\nActual:")), None, "deny+bug"),
    ("'hiển thị sai' is a bug report", chat("ngày hiển thị sai", T(OK)), None, "deny+bug"),
    ("'sai chính tả' is not a bug report", chat("sửa sai chính tả nút Lưu", T(OK)), None, "allow"),
    ("old bug, then new request", [U("tổng sai"), A(T("fixed")), U("thêm cột ngày"), A(T(OK))], None, "allow"),
    ("bug, then 'làm đi'", [U("tổng sai"), A(T(OK)), U("làm đi")], None, "deny+bug"),
    ("bug, then interrupt", [U("tổng sai"), A(T(OK)), U("[Request interrupted by user]")], None, "deny+bug"),
    # Request scope.
    ("labels for an earlier task", [U("thêm cột A"), A(T(OK)), U("thêm cột B"), A(T("ok"))], None, "deny"),
    ("labels, then 'ok'", [U("thêm cột A"), A(T(OK)), U("ok")], None, "allow"),
    ("labels before compact", [U("thêm cột A"), A(T(OK)), U("Summary: the user asked to add a column. đang lỗi build.", isCompactSummary=True), U("tiếp tục")], None, "allow"),
    ("compact summary alone is not a bug report", [U("thêm cột A"), A(T(OK)), U("Summary: lỗi build earlier.", isCompactSummary=True)], None, "allow"),
    # One-line edits that are not conflicts.
    ("one line: className tweak", [U("đổi màu nút")], E("  <B className='p-1' />", "  <B className='p-2' />", "src/B.tsx"), "allow"),
    ("one line: JSX text wording", [U("sửa chữ")], E("  <p>Save</p>", "  <p>Store</p>", "src/B.tsx"), "allow"),
    ("one line: new handler", [U("sửa nút")], E("  <B label='x' />", "  <B label='x' onClick={save} />", "src/B.tsx"), "deny"),
    ("one line: new call", [U("sửa nút")], E("  {label}", "  {toHalf(label)}", "src/B.tsx"), "deny"),
    ("one line: changed value", [U("sửa bảng")], E("  <T limit={10} />", "  <T limit={20} />", "src/B.tsx"), "deny"),
    ("one line: new ?? default", [U("sửa nút")], E("  {label}", "  {label ?? 'OK'}", "src/B.tsx"), "deny"),
    # From a replay of real sessions: lines that change no behavior.
    ("one line: class list inside a multi-line string", [U("sửa")], E("        h-14.5 min-h-14.5", "        h-15.5 min-h-15.5", "src/B.tsx"), "allow"),
    ("one line: class list with arbitrary values", [U("sửa")], E("  [&>svg]:translate-y-0 [&>img]:translate-y-0\"", "  [&>svg]:translate-y-0 [&>svg]:self-center [&>img]:translate-y-0\"", "src/B.tsx"), "allow"),
    ("one line: // comment", [U("sửa")], E("  // Design: the chevron sits 8px from the edge.", "  // Design: the chevron starts 8px from the outer edge.", "src/B.tsx"), "allow"),
    ("one line: JSX comment", [U("sửa")], E("  {/* Until the search ends. */}", "  {/* Until the whole search ends. */}", "src/B.tsx"), "allow"),
    ("one line: doc comment", [U("sửa")], E("/** Design system button. */", "/** Design system button (Button.svg). */", "src/B.tsx"), "allow"),
    ("one line: import list", [U("sửa")], E("import { RotateCcw, Ban } from 'lucide-react';", "import { RotateCcw, Ban, ChevronRight } from 'lucide-react';", "src/B.tsx"), "allow"),
    ("one line: class string opens here", [U("sửa")], E('        className="inline-flex h-8 shrink-0 items-center', '        className="inline-flex h-5 shrink-0 items-center', "src/B.tsx"), "allow"),
    ("one line: class string closes here", [U("sửa")], E('        px-3 text-sm font-semibold text-primary">', '        px-3 text-sm font-medium text-brand-strong">', "src/B.tsx"), "allow"),
    ("one line: open JSX comment", [U("sửa")], E("  {/* The search buttons wait for the lock */}", "  {/* A search waits for the lock session, so its read shows. */}", "src/B.tsx"), "allow"),
    ("one line: comment end", [U("sửa")], E("   A file is a download link. */", "   A file is a ダウンロード link. */", "src/B.tsx"), "allow"),
    ("one line: export list", [U("sửa")], E("export { Alert, AlertTitle };", "export { Alert, AlertTitle, alertVariants };", "src/B.tsx"), "allow"),
    ("one line: first line of an import list", [U("sửa")], E("import { useCallback, useMemo,", "import { useCallback, useEffect, useMemo,", "src/B.tsx"), "allow"),
    ("one line: import with module on the next line", [U("sửa")], E("import { codeName, LOCKED_CLASS } from", "import { codeName } from", "src/B.tsx"), "allow"),
    ("one line: class string in cn()", [U("sửa")], E("    month: cn('flex flex-col w-full gap-4', defaultClassNames.month),", "    month: cn('flex flex-col w-full gap-2', defaultClassNames.month),", "src/B.tsx"), "allow"),
    ("one line: object key with a class string", [U("sửa")], E("    sm: 'h-8 rounded-md gap-1.5 px-3',", "    sm: 'h-7 rounded-md gap-1.5 px-3',", "src/B.tsx"), "allow"),
    ("one line: class string end with a hex color", [U("sửa")], E("bg-[#FFFFFF33]',", "bg-[#FFFFFF34]',", "src/B.tsx"), "allow"),
    ("one line: object flag is not a class list", [U("sửa")], E("    open: true,", "    open: false,", "src/B.tsx"), "deny"),
    ("one line: object number is not a class list", [U("sửa")], E("    max-rows: 10,", "    max-rows: 20,", "src/B.tsx"), "deny"),
    ("one line: key with a class string value change", [U("sửa")], E("    month: 'gap-4',", "    month: 'gap-2',", "src/B.tsx"), "allow"),
    ("one line: camelCase word is not a class list", [U("sửa")], E("  emptyRow", "  emptyRow={t('M00001')}", "src/B.tsx"), "deny"),
    ("one line: code after a closing class string", [U("sửa")], E('        px-3">', '        px-3" onClick={save}>', "src/B.tsx"), "deny"),
    ("one line: code before an open string", [U("sửa")], E('  <B a={x} label="one', '  <B a={y} label="one', "src/B.tsx"), "deny"),
    # From the same replay: lines that do change behavior.
    ("one line: hook deps change", [U("sửa")], E("  }, [fitRows, isEmpty]);", "  }, [fitRows, height, isEmpty]);", "src/B.tsx"), "deny"),
    ("one line: condition change", [U("sửa")], E("const failed = shouldSearch && isError && !isFetching;", "const failed = shouldSearch && mutation.isError;", "src/B.tsx"), "deny"),
    ("one line: new prop value", [U("sửa")], E("  emptyRow", "  emptyRow={t('M00001')}", "src/B.tsx"), "deny"),
    ("one line: new call argument", [U("sửa")], E("q.useCatalog('sales-persons');", "q.useCatalog('sales-persons', {});", "src/B.tsx"), "deny"),
    ("one line: arithmetic is not a class list", [U("sửa")], E("  total - discount", "  total + discount", "src/B.tsx"), "deny"),
    ("one line: code after a URL string", [U("sửa")], E("  fetchUrl('http://a/b')", "  fetchUrl('http://a/b', opts)", "src/B.tsx"), "deny"),
    # Conflict edits (from renew-core sessions).
    ("stash: remove one marker line", [U(STASH_USER), A(SUMMARY)], E("<<<<<<< Updated upstream\n                <AlertDialogFooter", "                <AlertDialogFooter"), "allow"),
    ("stash: combine sides", [U(STASH_USER), A(SUMMARY)], E(BLOCK, COMBINED), "allow"),
    ("stash: new code, no labels", [U(STASH_USER), A(SUMMARY)], E(BLOCK, NEW_CODE), "deny"),
    ("stash: new code, labels, no bug fields", [U(STASH_USER), A(T(OK))], E(BLOCK, NEW_CODE), "allow"),
    ("merge: width classes in one line", [U("fix conflict")], E(WIDTH, WIDTH_MERGED), "allow"),
    ("conflict: one line with a new call", [U("fix conflict")], E(M2, "  <A x={toHalf(2)} />"), "deny"),
    ("conflict: one line with a new ??", [U("fix conflict")], E(M2, "  <A x={y ?? 2} />"), "deny"),
    ("conflict: CRLF, pick one side", [U("fix conflict")], E(M2.replace("\n", "\r\n"), "  <A x={2} />"), "allow"),
    ("conflict: diff3, pick base", [U("fix conflict")], E(D3, "  <A x={0} />"), "allow"),
    ("conflict: diff3, new ||", [U("fix conflict")], E(D3, "  <A x={a || 2} />"), "deny"),
    ("conflict: keeps a marker", [U("fix conflict")], E(M2, "=======\n  <A x={2} />"), "deny"),
    ("conflict via MultiEdit", [U("fix conflict")], ("MultiEdit", {"file_path": "src/B.tsx", "edits": [{"old_string": M2, "new_string": "  <A x={2} />"}]}), "deny"),
    ("conflict via Write", [U("fix conflict")], ("Write", {"file_path": "src/B.tsx", "content": "x"}), "deny"),
    ("non-conflict edit after 'lỗi'", [U(STASH_USER), A(T(OK))], E("  a\n  b", "  a\n  c", "src/B.tsx"), "deny+bug"),
    # Wording across file types and multi-line edits.
    ("wording: jsx text own line", [U("đổi text")], E("  <p>\n    Bạn có chắc?\n  </p>", "  <p>\n    Bạn chắc chứ?\n  </p>", "src/B.tsx"), "allow"),
    ("wording: multi-line paragraph", [U("đổi text")], E("  <p>\n    Dòng một\n    Dòng hai\n  </p>", "  <p>\n    Dòng một mới\n    Dòng hai mới\n  </p>", "src/B.tsx"), "allow"),
    ("wording: MultiEdit", [U("đổi text")], ("MultiEdit", {"file_path": "src/B.tsx", "edits": [
        {"old_string": "  <p>Save</p>", "new_string": "  <p>Store</p>"},
        {"old_string": "  <B label=\"A\" />", "new_string": "  <B label=\"B\" />"},
    ]}), "allow"),
    ("wording: comment mentions useState", [U("đổi text")], E("// reset useState here\nconst x = 1;", "// reset the useState hook here\nconst x = 1;", "src/B.tsx"), "allow"),
    ("wording: multi-line template", [U("đổi text")], E("const label = `Dòng một\nDòng hai`;", "const label = `Dòng một mới\nDòng hai mới`;", "src/B.tsx"), "allow"),
    ("wording: .js label", [U("đổi text")], E("const label = 'Save';", "const label = 'Store';", "src/B.js"), "allow"),
    ("wording: .jsx label", [U("đổi text")], E("const label = 'Save';", "const label = 'Store';", "src/B.jsx"), "allow"),
    ("behavior: .js fetch url", [U("đổi text")], E("fetch('/api/v1');", "fetch('/api/v2');", "src/B.js"), "deny"),
    ("behavior: .mjs export value", [U("đổi text")], E("export const API_URL = '/v1';", "export const API_URL = '/v2';", "src/B.mjs"), "deny"),
    ("behavior: .cjs key", [U("đổi text")], E("const key = 'token';", "const key = 'auth';", "src/B.cjs"), "deny"),
    ("behavior: .mdx is gated", [U("đổi text")], E("const label = 'Save';", "const label = 'Store';", "src/B.mdx"), "deny"),
    ("behavior: .astro is gated", [U("đổi text")], E("const label = 'Save';", "const label = 'Store';", "src/B.astro"), "deny"),
    ("behavior: import source path", [U("sửa import")], E("import { A } from './a';", "import { A } from './b';", "src/B.tsx"), "deny"),
    ("behavior: enum value", [U("sửa status")], E("const status = 'ACTIVE';", "const status = 'INACTIVE';", "src/B.tsx"), "deny"),
    ("behavior: apostrophe then handler", [U("sửa text")], E("const x = <p>Don't <B /> save</p>;", "const x = <p>Don't <B onClick={save} /> save</p>;", "src/B.tsx"), "deny"),

    # Decisions and scope.
    ("Decision: do not reuse", chat("add field", T("Runtime owner: OrderForm\nDecision: do not reuse, write new")), E("  <B limit={10} />", "  <B limit={20} />", "src/B.tsx"), "deny"),
    ("Decision: no shared", chat("add field", T("Runtime owner: OrderForm\nDecision: no shared")), E("  <B limit={10} />", "  <B limit={20} />", "src/B.tsx"), "deny"),
    ("Owner: TBD", chat("add field", T("Runtime owner: TBD\nDecision: reuse")), E("  <B limit={10} />", "  <B limit={20} />", "src/B.tsx"), "deny"),
    ("stale labels, new task", [U("thêm cột A"), A(T(OK)), U("đổi limit bảng 10 thành 20")], E("  <B limit={10} />", "  <B limit={20} />", "src/B.tsx"), "deny"),
    ("wording prompt with lỗi is not bug mode", [U("sửa lỗi chính tả trong B"), A(T("Runtime owner: OrderForm\nDecision: reuse"))], E("  <B limit={10} />", "  <B limit={20} />", "src/B.tsx"), "allow"),
    ("text prompt with lỗi is not bug mode", [U("Text nút X bị lỗi hiển thị, đổi thành Y"), A(T("Runtime owner: OrderForm\nDecision: reuse"))], E("  <B limit={10} />", "  <B limit={20} />", "src/B.tsx"), "allow"),
    ("plugin bug prompt is not bug mode", [U("plugin fe-kit bị lỗi"), A(T("Runtime owner: OrderForm\nDecision: reuse"))], E("  <B limit={10} />", "  <B limit={20} />", "src/B.tsx"), "allow"),
    ("ast_edit path-only is gated", [U("add field")], ("MultiEdit", {"file_path": "src/B.tsx"}), "deny"),
    ("Write path-only is gated", [U("add field")], ("Write", {"file_path": "src/B.tsx"}), "deny"),

    # File types.
    (".ts file is not gated", [U("add field")], ("Edit", {"file_path": "src/b.ts", "old_string": "a\nb", "new_string": "c\nd"}), "allow"),
    (".vue file is gated", [U("add field")], ("Edit", {"file_path": "src/B.vue", "old_string": "a\nb", "new_string": "c\nd"}), "deny"),
]

SOURCE = {
    "one line: class list inside a multi-line string":
        'const x = <B\n  className="inline-flex\n        h-14.5 min-h-14.5\n  text-sm"\n/>;\n',
    "one line: class list with arbitrary values":
        'const x = <B\n  className="flex\n  [&>svg]:translate-y-0 [&>img]:translate-y-0"\n/>;\n',
    "one line: class string opens here":
        'const x = <B\n        className="inline-flex h-8 shrink-0 items-center\n        px-3 text-sm"\n/>;\n',
    "one line: class string closes here":
        'const x = <B\n        className="inline-flex\n        px-3 text-sm font-semibold text-primary">\n</B>;\n',
    "one line: comment end":
        "/**\n   A file is a download link. */\nconst x = 1;\n",
    "one line: import with module on the next line":
        "import { codeName, LOCKED_CLASS } from\n  './module';\nconst x = 1;\n",
    "one line: class string end with a hex color":
        "const x = { month: 'flex bg-[#FFFFFF33]', };\n",
}

def run_cases():
    failures = 0
    for name, entries, tool, want in CASES:
        got = pre_tool(entries, tool, source=SOURCE.get(name))
        failures += got != want
        print(("OK  " if got == want else "FAIL"), "%-8s %s" % (want, name) + ("" if got == want else "  (got %s)" % got))
    return failures

SPECIAL_TOTAL = [0]

def run_special():
    failures = 0
    def check(name, got, want):
        nonlocal failures
        SPECIAL_TOTAL[0] += 1
        failures += got != want
        print(("OK  " if got == want else "FAIL"), "%-8s %s" % (want, name) + ("" if got == want else "  (got %s)" % got))

    # Subagent: the main transcript has no labels, the subagent transcript has them.
    main = write_transcript("sess.jsonl", [U("thêm cột")])
    write_transcript(os.path.join("sess", "subagents", "agent-abc.jsonl"), [U("thêm cột, edit B.tsx"), A(T(OK))])
    base = {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": "src/B.tsx", "content": "x"},
            "transcript_path": main, "cwd": TMP}
    check("subagent labels, agent_id given", decision(call_gate(dict(base, agent_id="abc"))), "allow")
    check("subagent labels, no agent_id", decision(call_gate(base)), "deny")

    # The reply text reaches the transcript 0.5 seconds after the hook starts.
    late = write_transcript("late.jsonl", [U("thêm cột")])
    def append_later():
        time.sleep(0.5)
        with open(late, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(A(T(OK))) + "\n")
    thread = threading.Thread(target=append_later)
    thread.start()
    slow_env = {key: value for key, value in ENV.items() if key != "FE_GATE_NO_FLUSH"}
    check("labels written 0.5 s late", decision(call_gate(dict(base, transcript_path=late), env=slow_env)), "allow")
    thread.join()

    # The deny message names the missing line, so the agent does not retry the same edit.
    only_owner = write_transcript("owner.jsonl", chat("add field", T("Runtime owner: OrderForm")))
    out = call_gate(dict(base, transcript_path=only_owner))
    check("deny names the missing Decision line", "allow" if "Not found after the latest request: `Decision:`" in out and "Runtime owner:` with a name" not in out.split("Not found")[1] else "deny", "allow")

    # UserPromptSubmit reads a Vietnamese prompt as UTF-8.
    def injects(prompt):
        out = call_gate({"hook_event_name": "UserPromptSubmit", "prompt": prompt, "cwd": TMP})
        return "allow" if "behaviorless by what it changes" in out else "deny"
    check("vi prompt 'đang lỗi màn hình trắng' injects rules (allow = injected)", injects("đang lỗi màn hình trắng"), "allow")
    check("vi prompt 'đổi màu nút' injects no impl rule (deny = none)", injects("đổi màu nút"), "deny")
    check("prompt naming fe-kit injects rules", injects("sử dung fe-kit để review repo"), "allow")
    check("prompt naming skill://fe-kit injects rules", injects("read skill://fe-kit first"), "allow")

    # The deny message says that prose, a thinking summary, and labels of an earlier request do not count.
    prose = write_transcript("prose.jsonl", chat("đổi đi", T("Chủ sở hữu là AuthenticatedLayout.")))
    out = call_gate(dict(base, transcript_path=prose))
    check("deny explains prose and earlier labels", "allow" if "prose, and a table row do not count" in out and "before the latest user message" in out else "deny", "allow")
    bash = dict(base, transcript_path=prose, tool_name="Bash", tool_input={"command": "sed -i 's/a/b/' src/A.tsx"})
    check("bash deny names the Bash route", "allow" if "Bash command that writes a frontend file" in call_gate(bash) else "deny", "allow")

    # A script file run through a variable is read from disk, so its writes count too.
    scripts = os.path.join(TMP, "scratchpad")
    os.makedirs(scripts, exist_ok=True)
    def run_script(file_name, source):
        script = os.path.join(scripts, file_name)
        with open(script, "w", encoding="utf-8") as handle:
            handle.write(source)
        return decision(call_gate(dict(base, transcript_path=prose, tool_name="Bash",
                                       tool_input={"command": 'S="%s"; node "$S"' % script.replace("\\", "/")})))
    check("script file that writes .tsx paths in a loop", run_script("rename.mjs",
          "for (const f of files) if (f.endsWith('.tsx')) fs.writeFileSync(f, fix(fs.readFileSync(f, 'utf8')));"), "deny")
    check("script file that writes only json", run_script("probe.mjs",
          "const cols = fs.readFileSync('src/A-columns.tsx', 'utf8');\nfs.writeFileSync('out.json', cols);"), "allow")

    # A wording prompt must not drag in the reuse/modules bundle.
    def reuse_injected(prompt):
        out = call_gate({"hook_event_name": "UserPromptSubmit", "prompt": prompt, "cwd": TMP})
        return "allow" if "Duplicated code means" in out else "deny"
    check("sửa text injects no reuse bundle", reuse_injected("sửa text nút Lưu"), "deny")
    check("sửa copy injects no reuse bundle", reuse_injected("sửa copy màn chi tiết"), "deny")
    check("đổi text injects nothing", reuse_injected("đổi text nút Lưu"), "deny")
    check("sửa lỗi chính tả injects no bug rules", injects("sửa lỗi chính tả"), "deny")
    def comments_injected(prompt):
        out = call_gate({"hook_event_name": "UserPromptSubmit", "prompt": prompt, "cwd": TMP})
        return "allow" if "Default to deleting comments" in out else "deny"
    check("frontend prompt injects comments rule", comments_injected("thêm component OrderForm"), "allow")
    check("sửa text injects no comments rule", comments_injected("sửa text nút Lưu"), "deny")

    # A repo with .fe-kit/config.yaml gets the project rules command; every review gets the command.
    with_config = os.path.join(TMP, "with-config")
    os.makedirs(os.path.join(with_config, ".git"), exist_ok=True)
    os.makedirs(os.path.join(with_config, ".fe-kit"), exist_ok=True)
    with open(os.path.join(with_config, ".fe-kit", "config.yaml"), "w", encoding="utf-8") as handle:
        handle.write("rules: []\n")
    no_config = os.path.join(TMP, "no-config")
    os.makedirs(os.path.join(no_config, ".git"), exist_ok=True)
    def prompt_out(prompt, root):
        env = dict(ENV)
        env.pop("CLAUDE_PROJECT_DIR", None)
        return call_gate({"hook_event_name": "UserPromptSubmit", "prompt": prompt, "cwd": root}, env=env)
    config_out = prompt_out("thêm component OrderForm", with_config)
    check("config repo: frontend prompt names .fe-kit/config.yaml and --mode author",
          "allow" if ".fe-kit/config.yaml" in config_out and "--mode author" in config_out else "deny", "allow")
    check("no-config repo: frontend prompt has no config line",
          "allow" if ".fe-kit/config.yaml" not in prompt_out("thêm component OrderForm", no_config) else "deny", "allow")
    check("review prompt always carries the project rules command",
          "allow" if "Project rules command: python3" in prompt_out("review diff trước commit", no_config)
          and "project_config.py" in prompt_out("review diff trước commit", no_config) else "deny", "allow")
    check("wording prompt in a config repo gets no config line",
          "allow" if ".fe-kit/config.yaml" not in prompt_out("đổi màu nút", with_config) else "deny", "allow")

    # An echo declaration is read from the Bash payload, so a thinking block or a late transcript write does not lose it.
    def declare(transcript, command, agent_id=None):
        payload = dict(base, transcript_path=transcript, tool_name="Bash", tool_input={"command": command})
        if agent_id:
            payload["agent_id"] = agent_id
        return call_gate(payload)
    def edit(transcript, agent_id=None):
        payload = dict(base, transcript_path=transcript)
        if agent_id:
            payload["agent_id"] = agent_id
        return decision(call_gate(payload))
    declared = write_transcript("declare.jsonl", [U("thêm cột vào DA1020"), A(THINK(""))])
    check("edit with no labels before a declaration", edit(declared), "deny")
    out = declare(declared, 'echo "Runtime owner: Da1020Columns" "Decision: feature-local"')
    check("declaration is allowed and confirmed", "allow" if '"deny"' not in out and "recorded" in out else "deny", "allow")
    check("edit after an echo declaration", edit(declared), "allow")

    renewed = write_transcript("declare-new.jsonl", [U("thêm cột vào DA1020"), A(THINK(""))])
    declare(renewed, 'echo "Runtime owner: Da1020Columns" "Decision: reuse"')
    with open(renewed, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(U("giờ sửa màn DA1021 header")) + "\n")
    check("declaration of an earlier request does not count", edit(renewed), "deny")
    continued = write_transcript("declare-ok.jsonl", [U("thêm cột vào DA1020")])
    declare(continued, 'echo "Runtime owner: Da1020Columns" "Decision: reuse"')
    with open(continued, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(U("ok")) + "\n")
    check("declaration survives a continuation reply", edit(continued), "allow")

    placeholder = write_transcript("declare-ph.jsonl", [U("thêm cột vào DA1020")])
    declare(placeholder, 'echo "Runtime owner: <the component or hook that runs B.tsx>" "Decision: <reuse|extend|feature-local|shared|n/a>"')
    check("copied placeholder declaration does not count", edit(placeholder), "deny")
    printf = write_transcript("declare-printf.jsonl", [U("thêm cột vào DA1020")])
    declare(printf, "printf 'Runtime owner: Da1020Columns\\nDecision: extend\\n'")
    check("printf declaration with a backslash-n counts", edit(printf), "allow")
    for label, command in (("pipe", 'echo "Runtime owner: A" "Decision: reuse" | tee log.txt'),
                           ("chain", 'echo "Runtime owner: A" "Decision: reuse" && ls'),
                           ("substitution", 'echo "Runtime owner: $(whoami)" "Decision: reuse"'),
                           ("grep", 'grep -n "Runtime owner: A" "Decision: reuse" rules')):
        other = write_transcript("declare-%s.jsonl" % label, [U("thêm cột vào DA1020")])
        out = declare(other, command)
        check("%s is not a declaration" % label, "allow" if out.strip() == "" and edit(other) == "deny" else "deny", "allow")
    redirect = write_transcript("declare-redirect.jsonl", [U("thêm cột vào DA1020")])
    check("echo with labels into a .tsx file is gated", decision(declare(redirect, 'echo "Runtime owner: A" "Decision: reuse" > src/B.tsx')), "deny")

    bug = write_transcript("declare-bug.jsonl", [U("tổng sai khi bấm Lưu ở DA1020")])
    declare(bug, 'echo "Runtime owner: Da1020Form" "Decision: extend"')
    check("bug edit with owner and decision only", edit(bug), "deny+bug")
    declare(bug, 'echo "Trigger: click Save" "Expected: 10" "Actual: 0"')
    check("bug edit after a second declaration adds the repro", edit(bug), "allow")

    shared = write_transcript("declare-sub.jsonl", [U("thêm cột vào DA1020")])
    declare(shared, 'echo "Runtime owner: Da1020Columns" "Decision: reuse"')
    check("subagent edit sees the main declaration", edit(shared, agent_id="sub1"), "allow")
    own = write_transcript("declare-sub-own.jsonl", [U("thêm cột vào DA1020")])
    declare(own, 'echo "Runtime owner: Da1020Columns" "Decision: reuse"', agent_id="sub2")
    check("main agent edit does not see a subagent declaration", edit(own), "deny")
    check("subagent edit sees its own declaration", edit(own, agent_id="sub2"), "allow")

    # The echo is also read from the transcript's Bash tool_use, so a state entry keyed by a request
    # the host had not flushed yet cannot drop a declaration the agent already ran.
    def bash_echo(command):
        return {"type": "tool_use", "id": "tool-1", "name": "Bash", "input": {"command": command}}
    def tools(*blocks):
        return {"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}}
    DECLARE_ECHO = 'echo "Runtime owner: Da1020Columns" "Decision: reuse"'
    transcript_only = write_transcript("declare-transcript.jsonl", [U("thêm cột vào DA1020"), tools(bash_echo(DECLARE_ECHO))])
    check("session: a transcript echo counts without a state entry",
          decision(call_gate(dict(base, transcript_path=transcript_only, session_id="cc-transcript"))), "allow")
    stale = write_transcript("declare-transcript-old.jsonl",
                             [U("thêm cột vào DA1020"), tools(bash_echo(DECLARE_ECHO)), U("giờ sửa màn DA1021 header")])
    check("session: a transcript echo before the latest request does not count",
          decision(call_gate(dict(base, transcript_path=stale, session_id="cc-stale"))), "deny")
    parallel = write_transcript("declare-parallel.jsonl", [U("thêm cột vào DA1020"), tools(
        bash_echo(DECLARE_ECHO), {"type": "tool_use", "id": "tool-2", "name": "Edit", "input": {"file_path": "src/B.tsx"}})])
    check("session: an echo in the same message as the edit counts",
          decision(call_gate(dict(base, transcript_path=parallel, session_id="cc-parallel"))), "allow")

    # A host notice is a user entry that no person typed, so it does not start a new request.
    notice = "<task-notification>\n<task-id>a1</task-id>\n<status>completed</status>\n</task-notification>"
    check("labels survive a task notification",
          edit(write_transcript("notice-1.jsonl", [U("thêm cột"), A(T(OK)),
                                                   U(notice, origin={"kind": "task-notification"})])), "allow")
    check("labels survive a notice with no origin field",
          edit(write_transcript("notice-2.jsonl", [U("thêm cột"), A(T(OK)), U(notice)])), "allow")
    check("labels survive /export",
          edit(write_transcript("notice-3.jsonl", [U("thêm cột"), A(T(OK)),
                                                   U("<command-name>/export</command-name>\n<command-message>export</command-message>"),
                                                   U("<local-command-stdout>Conversation copied to clipboard</local-command-stdout>")])), "allow")
    check("labels inside a task notification do not count",
          edit(write_transcript("notice-4.jsonl", [U("thêm cột"),
                                                   U(notice.replace("</status>", "</status>\n" + OK),
                                                     origin={"kind": "task-notification"})])), "deny")
    check("a typed request after a notice still starts a new request",
          edit(write_transcript("notice-5.jsonl", [U("thêm cột"), A(T(OK)), U(notice, origin={"kind": "task-notification"}),
                                                   U("giờ sửa màn DA1021", origin={"kind": "human"})])), "deny")
    noticed = write_transcript("notice-6.jsonl", [U("thêm cột vào DA1020")])
    declare(noticed, 'echo "Runtime owner: Da1020Columns" "Decision: reuse"')
    with open(noticed, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(U(notice, origin={"kind": "task-notification"})) + "\n")
    check("echo declaration survives a task notification", edit(noticed), "allow")

    # omp writes a new transcript file on every call, so the session id keys the declaration.
    first = write_transcript("omp-1.jsonl", [U("thêm cột vào DA1020")])
    second = write_transcript("omp-2.jsonl", [U("thêm cột vào DA1020")])
    call_gate(dict(base, transcript_path=first, session_id="omp-s1", tool_name="Bash",
                   tool_input={"command": 'echo "Runtime owner: Da1020Columns" "Decision: reuse"'}))
    check("session id carries a declaration to a new transcript file",
          decision(call_gate(dict(base, transcript_path=second, session_id="omp-s1"))), "allow")
    check("another session id does not see it",
          decision(call_gate(dict(base, transcript_path=second, session_id="omp-s2"))), "deny")

    # With a session id, Claude's labels count only from a declaration. Text the user typed still counts.
    def sess_edit(name, entries, session="cc-1", transcript=True):
        payload = dict(base, session_id=session)
        payload["transcript_path"] = write_transcript(name, entries) if transcript else ""
        return decision(call_gate(payload))
    check("session: reply-text labels do not count", sess_edit("s-reply.jsonl", chat("thêm cột", T(OK))), "deny")
    check("session: thinking labels do not count", sess_edit("s-think.jsonl", chat("thêm cột", THINK(OK))), "deny")
    check("session: subagent reply-text labels do not count",
          decision(call_gate(dict(base, agent_id="abc", session_id="cc-sub"))), "deny")
    check("session: labels the user typed count", sess_edit("s-user.jsonl", [U(OK + "thêm cột"), A(T("ok"))]), "allow")
    bug_s = write_transcript("s-bug2.jsonl", [U("tổng sai khi bấm Lưu\nTrigger: bấm Lưu\nExpected: 10\nActual: 0")])
    call_gate(dict(base, transcript_path=bug_s, session_id="cc-bug", tool_name="Bash",
                   tool_input={"command": 'echo "Runtime owner: Da1020Form" "Decision: extend"'}))
    check("session: bug repro typed by the user plus an echo declaration",
          decision(call_gate(dict(base, transcript_path=bug_s, session_id="cc-bug"))), "allow")
    echo_s = write_transcript("s-echo.jsonl", [U("thêm cột vào DA1020"), A(T(OK))])
    call_gate(dict(base, transcript_path=echo_s, session_id="cc-echo", tool_name="Bash",
                   tool_input={"command": 'echo "Runtime owner: Da1020Columns" "Decision: reuse"'}))
    check("session: echo declaration counts", decision(call_gate(dict(base, transcript_path=echo_s, session_id="cc-echo"))), "allow")
    call_gate(dict(base, transcript_path="", session_id="cc-none", tool_name="Bash",
                   tool_input={"command": 'echo "Runtime owner: Da1020Columns" "Decision: reuse"'}))
    check("session: echo declaration counts with no transcript path",
          sess_edit("unused.jsonl", [], session="cc-none", transcript=False), "allow")
    started = time.time()
    call_gate(dict(base, transcript_path=write_transcript("s-slow.jsonl", [U("thêm cột")]), session_id="cc-slow"), env=slow_env)
    check("session: a deny does not wait for a late transcript write",
          "allow" if time.time() - started < 2 else "deny", "allow")
    sess_out = call_gate(dict(base, transcript_path=write_transcript("s-msg.jsonl", [U("thêm cột")]), session_id="cc-msg"))
    sess_reason = json.loads(sess_out)["hookSpecificOutput"]["permissionDecisionReason"]
    check("session: deny says reply text does not count and offers no reply-text path",
          "allow" if "Labels in the reply text, in thinking, or in prose do not count" in sess_reason
          and "also counts" not in sess_reason else "deny", "allow")

    lead = call_gate(dict(base, transcript_path=write_transcript("lead.jsonl", [U("thêm cột")])))
    reason = json.loads(lead)["hookSpecificOutput"]["permissionDecisionReason"]
    check("deny starts with the command and names the file",
          "allow" if reason.startswith("Blocked. Run this Bash command") and 'echo "Runtime owner: <the component or hook that runs B.tsx>"' in reason else "deny", "allow")
    return failures

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    total = run_cases() + run_special()
    print("cases: %d, failures: %d" % (len(CASES) + SPECIAL_TOTAL[0], total))
    sys.exit(total)
