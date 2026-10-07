"""miniformat -- a strict, tiny subset of YAML.  Single file, stdlib only.

This is the loader; it is self-contained, so vendor just this file.  The optional
writer lives in miniformat_dump.py.

Every document this module accepts is also valid YAML, so any YAML parser
(and any editor's YAML highlighting) can read it.  The difference is meaning:
here *every scalar is a string*.  ``no``, ``8080`` and ``1.10`` stay as
written; interpret them on the consumer side with ``get(data, "a.b", int)``.

The subset
----------
* block maps (``key: value``) and block lists (``- item``), nested by
  indenting with spaces (tabs are an error);
* a list under a key is always indented below it (never at the key's column);
* scalars: plain (``text``) or double-quoted with JSON escapes (``"a\\tb"``);
* multi-line text: ``|`` literal blocks only (clip chomping: one final newline);
* ``{}`` and ``[]`` as the only flow syntax, for empty containers;
* ``# comments``; an optional leading ``---``.
* an empty value (``key:``) loads as ``""``.

Rejected with a line-numbered error: tabs for indentation, anchors/aliases/
tags, ``>`` folded scalars, chomp indicators, single quotes, other flow syntax,
duplicate keys, multiple documents, ``a: b: c`` (quote it), and
multi-line plain scalars.

API: ``loads``, ``load``, ``get``, ``MiniFormatError``.
(``dumps`` / ``dump`` are in miniformat_dump.py.)
"""

import json
import re

__version__ = "0.1.0"
__all__ = ["loads", "load", "get", "MiniFormatError"]

# MIT License -- see LICENSE.  Copy this file into your project freely;
# keep this notice.


class MiniFormatError(ValueError):
    """Raised for input outside the subset.  ``.line`` is 1-based (or None)."""

    def __init__(self, msg, line=None, source=None):
        self.msg = msg
        self.line = line
        text = msg if line is None else "line %d: %s" % (line, msg)
        if source is not None:
            text += "\n    " + source.strip()
        super().__init__(text)


# Characters YAML parsers accept, minus the exotic line breaks (NEL, LS, PS).
_BAD_CHAR = re.compile(
    "[^\t\n\x20-\x7e\xa0-\u2027\u202a-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]"
)
_QUOTED = re.compile(r'"(?:[^"\\]|\\.)*"')
_COMMENT = re.compile(r"[ \t]#")
_COLON = re.compile(r":(?:[ \t]|$)")
_DOC_MARK = re.compile(r"(?:---|\.\.\.)(?:[ \t]|$)")
_PLAIN_BAD_START = set("[]{}&*!|>'\"%@`#,")


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------


def loads(text):
    """Parse a document into nested ``dict`` / ``list`` / ``str``."""
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    for n, line in enumerate(lines, 1):
        m = _BAD_CHAR.search(line)
        if m:
            raise MiniFormatError(
                "unsupported character %r" % m.group(), n, line
            )
    return _Parser(lines).document()


def load(fp):
    """Like :func:`loads`, reading text from a file object."""
    return loads(fp.read())


def _split_comment(s):
    """Drop a trailing ``# comment`` (``#`` must follow whitespace)."""
    m = _COMMENT.search(s)
    return s[: m.start()] if m else s


def _is_blank(line):
    s = line.strip()
    return not s or s[0] == "#"


