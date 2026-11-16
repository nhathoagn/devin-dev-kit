"""Wording-only detection for JS/TS/JSX source edits.

This module decides whether the difference between two versions of a source file
changes only display text, style, or comments. It is used by the fe-kit gate so a
pure copy/style edit does not need an architecture owner and a reuse decision.

The decision is token based, not line based. A lexer splits the whole file into
code, strings, template text, JSX text, comments, and whitespace. Copy and style
content is erased before the old and new token streams are compared. Everything
that is not a known copy or style sink stays code, so an unknown string value is
gated instead of being excused.

No third-party parser is used: the hook must run with the system python3 and no
node_modules. Anything the lexer cannot read raises ValueError, and the caller
treats that as "not wording-only" (fail closed).

Run the unit matrix with: python3 scripts/test_wording.py
The exit code is the number of failures.
"""
import re

MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_JSX_DEPTH = 200

STYLE_WORDS = frozenset((
    "class", "classes", "classname", "classnames", "style", "styles", "css", "sx",
    "tw", "variant", "variants", "color", "colour", "theme", "spacing", "size",
    "sizes", "width", "height", "typography",
))
COPY_WORDS = frozenset((
    "label", "labels", "text", "texts", "title", "titles", "message", "messages",
    "description", "descriptions", "placeholder", "placeholders", "tooltip",
    "tooltips", "caption", "captions", "hint", "hints", "error", "errors", "subtitle",
    "subtitles", "heading", "headings", "summary", "summaries", "children",
))
COPY_COMPOUNDS = frozenset((
    "emptytext", "confirmtext", "canceltext", "oktext", "loadingtext", "errortext",
    "helptext", "arialabel", "ariadescription", "ariaplaceholder", "ariavaluetext",
    "ariaroledescription",
))
STYLE_KEYS = frozenset((
    "sm", "md", "lg", "xl", "2xl", "base", "default", "month", "day", "week",
    "hour", "minute", "second", "year",
))
COPY_ATTRS = frozenset((
    "title", "aria-label", "aria-description", "aria-placeholder", "aria-valuetext",
    "aria-roledescription", "placeholder", "alt", "label", "tooltip", "emptyText",
    "confirmText", "cancelText", "okText", "loadingText", "errorText", "helpText",
    "description", "caption", "message", "heading", "subtitle", "summary",
))
STYLE_ATTRS = frozenset(("class", "className", "classNames", "style", "css", "sx", "tw"))
COPY_CALLEES = frozenset((
    "t", "i18n.t", "translate", "formatMessage", "getText", "$t", "alert", "confirm",
    "prompt", "setLabel", "setTitle", "setMessage", "setError", "setPlaceholder",
    "setHelperText", "setCaption", "setTooltip", "setDescription", "notify",
    "showToast", "showMessage",
))
COPY_CALLEE_PREFIXES = ("toast.", "message.", "notification.", "Modal.")
STYLE_CALLEES = frozenset((
    "cn", "clsx", "classnames", "cva", "tw", "twMerge", "twJoin", "css", "keyframes",
    "createGlobalStyle", "styled", "tv",
))
STYLE_CALLEE_PREFIXES = ("styled.",)
CODE_NEIGHBOR_OPS = frozenset((
    "===", "!==", "==", "!=", "<", ">", "<=", ">=", "+", "-", "*", "/", "%",
    "<<", ">>", ">>>", "&", "|", "^",
))
CODE_NEIGHBOR_WORDS = frozenset(("in", "instanceof", "typeof"))
ASI_KEYWORDS = frozenset(("return", "throw", "yield", "break", "continue"))
REGEX_PREV_OPS = frozenset((
    "(", "[", "{", ",", ";", ":", "?", "=", "!", "&", "|", "+", "-", "*", "%", "~",
    "^", "<", ">", "=>", "&&", "||", "??",
))
REGEX_PREV_WORDS = frozenset((
    "return", "throw", "case", "delete", "void", "typeof", "instanceof", "in", "of",
    "yield", "await", "new", "else", "do", "while", "for", "if", "switch", "with",
    "extends",
))
IDENT_START = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_$")
IDENT_PART = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_$0123456789")
DIGITS = frozenset("0123456789")
MULTI_OPS = (
    ">>>=", "...", "===", "!==", "**=", "<<=", ">>=", ">>>", "=>", "==", "!=", "<=",
    ">=", "&&", "||", "??", "?.", "++", "--", "+=", "-=", "*=", "/=", "%=", "&=",
    "|=", "^=", "<<", ">>", "**", "::", "?.",
)
PAREN_KEYWORDS = frozenset((
    "return", "if", "for", "while", "switch", "catch", "with", "typeof", "void",
    "delete", "in", "of", "instanceof", "yield", "await", "else", "do", "function",
    "async", "new", "import",
))
JSX_DIALECTS = frozenset(("jsx",))


