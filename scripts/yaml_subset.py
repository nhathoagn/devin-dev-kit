"""Read the small YAML subset that `.fe-kit/config.yaml` uses, with the standard library only.

Supported: block mappings, block sequences (also of mappings), flow sequences of scalars, quoted
and plain scalars, `true`/`false`/`yes`/`no`/`on`/`off`, `null`/`~`, integers, and `#` comments.
Other syntax raises `YamlError` with the line number. A plain value that YAML 1.1 reads in a special way
(an alias, a tag, a number with a leading zero, a brace in a flow list) must be quoted.
For the value types the config uses (strings, lists of strings, an integer version), this reader and PyYAML
agree. Floats, dates, hex, and `1_000` stay strings here, where PyYAML converts them: quote such a value.
"""
import json
import re

KEY_RE = re.compile(r"""^("(?:[^"\\]|\\.)*"|'(?:[^']|'')*'|[A-Za-z0-9_][A-Za-z0-9_.-]*)\s*:(?:\s+(.*))?$""")
INT_RE = re.compile(r"^[-+]?\d+$")
# YAML 1.1 reads only these case forms: `true`, `True`, `TRUE`. `tRUE` is a string.
BOOLS = {form: value for word, value in (("true", True), ("yes", True), ("on", True),
                                         ("false", False), ("no", False), ("off", False))
         for form in (word, word.capitalize(), word.upper())}
NULLS = {"~", "null", "Null", "NULL"}
LEADING_ZERO_RE = re.compile(r"^[-+]?0\d")
RESERVED_START = "*&!{|>%@`"


class YamlError(ValueError):
    def __init__(self, line, message):
        super().__init__("line %d: %s" % (line, message))
        self.line = line


class _Line:
    def __init__(self, number, indent, text):
        self.number = number
        self.indent = indent
        self.text = text


def load(text):
    """Return the value of a YAML document in the supported subset. An empty document is None."""
    lines = _lines(text)
    if not lines:
        return None
    if lines[0].indent != 0:
        raise YamlError(lines[0].number, "the first line must not be indented")
    value, index = _block(lines, 0, 0)
    if index < len(lines):
        raise YamlError(lines[index].number, "unexpected indentation")
    return value


def _lines(text):
    out = []
    for number, raw in enumerate(text.replace("\r\n", "\n").split("\n"), start=1):
        if raw.strip() in ("---", "...") and raw.startswith(raw.strip()):
            if out:
                raise YamlError(number, "only one document is supported")
            continue
        body = raw.rstrip()
        stripped = body.lstrip(" ")
        if "\t" in body[: len(body) - len(body.lstrip(" \t"))]:
            raise YamlError(number, "use spaces for indentation, not tabs")
        if not stripped or stripped.startswith("#"):
            continue
        out.append(_Line(number, len(body) - len(stripped), stripped))
    return out


def _block(lines, index, indent):
    if _is_item(lines[index].text):
        return _sequence(lines, index, indent)
    return _mapping(lines, index, indent)


def _is_item(text):
    return text == "-" or text.startswith("- ")


def _sequence(lines, index, indent):
    items = []
    while index < len(lines) and lines[index].indent == indent and _is_item(lines[index].text):
        line = lines[index]
        rest = line.text[1:].lstrip(" ")
        if not rest or rest.startswith("#"):
            index += 1
            if index < len(lines) and lines[index].indent > indent:
                value, index = _block(lines, index, lines[index].indent)
            else:
                value = None
            items.append(value)
            continue
        if KEY_RE.match(_strip_comment(rest, line.number)) or _is_item(rest):
            inner = indent + (len(line.text) - len(rest))
            lines[index] = _Line(line.number, inner, rest)
            value, index = _block(lines, index, inner)
            items.append(value)
            continue
        items.append(_scalar(rest, line.number))
        index += 1
    if index < len(lines) and lines[index].indent > indent:
        raise YamlError(lines[index].number, "unexpected indentation")
    return items, index


