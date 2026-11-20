"""Unit matrix for scripts/wording.py.

Run: python3 scripts/test_wording.py
The exit code is the number of failures.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wording

JSX = "const x = <p>%s</p>;\n"
ATTR = "const x = <B %s />;\n"

CASES = [
    # Copy and style that should pass without labels.
    ("jsx text between tags", JSX % "Save", JSX % "Store", True),
    ("jsx text on its own line",
     "const x = (\n  <p>\n    Bạn có chắc chắn muốn xóa?\n  </p>\n);\n",
     "const x = (\n  <p>\n    Bạn chắc chắn muốn xóa chứ?\n  </p>\n);\n", True),
    ("button label on its own line",
     "const x = (\n  <button>\n    Xóa đơn\n  </button>\n);\n",
     "const x = (\n  <button>\n    Xóa\n  </button>\n);\n", True),
    ("text before an inline tag",
     "const x = <p>Chào bạn, <strong>x</strong></p>;\n",
     "const x = <p>Xin chào, <strong>x</strong></p>;\n", True),
    ("text after an inline tag",
     "const x = <p><strong>Lưu ý</strong> không thể hoàn tác.</p>;\n",
     "const x = <p><strong>Lưu ý</strong> không thể hủy.</p>;\n", True),
    ("text after an expression",
     "const x = <p>{count} đơn hàng</p>;\n",
     "const x = <p>{count} đơn</p>;\n", True),
    ("text with question marks", JSX % "Bạn chắc chắn?", JSX % "Bạn chắc chắn??", True),
    ("text with &&", JSX % "A và B", JSX % "A && B", True),
    ("text with ||", JSX % "A hoặc B", JSX % "A || B", True),
    ("text with arrow", JSX % "A đến B", JSX % "A => B", True),
    ("text with await", JSX % "chờ A", JSX % "await A", True),
    ("text with fetch", JSX % "tải A", JSX % "fetch A", True),
    ("text with if paren", JSX % "nếu A", JSX % "if (A", True),
    ("comment mentions useState",
     "// reset useState here\nconst x = <B />;\n",
     "// reset the useState hook here\nconst x = <B />;\n", True),
    ("paragraph over two lines",
     "const x = (\n  <p>\n    Dòng một\n    Dòng hai\n  </p>\n);\n",
     "const x = (\n  <p>\n    Dòng một mới\n    Dòng hai mới\n  </p>\n);\n", True),
    ("template copy over two lines",
     "const label = `Dòng một\nDòng hai`;\n",
     "const label = `Dòng một mới\nDòng hai mới`;\n", True),
    ("template copy substitution text",
     "const label = `Hi ${name}`;\n",
     "const label = `Hello ${name}`;\n", True),
    ("object label property",
     "const data = { label: 'Save' };\n",
     "const data = { label: 'Store' };\n", True),
    ("object errorMessage property",
     "const data = { errorMessage: 'Bad' };\n",
     "const data = { errorMessage: 'Invalid' };\n", True),
    ("const EMPTY_TEXT",
     "const EMPTY_TEXT = 'A';\n",
     "const EMPTY_TEXT = 'B';\n", True),
    ("const buttonLabel",
     "const buttonLabel = 'A';\n",
     "const buttonLabel = 'B';\n", True),
    ("labels object value",
     "const LABELS = { save: 'Lưu' };\n",
     "const LABELS = { save: 'Lưu lại' };\n", True),
    ("copy call t", "const x = t('a');\n", "const x = t('b');\n", True),
    ("copy call i18n.t", "const x = i18n.t('a');\n", "const x = i18n.t('b');\n", True),
    ("copy call alert", "alert('a');\n", "alert('b');\n", True),
    ("copy call toast.success", "toast.success('a');\n", "toast.success('b');\n", True),
    ("title attribute", ATTR % "title=\"A\"", ATTR % "title=\"B\"", True),
    ("aria-label attribute", ATTR % "aria-label=\"A\"", ATTR % "aria-label=\"B\"", True),
    ("placeholder attribute", ATTR % "placeholder=\"A\"", ATTR % "placeholder=\"B\"", True),
    ("alt attribute", ATTR % "alt=\"A\"", ATTR % "alt=\"B\"", True),
    ("label attribute", ATTR % "label=\"A\"", ATTR % "label=\"B\"", True),
    ("emptyText attribute", ATTR % "emptyText=\"A\"", ATTR % "emptyText=\"B\"", True),
    ("title attribute expression", ATTR % "title={t('a')}", ATTR % "title={t('b')}", True),
    ("jsx child ternary strings",
     "const x = <p>{idle ? 'Đang chờ' : 'Đang xử lý'}</p>;\n",
     "const x = <p>{idle ? 'Chờ' : 'Đang xử lý'}</p>;\n", True),
    ("jsx child logical string",
     "const x = <p>{cond && 'Save'}</p>;\n",
     "const x = <p>{cond && 'Store'}</p>;\n", True),
    ("className", ATTR % "className=\"p-1\"", ATTR % "className=\"p-2\"", True),
    ("multi-line className",
     "const x = <B\n  className=\"inline-flex\n    px-3 text-sm\"\n/>;\n",
     "const x = <B\n  className=\"inline-flex\n    px-3 text-lg\"\n/>;\n", True),
    ("cn style argument", "const x = cn('a', 'b');\n", "const x = cn('a', 'c');\n", True),
    ("style key sm", "const sizes = { sm: 'h-8' };\n", "const sizes = { sm: 'h-7' };\n", True),
    ("style key month", "const x = { month: 'gap-4' };\n", "const x = { month: 'gap-2' };\n", True),
    ("export specifier addition",
     "export { A };\n", "export { A, B };\n", True),
    ("import specifier addition",
     "import { A } from 'x';\n", "import { A, B } from 'x';\n", True),
    ("comment only change",
     "// old note\nconst x = 1;\n", "// new note\nconst x = 1;\n", True),
    ("whitespace only change",
     "const x = 1;\n", "const   x  =   1;\n", True),
    ("regex plus comment",
     "const re = /a\\/b/; // old\n", "const re = /a\\/b/; // new\n", True),
    ("style array value",
     "const classes = ['p-1'];\n", "const classes = ['p-2'];\n", True),

    # Behavior changes that must be gated.
    ("apostrophe then handler",
     "const x = <p>Don't <B /> save</p>;\n",
     "const x = <p>Don't <B onClick={save} /> save</p>;\n", False),
    ("object flag change",
     "const x = { open:true };\n", "const x = { open:false };\n", False),
    ("import source path",
     "import { A } from './a';\n", "import { A } from './b';\n", False),
    ("side effect import path",
     "import './a';\n", "import './b';\n", False),
    ("fetch url",
     "fetch('/api/v1/orders');\n", "fetch('/api/v2/orders');\n", False),
    ("enum value",
     "const status = 'ACTIVE';\n", "const status = 'INACTIVE';\n", False),
    ("storage key",
     "localStorage.getItem('token');\n", "localStorage.getItem('auth');\n", False),
    ("route path",
     "const route = { path: '/orders' };\n", "const route = { path: '/orders-v2' };\n", False),
    ("href attribute", ATTR % "href=\"/a\"", ATTR % "href=\"/b\"", False),
    ("src attribute", ATTR % "src=\"/a.png\"", ATTR % "src=\"/b.png\"", False),
    ("value attribute", ATTR % "value=\"a\"", ATTR % "value=\"b\"", False),
    ("data-testid attribute", ATTR % "data-testid=\"a\"", ATTR % "data-testid=\"b\"", False),
    ("value property",
     "const x = { value: 'ACTIVE' };\n", "const x = { value: 'INACTIVE' };\n", False),
    ("new handler",
     "const x = <B label='x' />;\n", "const x = <B label='x' onClick={save} />;\n", False),
    ("new call", "const x = <p>{label}</p>;\n", "const x = <p>{toHalf(label)}</p>;\n", False),
    ("changed prop value",
     "const x = <T limit={10} />;\n", "const x = <T limit={20} />;\n", False),
    ("new nullish default",
     "const x = <p>{label}</p>;\n", "const x = <p>{label ?? 'OK'}</p>;\n", False),
    ("condition change",
     "const x = a && b;\n", "const x = a || b;\n", False),
    ("hook deps change",
     "const x = useMemo(fn, [fitRows, isEmpty]);\n",
     "const x = useMemo(fn, [fitRows, height, isEmpty]);\n", False),
    ("comparison string in jsx",
     "const x = <p>{x === 'ACTIVE' && <B/>}</p>;\n",
     "const x = <p>{x === 'INACTIVE' && <B/>}</p>;\n", False),
    ("non-copy call string",
     "const x = format('x');\n", "const x = format('y');\n", False),
    ("cn condition change",
     "const x = cn('a', cond && 'b');\n", "const x = cn('a', !cond && 'b');\n", False),
    ("template url",
     "const x = fetch(`/api/${id}`);\n", "const x = fetch(`/api/v2/${id}`);\n", False),
    ("template substitution identifier",
     "const label = `Hi ${name}`;\n", "const label = `Hi ${user}`;\n", False),
    ("regex pattern change",
     "const re = /a\\/b/;\n", "const re = /a\\/c/;\n", False),
    ("comparison operator change",
     "const x = a < b;\n", "const x = a > b;\n", False),
    ("delete jsx text",
     "const x = <p>Save</p>;\n", "const x = <p></p>;\n", False),
    ("unterminated string",
     "const x = 'a;\n", "const x = 'b;\n", False),
    ("unterminated template",
     "const x = `a;\n", "const x = `b;\n", False),
    ("unterminated comment",
     "/* old\nconst x = 1;\n", "/* new\nconst x = 1;\n", False),
    ("mismatched jsx close",
     "const x = <A></B>;\n", "const x = <A></C>;\n", False),
    ("same source", "const x = 1;\n", "const x = 1;\n", False),
]


def main():
    failures = 0
    for name, old, new, expected in CASES:
        actual = wording.wording_only(old, new, "jsx")
        ok = actual == expected
        if not ok:
            failures += 1
        print("%s  %-14s %s" % ("OK  " if ok else "FAIL", "allow" if expected else "deny", name))
    print()
    print("cases: %d, failures: %d" % (len(CASES), failures))
    return failures


if __name__ == "__main__":
    sys.exit(main())