class _JsxFail(Exception):
    pass


def dialect_for(path):
    lower = (path or "").lower()
    for suffix in (".tsx", ".jsx", ".js", ".mjs", ".cjs"):
        if lower.endswith(suffix):
            return "jsx"
    return ""


def apply_edits(source, pairs):
    current = source
    for old, new in pairs:
        if not old:
            return None
        found = current.find(old)
        if found < 0:
            alternate = old.replace("\r\n", "\n")
            if alternate != old:
                found = current.find(alternate)
                if found >= 0:
                    current = current[:found] + new.replace("\r\n", "\n") + current[found + len(alternate):]
                    continue
            alternate = old.replace("\n", "\r\n")
            if alternate != old:
                found = current.find(alternate)
                if found >= 0:
                    current = current[:found] + new.replace("\n", "\r\n") + current[found + len(alternate):]
                    continue
            return None
        current = current[:found] + new + current[found + len(old):]
    return current


def wording_only(old_source, new_source, dialect="jsx"):
    if old_source == new_source:
        return False
    try:
        old_tokens = normalize(tokenize(old_source, dialect))
        new_tokens = normalize(tokenize(new_source, dialect))
    except (ValueError, RecursionError):
        return False
    return old_tokens == new_tokens


def edits_are_wording(source, pairs, dialect="jsx"):
    after = apply_edits(source, pairs)
    if after is None:
        return False
    return wording_only(source, after, dialect)


def _state(source, dialect):
    return {
        "src": source,
        "n": len(source),
        "i": 0,
        "dialect": dialect,
        "tokens": [],
        "prev": None,
        "depth": 0,
    }


def _token(kind, text, ctx=None, value="", role="", attr="", key=""):
    return {
        "kind": kind,
        "text": text,
        "value": value,
        "ctx": ctx,
        "role": role,
        "attr": attr,
        "key": key,
    }


def _emit(state, kind, text, ctx=None, value="", role="", attr="", key=""):
    token = _token(kind, text, ctx, value, role, attr, key)
    state["tokens"].append(token)
    if kind not in ("ws", "comment"):
        state["prev"] = token
    return token


def _skip_ws(state):
    source = state["src"]
    n = state["n"]
    while state["i"] < n and source[state["i"]] in " \t\r\n ﻿":
        state["i"] += 1


def _skip_line_comment(state):
    source = state["src"]
    n = state["n"]
    while state["i"] < n and source[state["i"]] not in "\r\n":
        state["i"] += 1


def _skip_block_comment(state):
    source = state["src"]
    n = state["n"]
    end = source.find("*/", state["i"] + 2)
    if end < 0:
        raise ValueError("unterminated block comment")
    state["i"] = end + 2


def _read_ident(state):
    source = state["src"]
    n = state["n"]
    start = state["i"]
    state["i"] += 1
    while state["i"] < n and source[state["i"]] in IDENT_PART:
        state["i"] += 1
    return source[start:state["i"]]


def _read_number(state):
    source = state["src"]
    n = state["n"]
    start = state["i"]
    while state["i"] < n and source[state["i"]] in "0123456789abcdefABCDEFxXoObBeE._+-":
        char = source[state["i"]]
        if char in "+-" and state["i"] > start and source[state["i"] - 1] not in "eE":
            break
        state["i"] += 1
    if state["i"] < n and source[state["i"]] == "n":
        state["i"] += 1
    return source[start:state["i"]]


