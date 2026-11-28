"""Tests for wording.py: the token diff that decides a behaviorless copy/style edit.

Locks the correct contract from rules/fe-implementation.md. Methods in the
Regressions* classes encode behavior that is buggy today (bugs W1-W4); they are
expected to fail until the fix lands.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wording


def only(old, new, dialect="jsx"):
    return wording.wording_only(old, new, dialect)


def edits(source, *pairs, dialect="jsx"):
    return wording.edits_are_wording(source, list(pairs), dialect)


class DialectFor(unittest.TestCase):
    def test_tsx_maps_to_jsx(self):
        self.assertEqual(wording.dialect_for("src/App.tsx"), "jsx")

    def test_js_maps_to_jsx(self):
        self.assertEqual(wording.dialect_for("src/util.js"), "jsx")

    def test_mjs_maps_to_jsx(self):
        self.assertEqual(wording.dialect_for("build/x.mjs"), "jsx")

    def test_ts_has_no_dialect(self):
        # .ts gets no dialect so the gate never calls wording_only on it.
        self.assertEqual(wording.dialect_for("src/util.ts"), "")

    def test_case_insensitive(self):
        self.assertEqual(wording.dialect_for("src/App.TSX"), "jsx")

    def test_empty_path(self):
        self.assertEqual(wording.dialect_for(""), "")


class ApplyEdits(unittest.TestCase):
    def test_missing_old_returns_none(self):
        self.assertIsNone(wording.apply_edits("const a = 1;", [("zzz", "x")]))

    def test_empty_old_returns_none(self):
        self.assertIsNone(wording.apply_edits("const a = 1;", [("", "x")]))

    def test_edits_apply_in_order(self):
        out = wording.apply_edits("const a = 1; const b = 2;",
                                  [("1", "9"), ("2", "8")])
        self.assertEqual(out, "const a = 9; const b = 8;")

    def test_crlf_old_matches_lf_source(self):
        out = wording.apply_edits("const a = 1;\nconst b = 2;",
                                  [("const a = 1;\r\nconst b = 2;", "const a = 3;\r\nconst b = 2;")])
        self.assertEqual(out, "const a = 3;\nconst b = 2;")


class WordingOnlyBasics(unittest.TestCase):
    def test_identical_source_is_not_a_change(self):
        self.assertFalse(only('const a = "x";', 'const a = "x";'))

    def test_whitespace_only_edit_is_wording(self):
        self.assertTrue(only("const a = 1;", "const  a  =  1 ;"))

    def test_comment_only_edit_is_wording(self):
        self.assertTrue(only("// hello\nconst a = 1;", "// hi\nconst a = 1;"))

    def test_block_comment_edit_is_wording(self):
        self.assertTrue(only("/* hi */ const a = 1;", "/* yo */ const a = 1;"))

    def test_unterminated_string_fails_closed(self):
        self.assertFalse(only('const a = "unclosed;', 'const a = "closed";'))

    def test_unsupported_dialect_fails_closed(self):
        # Only the "jsx" dialect is implemented; "ts"/"js" callers get False.
        self.assertFalse(only('const label = "a";', 'const label = "b";', "ts"))
        self.assertFalse(only('const label = "a";', 'const label = "b";', "js"))
        self.assertFalse(only('const label = "a";', 'const label = "b";', ""))

    def test_edits_are_wording_missing_old_is_false(self):
        self.assertFalse(edits('const a = "a";', ("not in source", "x")))


class JsxTextExempt(unittest.TestCase):
    def test_button_text(self):
        self.assertTrue(only("x = <button>Ghi</button>", "x = <button>Lưu</button>"))

    def test_text_after_expression_child(self):
        self.assertTrue(only("x = <p>{n} chào</p>", "x = <p>{n} xin</p>"))

    def test_fragment_text(self):
        self.assertTrue(only("x = <>Ghi</>", "x = <>Lưu</>"))

    def test_whitespace_around_jsx_text_keeps_exempt(self):
        self.assertTrue(only("x = <p>  Ghi  </p>", "x = <p>Lưu</p>"))

    def test_tag_name_change_is_code(self):
        self.assertFalse(only("x = <Button>Ghi</Button>", "x = <Modal>Ghi</Modal>"))

    def test_jsx_component_rename_is_code(self):
        self.assertFalse(only("x = <Foo>a</Foo>; x = <Bar>a</Bar>",
                              "x = <Foo>a</Foo>; x = <Baz>a</Baz>"))

    def test_jsx_text_inside_function_return(self):
        self.assertTrue(only("function f() { return <b>Ghi</b>; }",
                             "function f() { return <b>Lưu</b>; }"))


class JsxAttrExempt(unittest.TestCase):
    def test_title_quoted(self):
        self.assertTrue(only('x = <div title="Save" />', 'x = <div title="Lưu" />'))

    def test_aria_label_quoted(self):
        self.assertTrue(only('x = <div aria-label="Save" />', 'x = <div aria-label="Lưu" />'))

    def test_placeholder_quoted(self):
        self.assertTrue(only('x = <input placeholder="abc" />', 'x = <input placeholder="xyz" />'))

    def test_alt_quoted(self):
        self.assertTrue(only('x = <img alt="a" />', 'x = <img alt="b" />'))

    def test_label_quoted(self):
        self.assertTrue(only('x = <F label="a" />', 'x = <F label="b" />'))

    def test_copy_attr_expression_string(self):
        self.assertTrue(only('x = <div title={"a"} />', 'x = <div title={"b"} />'))

    def test_non_copy_attr_is_code(self):
        self.assertFalse(only('x = <a href="/a" />', 'x = <a href="/b" />'))

    def test_id_attr_is_code(self):
        self.assertFalse(only('x = <div id="a" />', 'x = <div id="b" />'))

    def test_key_attr_is_code(self):
        self.assertFalse(only('x = <div key="a" />', 'x = <div key="b" />'))


class CopyNameExempt(unittest.TestCase):
    def test_label_const(self):
        self.assertTrue(only("const label = 'hello';", "const label = 'xin chào';"))

    def test_endings_of_copy_words(self):
        for name in ("pageTitle", "helpText", "errorMessage", "shortDescription",
                     "inputPlaceholder"):
            with self.subTest(name=name):
                self.assertTrue(only("const %s = 'a';" % name, "const %s = 'b';" % name))

    def test_compound_copy_words(self):
        self.assertTrue(only("const emptyText = 'a';", "const emptyText = 'b';"))
        self.assertTrue(only("const confirmText = 'a';", "const confirmText = 'b';"))

    def test_uppercase_copy_const(self):
        self.assertTrue(only('const TITLE = "a";', 'const TITLE = "b";'))

    def test_let_reassignment(self):
        self.assertTrue(only('let label = "a"; label = "b";', 'let label = "a"; label = "c";'))

    def test_copy_key_in_object(self):
        self.assertTrue(only("const o = { label: 'a' };", "const o = { label: 'b' };"))

    def test_title_key_in_object(self):
        self.assertTrue(only("const o = { title: 'a' };", "const o = { title: 'b' };"))

    def test_unknown_key_under_copy_named_object(self):
        # { save: 'Lưu' } under LABELS falls back to the object's name.
        self.assertTrue(only("const LABELS = { save: 'a' };",
                             "const LABELS = { save: 'b' };"))

    def test_unknown_key_under_code_named_object_is_code(self):
        self.assertFalse(only("const DATA = { save: 'a' };",
                              "const DATA = { save: 'b' };"))


class StyleExempt(unittest.TestCase):
    def test_classname_string(self):
        self.assertTrue(only('x = <div className="a" />', 'x = <div className="b" />'))

    def test_class_attr(self):
        self.assertTrue(only('x = <div class="a" />', 'x = <div class="b" />'))

    def test_style_named_const(self):
        self.assertTrue(only("const style = { color: 'red' };",
                             "const style = { color: 'blue' };"))

    def test_style_key_in_style_attr(self):
        # base is a style key only inside a style context; the style attribute
        # is one, so the exemption stays.
        self.assertTrue(only('x = <div style={{ base: "a" }} />',
                             'x = <div style={{ base: "b" }} />'))

    def test_month_key_in_style_attr(self):
        # Any literal under the style attribute is style context.
        self.assertTrue(only('x = <div style={{ month: "a" }} />',
                             'x = <div style={{ month: "b" }} />'))

    def test_key_in_styles_named_object(self):
        # Unknown/style key falls back to the styles-named owner.
        self.assertTrue(only("const styles = { base: 'a' };",
                             "const styles = { base: 'b' };"))

    def test_cn_call(self):
        self.assertTrue(only('cn("a")', 'cn("b")'))

    def test_clsx_call(self):
        self.assertTrue(only('clsx("a", "b")', 'clsx("a", "c")'))

    def test_cva_call(self):
        self.assertTrue(only('cva("a")', 'cva("b")'))

    def test_styled_prefix_call(self):
        self.assertTrue(only('styled.div("a")', 'styled.div("b")'))


class CalleeExempt(unittest.TestCase):
    def test_t_call(self):
        self.assertTrue(only('t("hello")', 't("xin chào")'))

    def test_i18n_t_call(self):
        self.assertTrue(only('i18n.t("a")', 'i18n.t("b")'))

    def test_alert_call(self):
        self.assertTrue(only('alert("a")', 'alert("b")'))

    def test_toast_prefix(self):
        self.assertTrue(only('toast.error("a")', 'toast.error("b")'))

    def test_setlabel_second_arg_is_text(self):
        # VALUE_THEN_TEXT callees: the last argument is the copy.
        self.assertTrue(only('setLabel("f", "a")', 'setLabel("f", "b")'))

    def test_notify_second_arg_is_text(self):
        self.assertTrue(only('notify("err", "a")', 'notify("err", "b")'))

    def test_first_arg_of_value_then_text_is_code(self):
        self.assertFalse(only('setLabel("a", "x")', 'setLabel("b", "x")'))

    def test_extra_arg_of_t_is_code(self):
        self.assertFalse(only('t("a", "x")', 't("a", "y")'))


class NotExemptBehavior(unittest.TestCase):
    def test_number_change(self):
        self.assertFalse(only("const x = 1;", "const x = 2;"))

    def test_added_branch(self):
        self.assertFalse(only("function f() { return a; }",
                              "function f() { if (a) return b; return a; }"))

    def test_fetch_url_string(self):
        self.assertFalse(only('fetch("/v1/users")', 'fetch("/v2/users")'))

    def test_identifier_change(self):
        self.assertFalse(only("foo(x);", "foo(y);"))

    def test_code_named_variable_string(self):
        self.assertFalse(only('const endpoint = "a";', 'const endpoint = "b";'))

    def test_concatenated_string_is_operand(self):
        self.assertFalse(only('const x = "a" + y;', 'const x = "b" + y;'))

    def test_compared_string_is_operand(self):
        self.assertFalse(only('if (m === "a") {}', 'if (m === "b") {}'))

    def test_typeof_neighbor_string(self):
        self.assertFalse(only('x = typeof "a";', 'x = typeof "b";'))

    def test_returned_plain_string_is_code(self):
        self.assertFalse(only('function f() { return "a"; }',
                              'function f() { return "b"; }'))

    def test_import_source_change_is_code(self):
        # R2: the module source is data, already correct today.
        self.assertFalse(only('import { Button } from "./x";',
                              'import { Button } from "./y";'))

    def test_mixed_pairs_copy_and_code(self):
        self.assertFalse(edits('const label = "a";\nconst x = 1;',
                               ('"a"', '"b"'), ('1', '2')))

    def test_mixed_pairs_all_copy_passes(self):
        self.assertTrue(edits('const label = "a";\nconst title = "a";',
                              ('"a"', '"b"'), ('title = "a"', 'title = "b"')))


class NormalizeTokens(unittest.TestCase):
    def test_copy_string_erased(self):
        out = wording.normalize(wording.tokenize('const label = "a";'))
        self.assertIn(("copy",), out)

    def test_code_string_kept_with_value(self):
        out = wording.normalize(wording.tokenize('const endpoint = "a";'))
        self.assertIn(("str", "a"), out)

    def test_import_source_kept_with_value(self):
        out = wording.normalize(wording.tokenize('import { B } from "./x";'))
        self.assertIn(("str", "./x"), out)


class RegressionsW1(unittest.TestCase):
    # REGRESSION W1: import/export specifiers used to be swallowed by the
    # lexer, so a specifier swap looked wording-only. Specifier names are code.

    def test_named_import_specifier_swap(self):
        self.assertFalse(only('import { Button } from "./x";',
                              'import { Modal } from "./x";'))

    def test_named_import_list_grows(self):
        self.assertFalse(only('import { Button } from "./x";',
                              'import { Button, Modal } from "./x";'))

    def test_default_import_swap(self):
        self.assertFalse(only('import Button from "./x";',
                              'import Modal from "./x";'))

    def test_namespace_import_swap(self):
        self.assertFalse(only('import * as A from "./x";',
                              'import * as B from "./x";'))

    def test_import_type_specifier_swap(self):
        self.assertFalse(only('import type { A } from "./x";',
                              'import type { B } from "./x";'))

    def test_export_specifier_swap(self):
        self.assertFalse(only('export { B };', 'export { C };'))

    def test_export_from_specifier_swap(self):
        self.assertFalse(only('export { B } from "./x";',
                              'export { C } from "./x";'))

    def test_hook_import_swap(self):
        self.assertFalse(only('import { useState } from "react";',
                              'import { useReducer } from "react";'))

    def test_hook_call_swap(self):
        self.assertFalse(only("const [s, set] = useState(0);",
                              "const [s, set] = useReducer(0);"))


class RegressionsW2(unittest.TestCase):
    # REGRESSION W2: STYLE_KEYS (base/default/sm/md/...) are applied by key
    # name anywhere. Contract: they are style keys only inside a style context.
    # month/day/week/year were removed from STYLE_KEYS outright.

    def test_month_in_plain_data_object(self):
        self.assertFalse(only('const data = { month: "0.5" };',
                              'const data = { month: "9.9" };'))

    def test_day_in_plain_data_object(self):
        self.assertFalse(only('const data = { day: "1" };',
                              'const data = { day: "2" };'))

    def test_base_in_plain_data_object(self):
        self.assertFalse(only('const data = { base: "a" };',
                              'const data = { base: "b" };'))

    def test_default_in_plain_data_object(self):
        self.assertFalse(only('const data = { default: "a" };',
                              'const data = { default: "b" };'))

    def test_sm_in_plain_data_object(self):
        self.assertFalse(only('const data = { sm: "a" };',
                              'const data = { sm: "b" };'))


class RegressionsW3(unittest.TestCase):
    # REGRESSION W3: a path/URL-shaped string is never copy, even under a
    # copy-named owner. The owner name cannot excuse a path.

    def test_path_under_copy_named_const(self):
        self.assertFalse(only('const apiLabel = "/v1/users";',
                              'const apiLabel = "/v2/admin";'))

    def test_url_under_copy_named_const(self):
        self.assertFalse(only('const TITLE = "https://a.com/x";',
                              'const TITLE = "https://b.com/y";'))

    def test_relative_path_under_copy_named_const(self):
        self.assertFalse(only('const message = "./a/x";',
                              'const message = "./b/y";'))

    def test_path_under_copy_named_object_key(self):
        self.assertFalse(only('const meta = { label: "/a" };',
                              'const meta = { label: "/b" };'))


class RegressionsW4(unittest.TestCase):
    # REGRESSION W4: everything inside a JSX expression container was erased
    # as copy. Template text that is path-shaped is code, not copy.

    def test_path_template_in_jsx_child(self):
        self.assertFalse(only("x = <p>{`/api/${id}`}</p>",
                              "x = <p>{`/admin/${id}`}</p>"))

    def test_url_template_in_jsx_child(self):
        self.assertFalse(only("x = <p>{`https://a.com/${id}`}</p>",
                              "x = <p>{`https://b.com/${id}`}</p>"))

    def test_plain_template_in_jsx_child_stays_exempt(self):
        # MAY stay exempt: the implementation keeps non-path template text in
        # a JSX child container as copy.
        self.assertTrue(only("x = <p>{`xin ${name}`}</p>",
                             "x = <p>{`chào ${name}`}</p>"))


if __name__ == "__main__":
    unittest.main()