def _mapping(lines, index, indent):
    result = {}
    while index < len(lines) and lines[index].indent == indent:
        line = lines[index]
        if _is_item(line.text):
            raise YamlError(line.number, "a list item where a key was expected")
        match = KEY_RE.match(_strip_comment(line.text, line.number))
        if not match:
            raise YamlError(line.number, "expected `key: value`")
        key = _key(match.group(1), line.number)
        if key in result:
            raise YamlError(line.number, "duplicate key `%s`" % key)
        rest = match.group(2)
        index += 1
        if rest:
            result[key] = _scalar(rest, line.number)
        elif index < len(lines) and lines[index].indent > indent:
            result[key], index = _block(lines, index, lines[index].indent)
        elif index < len(lines) and lines[index].indent == indent and _is_item(lines[index].text):
            result[key], index = _sequence(lines, index, indent)
        else:
            result[key] = None
    if index < len(lines) and lines[index].indent > indent:
        raise YamlError(lines[index].number, "unexpected indentation")
    return result, index


def _key(token, number):
    if token[0] in "\"'":
        return _quoted(token, number)
    return token


def _strip_comment(text, number):
    """Drop a trailing ` # comment` that is outside quotes."""
    quote = None
    index = 0
    while index < len(text):
        char = text[index]
        if quote == '"' and char == "\\":
            index += 2
            continue
        if quote:
            if char == quote:
                if quote == "'" and text[index + 1:index + 2] == "'":
                    index += 2
                    continue
                quote = None
        elif char in "\"'" and (index == 0 or text[index - 1] in " [,:"):
            quote = char
        elif char == "#" and (index == 0 or text[index - 1] == " "):
            return text[:index].rstrip()
        index += 1
    if quote:
        raise YamlError(number, "a quoted string is not closed")
    return text.rstrip()


def _scalar(text, number):
    text = _strip_comment(text, number)
    if not text:
        return None
    if text[0] == "[":
        return _flow_sequence(text, number)
    if text[0] in "\"'":
        end = _quote_end(text, number)
        if text[end + 1:].strip():
            raise YamlError(number, "text after a quoted string")
        return _quoted(text[: end + 1], number)
    if text[0] in RESERVED_START:
        raise YamlError(number, "a value that starts with `%s` needs quotes: write %s" % (text[0], json.dumps(text)))
    if text.startswith("- ") or ": " in text or text.endswith(":"):
        raise YamlError(number, "a value that holds `: ` or starts with `- ` needs quotes: write %s" % json.dumps(text))
    return _plain(text, number)


def _plain(text, number):
    if text in BOOLS:
        return BOOLS[text]
    if text in NULLS:
        return None
    if LEADING_ZERO_RE.match(text):
        raise YamlError(number, "a number with a leading zero needs quotes: write %s" % json.dumps(text))
    if INT_RE.match(text):
        return int(text)
    return text


def _quote_end(text, number):
    quote = text[0]
    index = 1
    while index < len(text):
        char = text[index]
        if quote == '"' and char == "\\":
            index += 2
            continue
        if char == quote:
            if quote == "'" and text[index + 1:index + 2] == "'":
                index += 2
                continue
            return index
        index += 1
    raise YamlError(number, "a quoted string is not closed")


def _quoted(token, number):
    if token[0] == "'":
        return token[1:-1].replace("''", "'")
    try:
        return json.loads(token)
    except ValueError:
        raise YamlError(number, "an escape in a double-quoted string is not supported")


def _flow_sequence(text, number):
    if not text.endswith("]"):
        raise YamlError(number, "a flow list must end with `]` on the same line")
    body = text[1:-1].strip()
    if not body:
        return []
    items = []
    index = 0
    while index <= len(body):
        while index < len(body) and body[index] == " ":
            index += 1
        if index < len(body) and body[index] in "\"'":
            end = index + _quote_end(body[index:], number)
            items.append(_quoted(body[index:end + 1], number))
            index = end + 1
            while index < len(body) and body[index] == " ":
                index += 1
            if index < len(body) and body[index] != ",":
                raise YamlError(number, "expected `,` after a quoted item")
        else:
            end = body.find(",", index)
            end = len(body) if end < 0 else end
            item = body[index:end].strip()
            if not item:
                raise YamlError(number, "an empty item in a flow list")
            if item[0] in RESERVED_START or item[0] in "[":
                raise YamlError(number, "a list item that starts with `%s` needs quotes: write %s" % (item[0], json.dumps(item)))
            if any(char in item for char in "{}[]") or ": " in item:
                raise YamlError(number, "a list item with a brace, a bracket, or `: ` needs quotes")
            items.append(_plain(item, number))
            index = end
        index += 1
    return items