def _read_op(state):
    source = state["src"]
    for op in MULTI_OPS:
        if source.startswith(op, state["i"]):
            state["i"] += len(op)
            return op
    char = source[state["i"]]
    state["i"] += 1
    return char


def _newline_ahead(state):
    source = state["src"]
    n = state["n"]
    i = state["i"]
    saw = False
    while i < n and source[i] in " \t\r":
        i += 1
    while i < n and source[i] == "\n":
        saw = True
        i += 1
        while i < n and source[i] in " \t\r":
            i += 1
    return saw


def _at_statement_start(state, start):
    source = state["src"]
    i = start - 1
    while i >= 0 and source[i] in " \t\r\n":
        i -= 1
    if i < 0:
        return True
    return source[i] in ";{}"


def _lex_string(state, quote, ctx, role="", attr="", key="", allow_newline=False):
    source = state["src"]
    n = state["n"]
    start = state["i"]
    state["i"] += 1
    while state["i"] < n:
        char = source[state["i"]]
        if char == "\\":
            state["i"] += 2
            continue
        if char == quote:
            state["i"] += 1
            inner = source[start + 1:state["i"] - 1]
            _emit(state, "string", source[start:state["i"]], ctx=ctx, value=inner, role=role, attr=attr, key=key)
            return
        if char in "\r\n":
            if allow_newline:
                state["i"] += 1
                continue
            raise ValueError("unterminated string")
        state["i"] += 1
    raise ValueError("unterminated string")


def _tag_name(tokens):
    if not tokens:
        return ""
    last = tokens[-1]
    if last["kind"] != "id":
        return ""
    parts = [last["text"]]
    index = len(tokens) - 2
    while index >= 1 and tokens[index]["kind"] == "op" and tokens[index]["text"] in (".", "?.") \
            and tokens[index - 1]["kind"] == "id":
        parts.insert(0, tokens[index - 1]["text"])
        index -= 2
    return ".".join(parts)


def _lex_template(state, ctx):
    source = state["src"]
    n = state["n"]
    state["i"] += 1
    text_start = state["i"]
    while state["i"] < n:
        char = source[state["i"]]
        if char == "\\":
            state["i"] += 2
            continue
        if char == "`":
            if state["i"] > text_start:
                _emit(state, "template_text", source[text_start:state["i"]], ctx=ctx,
                      value=source[text_start:state["i"]])
            state["i"] += 1
            return
        if char == "$" and state["i"] + 1 < n and source[state["i"] + 1] == "{":
            if state["i"] > text_start:
                _emit(state, "template_text", source[text_start:state["i"]], ctx=ctx,
                      value=source[text_start:state["i"]])
            _emit(state, "op", "${", ctx=ctx)
            state["i"] += 2
            _lex_code(state, ("}",), {"kind": "template_expr"})
            if state["i"] >= n or source[state["i"]] != "}":
                raise ValueError("unterminated template expression")
            _emit(state, "op", "}", ctx=ctx)
            state["i"] += 1
            text_start = state["i"]
            continue
        state["i"] += 1
    raise ValueError("unterminated template")


def _regex_allowed(state):
    prev = state["prev"]
    if prev is None:
        return True
    if prev["kind"] == "op":
        return prev["text"] in REGEX_PREV_OPS
    if prev["kind"] == "id":
        return prev["text"] in REGEX_PREV_WORDS
    return False


def _lex_slash(state, ctx):
    source = state["src"]
    n = state["n"]
    if not _regex_allowed(state):
        state["i"] += 1
        _emit(state, "op", "/", ctx=ctx)
        return
    start = state["i"]
    state["i"] += 1
    in_class = False
    while state["i"] < n:
        char = source[state["i"]]
        if char == "\\":
            state["i"] += 2
            continue
        if char in "\r\n":
            state["i"] = start + 1
            _emit(state, "op", "/", ctx=ctx)
            return
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            state["i"] += 1
            while state["i"] < n and source[state["i"]] in IDENT_PART:
                state["i"] += 1
            _emit(state, "regex", source[start:state["i"]], ctx=ctx)
            return
        state["i"] += 1
    state["i"] = start + 1
    _emit(state, "op", "/", ctx=ctx)