class _Parser:
    def __init__(self, lines):
        self.lines = lines
        self.i = 0

    def err(self, msg, i=None):
        i = self.i if i is None else i
        src = self.lines[i] if i < len(self.lines) else None
        return MiniFormatError(msg, i + 1, src)

    # -- cursor helpers ----------------------------------------------------

    def skip(self):
        """Advance to the next structural line; return its index or None."""
        while self.i < len(self.lines) and _is_blank(self.lines[self.i]):
            self.i += 1
        if self.i >= len(self.lines):
            return None
        line = self.lines[self.i]
        content = line.lstrip(" ")
        if content[0] == "\t":
            raise self.err("tabs are not allowed for indentation")
        if line == content and _DOC_MARK.match(content):
            raise self.err("document markers are only allowed as a first-line '---'")
        return self.i

    def indent_of(self, i):
        line = self.lines[i]
        return len(line) - len(line.lstrip(" "))

    # -- grammar -------------------------------------------------------------

    def document(self):
        k = self.i
        while k < len(self.lines) and _is_blank(self.lines[k]):
            k += 1
        if k < len(self.lines) and re.match(r"---(?:[ \t]+#.*)?$", self.lines[k]):
            self.i = k + 1
        j = self.skip()
        if j is None:
            raise MiniFormatError("empty document")
        if self.indent_of(j) != 0:
            raise self.err("document must start at column 0")
        content = self.lines[j]
        if _split_comment(content).rstrip() in ("{}", "[]"):
            result = {} if content.startswith("{") else []
            self.i += 1
        else:
            result = self.block(-1)
        if self.skip() is not None:
            raise self.err("unexpected content (inconsistent indentation?)")
        return result

    def block(self, parent):
        """Parse the map/list starting at the next line, indented > parent."""
        j = self.skip()
        if j is None or self.indent_of(j) <= parent:
            return None
        ind = self.indent_of(j)
        content = self.lines[j][ind:]
        if content == "-" or content.startswith("- "):
            return self.list_(ind)
        return self.map_(ind)

    def map_(self, ind):
        result = {}
        while True:
            j = self.skip()
            if j is None:
                break
            cur = self.indent_of(j)
            if cur < ind:
                break
            if cur > ind:
                raise self.err("unexpected indentation")
            content = self.lines[j][ind:]
            if content == "-" or content.startswith("- "):
                raise self.err(
                    "list item inside a map; indent list items below their key"
                )
            entry = self.split_entry(content)
            if entry is None:
                raise self.err("expected 'key: value'")
            key, rest = entry
            if key in result:
                raise self.err("duplicate key %r" % key)
            result[key] = self.value(rest, ind)
        return result

    def list_(self, ind):
        result = []
        while True:
            j = self.skip()
            if j is None:
                break
            cur = self.indent_of(j)
            if cur < ind:
                break
            if cur > ind:
                raise self.err("unexpected indentation")
            content = self.lines[j][ind:]
            if content == "-":
                rest = ""
            elif content.startswith("- "):
                rest = content[2:]
                if rest.startswith(" "):
                    raise self.err("exactly one space is allowed after '-'")
            else:
                raise self.err("expected '- ' list item")
            if rest and not _is_blank(rest) and rest[0] != "|" \
                    and self.split_entry(rest) is not None:
                # '- key: v' -> rewrite as a map line indented under the dash
                self.lines[j] = " " * (ind + 2) + rest
                result.append(self.map_(ind + 2))
            else:
                result.append(self.value(rest, ind))
        return result

    # -- values ----------------------------------------------------------------

    def value(self, rest, parent):
        """Value after 'key:' or '-'; the current line is self.i."""
        rest = rest.strip(" ")
        if rest == "" or rest[0] == "#":
            self.i += 1
            nested = self.block(parent)
            return "" if nested is None else nested
        if rest[0] == "|":
            if _split_comment(rest).rstrip() != "|":
                raise self.err("only a plain '|' block scalar header is supported")
            return self.block_scalar(parent)
        v = self.inline(rest)
        self.i += 1
        return v

    def inline(self, rest):
        if rest[0] == '"':
            m = _QUOTED.match(rest)
            if not m:
                raise self.err("unterminated or multi-line quoted string")
            tail = rest[m.end():]
            if tail.strip() and not re.match(r"[ \t]+#", tail):
                raise self.err("unexpected text after quoted string")
            return self.unquote(m.group())
        s = _split_comment(rest).rstrip()
        if s == "{}":
            return {}
        if s == "[]":
            return []
        self.check_plain(s)
        return s

    def unquote(self, token):
        try:
            s = json.loads(token)
        except ValueError as e:
            raise self.err("bad escape in quoted string (%s)" % e) from None
        if any("\ud800" <= c <= "\udfff" for c in s):
            raise self.err("lone surrogate in quoted string")
        return s

    def check_plain(self, s):
        if not s:
            raise self.err("empty value")
        c = s[0]
        if c in _PLAIN_BAD_START:
            hint = {
                "[": "flow syntax is not supported (only [] and {})",
                "{": "flow syntax is not supported (only [] and {})",
                "&": "anchors are not supported",
                "*": "aliases are not supported",
                "!": "tags are not supported",
                ">": "folded scalars are not supported; use '|'",
                "'": "single quotes are not supported; use double quotes",
            }.get(c, "quote this value with double quotes")
            raise self.err("a plain value cannot start with %r: %s" % (c, hint))
        if c in "-?:" and (len(s) == 1 or s[1] in " \t"):
            raise self.err("a plain value cannot start with %r; quote it" % c)
        if _COLON.search(s):
            raise self.err("': ' inside a plain value; quote it with double quotes")
        if "\t" in s:
            raise self.err("tab inside a plain value; quote it and use \\t")

    def split_entry(self, content):
        """Split 'key: rest' -> (key, rest), or None if not a map entry."""
        if content[0] == '"':
            m = _QUOTED.match(content)
            if not m or not _COLON.match(content, m.end()):
                return None
            return self.unquote(m.group()), content[m.end() + 1:]
        colon = _COLON.search(content)
        if not colon:
            return None
        comment = _COMMENT.search(content)
        if comment and comment.start() < colon.start():
            return None
        key = content[: colon.start()].rstrip()
        self.check_plain(key)
        return key, content[colon.end():]

    def block_scalar(self, parent):
        """Read a '|' block whose header is on the current line."""
        self.i += 1
        body = []
        content_indent = None
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if not line.strip():
                if content_indent is not None and len(line) > content_indent:
                    raise self.err("whitespace-only line longer than the block indent")
                if content_indent is None and line:
                    # leading blank line; any width is fine only if it is not
                    # wider than the (not yet known) indent -- checked below
                    body.append(line)
                else:
                    body.append("")
                self.i += 1
                continue
            ind = len(line) - len(line.lstrip(" "))
            if content_indent is None:
                if ind <= parent:
                    break
                content_indent = ind
                for k, b in enumerate(body):
                    if len(b) > content_indent:
                        raise self.err(
                            "whitespace-only line longer than the block indent",
                            self.i - len(body) + k,
                        )
                    body[k] = ""
            elif ind < content_indent:
                break
            if ind == content_indent and line[ind] == "\t":
                raise self.err("a block line cannot start with a tab; use a quoted string")
            body.append(line[content_indent:])
            self.i += 1
        if content_indent is None:
            return ""
        while body and body[-1] == "":
            body.pop()
        return "\n".join(body) + "\n" if body else ""