def _jsx_allowed(state):
    source = state["src"]
    n = state["n"]
    i = state["i"]
    if i + 1 >= n:
        return False
    nxt = source[i + 1]
    if nxt not in IDENT_START and nxt not in (">", "/"):
        return False
    prev = state["prev"]
    if prev is None:
        return True
    if prev["kind"] == "op":
        return prev["text"] in ("(", "[", "{", ",", ";", ":", "?", "=", "=>", "&&",
                                "||", "??", "!", "+", "-", "*", "%", "~", "^", "<", ">")
    if prev["kind"] == "id":
        return prev["text"] in ("return", "yield", "case", "throw", "else", "do",
                                "typeof", "void", "delete", "new", "in", "of",
                                "instanceof", "await")
    return False


def _read_jsx_name(state):
    source = state["src"]
    n = state["n"]
    start = state["i"]
    while state["i"] < n:
        char = source[state["i"]]
        if char in IDENT_PART or char in "-:.$":
            state["i"] += 1
            continue
        break
    if state["i"] == start:
        raise _JsxFail("empty jsx name")
    return source[start:state["i"]]


def _skip_type_args(state):
    source = state["src"]
    n = state["n"]
    start = state["i"]
    depth = 0
    while state["i"] < n:
        char = source[state["i"]]
        if char == "<":
            depth += 1
        elif char == ">":
            depth -= 1
            if depth == 0:
                state["i"] += 1
                _emit(state, "type", source[start:state["i"]])
                return
        elif char in "\r\n":
            raise _JsxFail("newline in type args")
        state["i"] += 1
    raise _JsxFail("unterminated type args")


def _lex_jsx_element(state, closing=False, self_closing_ok=True):
    source = state["src"]
    n = state["n"]
    state["depth"] += 1
    if state["depth"] > MAX_JSX_DEPTH:
        raise _JsxFail("jsx too deep")
    try:
        if state["i"] >= n or source[state["i"]] != "<":
            raise _JsxFail("no jsx")
        _emit(state, "op", "<")
        state["i"] += 1
        if state["i"] < n and source[state["i"]] == "/":
            raise _JsxFail("closing tag in element position")
        if state["i"] < n and source[state["i"]] == ">":
            _emit(state, "op", ">")
            state["i"] += 1
            _lex_jsx_children(state, "")
            return
        name = _read_jsx_name(state)
        _emit(state, "id", name)
        _skip_ws(state)
        if state["i"] < n and source[state["i"]] == "<":
            _skip_type_args(state)
            _skip_ws(state)
        while True:
            _skip_ws(state)
            if state["i"] >= n:
                raise _JsxFail("eof in tag")
            char = source[state["i"]]
            if char == ">":
                _emit(state, "op", ">")
                state["i"] += 1
                _lex_jsx_children(state, name)
                return
            if char == "/" and state["i"] + 1 < n and source[state["i"] + 1] == ">":
                _emit(state, "op", "/>")
                state["i"] += 2
                return
            if char == "{":
                _emit(state, "op", "{")
                state["i"] += 1
                _lex_code(state, ("}",), {"kind": "spread"})
                if state["i"] >= n or source[state["i"]] != "}":
                    raise _JsxFail("unterminated spread")
                _emit(state, "op", "}")
                state["i"] += 1
                continue
            attr = _read_jsx_name(state)
            _emit(state, "id", attr)
            _skip_ws(state)
            if state["i"] >= n or source[state["i"]] != "=":
                continue
            _emit(state, "op", "=")
            state["i"] += 1
            _skip_ws(state)
            if state["i"] >= n:
                raise _JsxFail("eof after attr")
            quote = source[state["i"]]
            if quote in "'\"":
                sink = _attr_sink(attr)
                _lex_string(state, quote, {"kind": "jsx_attr", "attr": attr, "sink": sink},
                            role="jsx_attr", attr=attr, allow_newline=True)
            elif quote == "{":
                _emit(state, "op", "{")
                state["i"] += 1
                sink = _attr_sink(attr)
                _lex_code(state, ("}",), {"kind": "jsx_attr", "attr": attr, "sink": sink})
                if state["i"] >= n or source[state["i"]] != "}":
                    raise _JsxFail("unterminated attr expression")
                _emit(state, "op", "}")
                state["i"] += 1
            else:
                raise _JsxFail("bad attr value")
    finally:
        state["depth"] -= 1


def _lex_jsx_children(state, name):
    source = state["src"]
    n = state["n"]
    while state["i"] < n:
        char = source[state["i"]]
        if char == "<":
            if state["i"] + 1 < n and source[state["i"] + 1] == "/":
                _emit(state, "op", "</")
                state["i"] += 2
                close = ""
                if state["i"] < n and source[state["i"]] != ">":
                    close = _read_jsx_name(state)
                    _emit(state, "id", close)
                _skip_ws(state)
                if state["i"] >= n or source[state["i"]] != ">":
                    raise _JsxFail("bad closing tag")
                _emit(state, "op", ">")
                state["i"] += 1
                if close != name:
                    raise _JsxFail("mismatched closing tag")
                return
            _lex_jsx_element(state)
            continue
        if char == "{":
            _emit(state, "op", "{")
            state["i"] += 1
            _lex_code(state, ("}",), {"kind": "jsx_child"})
            if state["i"] >= n or source[state["i"]] != "}":
                raise _JsxFail("unterminated child expression")
            _emit(state, "op", "}")
            state["i"] += 1
            continue
        start = state["i"]
        while state["i"] < n and source[state["i"]] not in "<{":
            state["i"] += 1
        text = source[start:state["i"]]
        if text.strip():
            _emit(state, "jsx_text", text, ctx={"kind": "jsx_text"})
    raise _JsxFail("unterminated jsx children")


def _attr_sink(attr):
    if attr in STYLE_ATTRS:
        return "style"
    if attr in COPY_ATTRS:
        return "copy"
    return "code"


def _lex_jsx(state, ctx):
    saved_i = state["i"]
    saved_tokens = len(state["tokens"])
    saved_prev = state["prev"]
    saved_depth = state["depth"]
    try:
        _lex_jsx_element(state)
        return True
    except _JsxFail:
        del state["tokens"][saved_tokens:]
        state["i"] = saved_i
        state["prev"] = saved_prev
        state["depth"] = saved_depth
        return False


def _call_name(tokens, paren_index):
    index = paren_index - 1
    if index < 0:
        return ""
    token = tokens[index]
    if token["kind"] == "op" and token["text"] in (")", "]"):
        return "<call>"
    if token["kind"] != "id" or token["text"] in PAREN_KEYWORDS:
        return ""
    parts = [token["text"]]
    index -= 1
    while index >= 1 and tokens[index]["kind"] == "op" and tokens[index]["text"] in (".", "?.") \
            and tokens[index - 1]["kind"] == "id":
        parts.insert(0, tokens[index - 1]["text"])
        index -= 2
    return ".".join(parts)


def _call_sink(name):
    if not name or name == "<call>":
        return ""
    if name in COPY_CALLEES:
        return "copy"
    if name in STYLE_CALLEES:
        return "style"
    for prefix in COPY_CALLEE_PREFIXES:
        if name.startswith(prefix):
            return "copy"
    for prefix in STYLE_CALLEE_PREFIXES:
        if name.startswith(prefix):
            return "style"
    return ""


def _lex_call_or_group(state, ctx):
    tokens = state["tokens"]
    significant = [token for token in tokens if token["kind"] not in ("ws", "comment")]
    paren_index = len(significant)
    source = state["src"]
    if source[state["i"]] == "(":
        state["i"] += 1
        _emit(state, "op", "(", ctx=ctx)
        name = _call_name(significant, paren_index)
        sink = _call_sink(name)
        inner = {"kind": "call", "callee": name, "sink": sink} if name else ctx
        _lex_code(state, (")",), inner)
        if state["i"] >= state["n"] or source[state["i"]] != ")":
            raise ValueError("unterminated call")
        _emit(state, "op", ")", ctx=ctx)
        state["i"] += 1
        return