# --------------------------------------------------------------------------
# typed access
# --------------------------------------------------------------------------

_MISSING = object()
_BOOLS = {"true": True, "yes": True, "on": True, "1": True,
          "false": False, "no": False, "off": False, "0": False}


def get(data, path, cast=str, default=_MISSING):
    """Fetch ``data["a"]["b"][0]`` as ``get(data, "a.b.0")``, converting it.

    ``cast`` may be ``str``, ``int``, ``float``, ``bool`` (true/false/yes/no/
    on/off/1/0, case-insensitive) or any callable.  A missing path returns
    ``default`` if given, else raises ``KeyError``; a bad value raises
    ``ValueError`` naming the path.
    """
    cur = data
    for part in path.split("."):
        try:
            cur = cur[int(part)] if isinstance(cur, list) else cur[part]
        except (KeyError, IndexError, ValueError, TypeError):
            if default is not _MISSING:
                return default
            raise KeyError(path) from None
    try:
        if cast is bool:
            if not isinstance(cur, str) or cur.lower() not in _BOOLS:
                raise ValueError(cur)
            return _BOOLS[cur.lower()]
        return cast(cur)
    except (ValueError, TypeError):
        raise ValueError("%s: cannot convert %r with %s" % (
            path, cur, getattr(cast, "__name__", cast))) from None



# --------------------------------------------------------------------------
# command line:  python miniformat.py FILE      (prints JSON)
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        sys.exit("usage: miniformat.py FILE   (prints JSON; see miniformat_dump.py --fmt)")
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            parsed = load(f)
    except MiniFormatError as e:
        sys.exit("%s: %s" % (sys.argv[1], e))
    print(json.dumps(parsed, indent=2, ensure_ascii=False))