def _lex_bracket(state, ctx):
    source = state["src"]
    state["i"] += 1
    _emit(state, "op", "[", ctx=ctx)
    _lex_code(state, ("]",), ctx)
    if state["i"] >= state["n"] or source[state["i"]] != "]":
        raise ValueError("unterminated array")
    _emit(state, "op", "]", ctx=ctx)
    state["i"] += 1


def _object_like(state):
    prev = state["prev"]
    if prev is None:
        return False
    if prev["kind"] == "op":
        return prev["text"] in ("(", "[", "{", ",", ":", "=", "=>", "?", "&&", "||", "??", "return")
    if prev["kind"] == "id":
        return prev["text"] in ("return", "yield", "case", "=>")
    return False


def _lex_brace(state, ctx):
    source = state["src"]
    inner = {"kind": "object"} if _object_like(state) else ctx
    state["i"] += 1
    _emit(state, "op", "{", ctx=ctx)
    _lex_code(state, ("}",), inner)
    if state["i"] >= state["n"] or source[state["i"]] != "}":
        raise ValueError("unterminated brace")
    _emit(state, "op", "}", ctx=ctx)
    state["i"] += 1


def _skip_import_or_export(state, name):
    source = state["src"]
    n = state["n"]
    start_after = state["i"]
    _skip_ws(state)
    if state["i"] >= n:
        _emit(state, "id", name)
        return
    char = source[state["i"]]
    if name == "import" and char in "(.$":
        _emit(state, "id", name)
        return
    if name == "export" and char != "{" and char != "*":
        _emit(state, "id", name)
        return
    _emit(state, "id", name)
    depth = 0
    while state["i"] < n:
        char = source[state["i"]]
        if char in " \t\r\n":
            state["i"] += 1
            continue
        if char == "{":
            depth += 1
            state["i"] += 1
            continue
        if char == "}":
            depth -= 1
            state["i"] += 1
            continue
        if depth == 0 and char in "\"'" and name == "export":
            _lex_string(state, char, {"kind": "import"}, role="import_source")
            return
        if depth == 0 and source.startswith("from", state["i"]) and (state["i"] + 4 >= n or source[state["i"] + 4] not in IDENT_PART):
            state["i"] += 4
            _skip_ws(state)
            if state["i"] < n and source[state["i"]] in "\"'":
                _lex_string(state, source[state["i"]], {"kind": "import"}, role="import_source")
                return
            raise ValueError("import without source")
        if depth == 0 and char in "\"'" and name == "import":
            _lex_string(state, char, {"kind": "import"}, role="import_source")
            return
        if depth == 0 and char in ";\n":
            if char == ";":
                state["i"] += 1
            return
        state["i"] += 1
    if state["i"] == start_after:
        raise ValueError("empty import")


def _lex_code(state, stop, ctx):
    source = state["src"]
    n = state["n"]
    while state["i"] < n:
        char = source[state["i"]]
        if char in " \t\r\n":
            _skip_ws(state)
            continue
        if stop and char in stop:
            return
        if char == "/" and state["i"] + 1 < n and source[state["i"] + 1] == "/":
            _skip_line_comment(state)
            continue
        if char == "/" and state["i"] + 1 < n and source[state["i"] + 1] == "*":
            _skip_block_comment(state)
            continue
        if char in "'\"":
            _lex_string(state, char, ctx)
            continue
        if char == "`":
            prev_name = _tag_name([token for token in state["tokens"] if token["kind"] not in ("ws", "comment")])
            if prev_name:
                template_ctx = {"kind": "tag", "callee": prev_name}
                if _call_sink(prev_name) == "style":
                    template_ctx = {"kind": "jsx_attr", "attr": "class", "sink": "style"}
                elif prev_name and prev_name not in ("gql", "String.raw"):
                    template_ctx = {"kind": "tag", "callee": prev_name, "sink": ""}
                _lex_template(state, template_ctx)
            else:
                _lex_template(state, ctx)
            continue
        if char == "/":
            _lex_slash(state, ctx)
            continue
        if char == "<" and _jsx_allowed(state):
            if _lex_jsx(state, ctx):
                continue
        if char == "(":
            _lex_call_or_group(state, ctx)
            continue
        if char == "[":
            _lex_bracket(state, ctx)
            continue
        if char == "{":
            _lex_brace(state, ctx)
            continue
        if char in ")]}":
            raise ValueError("unexpected closer")
        if char in IDENT_START:
            start = state["i"]
            name = _read_ident(state)
            if name in ("import", "export") and _at_statement_start(state, start):
                _skip_import_or_export(state, name)
                continue
            _emit(state, "id", name, ctx=ctx)
            if name in ASI_KEYWORDS and _newline_ahead(state):
                _emit(state, "op", "NL", ctx=ctx)
            continue
        if char in DIGITS or (char == "." and state["i"] + 1 < n and source[state["i"] + 1] in DIGITS):
            _emit(state, "num", _read_number(state), ctx=ctx)
            continue
        op = _read_op(state)
        _emit(state, "op", op, ctx=ctx)


def tokenize(source, dialect="jsx"):
    if dialect not in JSX_DIALECTS:
        raise ValueError("unsupported dialect")
    state = _state(source, dialect)
    _lex_code(state, set(), None)
    return state["tokens"]


def _words(name):
    return [part.lower() for part in re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|\b)|[A-Z]?[a-z]+|\d+", name or "")]


def _name_sink(name):
    if not name:
        return ""
    lowered = name.lower()
    if lowered in COPY_COMPOUNDS:
        return "copy"
    words = _words(name)
    for word in words:
        if word in STYLE_WORDS:
            return "style"
    if words and words[-1] in COPY_WORDS:
        return "copy"
    return ""


def _key_sink(key):
    if not key:
        return ""
    lowered = key.lower()
    if lowered in STYLE_KEYS:
        return "style"
    return _name_sink(key)


def _significant(tokens):
    return [token for token in tokens if token["kind"] not in ("ws", "comment")]


def _mark_calls(tokens):
    stack = []
    for index, token in enumerate(tokens):
        if token["kind"] == "op" and token["text"] == "(":
            name = _call_name(tokens, index)
            if name:
                stack.append({"callee": name, "sink": _call_sink(name)})
            else:
                stack.append(None)
        token["call"] = None
        for entry in reversed(stack):
            if entry is not None:
                token["call"] = entry
                break
        if token["kind"] == "op" and token["text"] == ")":
            if stack:
                stack.pop()


def _is_ternary_colon(tokens, colon_index):
    depth = 0
    index = colon_index - 1
    while index >= 0:
        token = tokens[index]
        if token["kind"] == "op":
            if token["text"] in (")", "]", "}"):
                depth += 1
            elif token["text"] in ("(", "[", "{"):
                if depth == 0:
                    return False
                depth -= 1
            elif token["text"] == "?" and depth == 0:
                return True
            elif token["text"] in (",", ";") and depth == 0:
                return False
        index -= 1
    return False


def _property_key(tokens, index):
    if index < 2:
        return ""
    colon = tokens[index - 1]
    if colon["kind"] != "op" or colon["text"] != ":":
        return ""
    if _is_ternary_colon(tokens, index - 1):
        return ""
    key = tokens[index - 2]
    if key["kind"] == "id":
        return key["text"]
    if key["kind"] == "string":
        return key["value"]
    return ""


def _is_property_key(tokens, index):
    if index + 1 >= len(tokens):
        return False
    colon = tokens[index + 1]
    if colon["kind"] != "op" or colon["text"] != ":":
        return False
    if index == 0:
        return True
    before = tokens[index - 1]
    return before["kind"] == "op" and before["text"] in ("{", ",")


def _literal_opener(tokens, cursor):
    if cursor <= 0:
        return True
    before = tokens[cursor - 1]
    if before["kind"] == "op":
        return before["text"] in ("(", "[", "{", ",", ":", "=", "?", "&&", "||", "??")
    if before["kind"] == "id":
        return before["text"] in ("return", "yield", "case")
    return False


def _assignment_name(tokens, index):
    depth = 0
    cursor = index - 1
    while cursor >= 0:
        token = tokens[cursor]
        if token["kind"] == "op":
            text = token["text"]
            if text in (")", "]", "}"):
                depth += 1
            elif text in ("(", "[", "{"):
                if depth == 0:
                    if text == "(" or not _literal_opener(tokens, cursor):
                        return ""
                else:
                    depth -= 1
            elif text == "=" and depth == 0:
                if cursor >= 1:
                    left = tokens[cursor - 1]
                    if left["kind"] == "id":
                        return left["text"]
                return ""
            elif text in (";",) and depth == 0:
                return ""
        cursor -= 1
    return ""


def _operand_of_code(tokens, index):
    if index > 0:
        prev = tokens[index - 1]
        if prev["kind"] == "op" and prev["text"] in CODE_NEIGHBOR_OPS:
            return True
        if prev["kind"] == "id" and prev["text"] in CODE_NEIGHBOR_WORDS:
            return True
    if index + 1 < len(tokens):
        nxt = tokens[index + 1]
        if nxt["kind"] == "op" and nxt["text"] in CODE_NEIGHBOR_OPS:
            return True
        if nxt["kind"] == "id" and nxt["text"] in CODE_NEIGHBOR_WORDS:
            return True
    return False


def _classify(tokens, index):
    token = tokens[index]
    if token.get("role") == "import_source":
        return "code"
    if token.get("role") == "jsx_attr":
        # A quoted attribute value is copy or style. The > that closes the tag is not a comparison.
        ctx = token.get("ctx") or {}
        sink = ctx.get("sink") or "code"
        return sink if sink in ("copy", "style") else "code"
    if _is_property_key(tokens, index):
        return "code"
    if _operand_of_code(tokens, index):
        return "code"
    call = token.get("call")
    if call is not None:
        return call.get("sink") or "code"
    ctx = token.get("ctx") or {}
    kind = ctx.get("kind")
    if kind == "jsx_attr":
        sink = ctx.get("sink") or "code"
        return sink if sink in ("copy", "style") else "code"
    if kind == "jsx_child":
        return "copy"
    key = _property_key(tokens, index)
    if key:
        sink = _key_sink(key)
        if sink:
            return sink
    name = _assignment_name(tokens, index)
    if name:
        sink = _name_sink(name)
        if sink:
            return sink
    if kind == "jsx_text":
        return "copy"
    if kind == "tag":
        return "style" if ctx.get("sink") == "style" else "code"
    return "code"


def _annotate(tokens):
    significant = _significant(tokens)
    _mark_calls(significant)
    for index, token in enumerate(significant):
        if token["kind"] in ("string", "template_text"):
            token["sink"] = _classify(significant, index)


def normalize(tokens):
    _annotate(tokens)
    significant = _significant(tokens)
    result = []
    for index, token in enumerate(significant):
        kind = token["kind"]
        if kind == "jsx_text":
            if token["text"].strip():
                result.append(("copy",))
            continue
        if kind == "string":
            sink = token.get("sink") or "code"
            if sink == "copy":
                result.append(("copy",))
            elif sink == "style":
                result.append(("style",))
            else:
                result.append(("str", token["value"]))
            continue
        if kind == "template_text":
            sink = token.get("sink") or "code"
            if sink == "copy":
                result.append(("copy",))
            elif sink == "style":
                result.append(("style",))
            else:
                result.append(("tpl", token["value"]))
            continue
        if kind == "regex":
            result.append(("re", token["text"]))
            continue
        if kind == "type":
            result.append(("type", token["text"]))
            continue
        if kind == "op" and token["text"] == ",":
            if index + 1 < len(significant) and significant[index + 1]["kind"] == "op" \
                    and significant[index + 1]["text"] in (")", "]", "}"):
                continue
        result.append((kind, token["text"]))
    return result
