"""miniformat.mfdumper -- canonical writer for miniformat (see mfloader.py).

Not needed to read files; copy it next to mfloader.py (same package) only if
you also want to write them.  ``from miniformat import mfdumper``.
Output is deterministic (dict order preserved) and comments are not kept.
Only ``str``, ``dict`` (str keys) and ``list``/``tuple`` can be written;
convert numbers and bools with ``str()`` first.


MIT License -- see LICENSE.
"""

from .mfloader import (
    _BAD_CHAR,
    _COLON,
    _COMMENT,
    _PLAIN_BAD_START,
    _TAG,
)

__all__ = ["dumps", "dump"]


_ESC = {
    '"': '\\"',
    "\\": "\\\\",
    "\n": "\\n",
    "\t": "\\t",
    "\r": "\\r",
    "\b": "\\b",
    "\f": "\\f",
}


def _odd(s):
    """Characters that are never written raw (also the BOM, which a reader
    would drop at the start of a document)."""
    return _BAD_CHAR.search(s) or "\ufeff" in s


def _quote(s):
    out = []
    for c in s:
        if "\ud800" <= c <= "\udfff":
            raise ValueError("cannot write a lone surrogate (%r)" % c)
        if c in _ESC:
            out.append(_ESC[c])
        elif c == "\ufeff" or _BAD_CHAR.match(c) or c < " ":
            out.append("\\u%04x" % ord(c))
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


def _plain_ok(s):
    if not s or s != s.strip(" \t") or _odd(s) or "\n" in s or "\t" in s:
        return False
    if s[0] in _PLAIN_BAD_START:
        return False
    if s[0] in "-?:" and (len(s) == 1 or s[1] in " \t"):
        return False
    if _COLON.search(s) or _COMMENT.search(s) or s in ("{}", "[]"):
        return False
    return True


def _block_ok(s):
    if "\n" not in s or not s.endswith("\n") or s.endswith("\n\n"):
        return False
    if "\r" in s or _odd(s.replace("\n", "").replace("\t", "")):
        return False
    lines = s[:-1].split("\n")
    if any(ln.strip(" \t") == "" and ln != "" for ln in lines):
        return False
    first = next((ln for ln in lines if ln), None)
    return (
        first is not None
        and first[0] != " "
        and not any(ln[:1] == "\t" for ln in lines)
    )


def _scalar(s):
    return s if _plain_ok(s) else _quote(s)


def _tag_of(v):
    """(tag, inner) if v is a one-key map whose key is a tag name: it is
    written as '!Name inner', which the loader reads back as the same map."""
    if isinstance(v, dict) and len(v) == 1:
        ((k, inner),) = v.items()
        if isinstance(k, str) and _TAG.fullmatch(k):
            return k, inner
    return None


def _lines(obj, ind, path):
    pad = " " * ind
    if isinstance(obj, dict):
        out = []
        for k, v in obj.items():
            if not isinstance(k, str):
                raise TypeError(
                    "keys must be str, got %r at %s" % (k, path or "<root>")
                )
            out.extend(
                _entry(pad + _scalar(k) + ":", v, ind, path + "." + k if path else k)
            )
        return out
    out = []
    for n, v in enumerate(obj):
        sub = "%s[%d]" % (path, n)
        if isinstance(v, dict) and v and not _tag_of(v):
            inner = _lines(v, ind + 2, sub)
            inner[0] = pad + "- " + inner[0][ind + 2 :]
            out.extend(inner)
        else:
            out.extend(_entry(pad + "-", v, ind, sub))
    return out


def _entry(head, v, ind, path, tagged=True):
    """Render 'head' (e.g. 'key:' or '-') followed by value v.  A tag holds
    one value, so under a tag a tag-shaped map is written as a plain map."""
    tag = _tag_of(v) if tagged else None
    if tag:
        return _entry(head + " " + tag[0], tag[1], ind, path + "." + tag[0], False)
    if isinstance(v, str):
        if _block_ok(v):
            body = [(" " * (ind + 2) + ln) if ln else "" for ln in v[:-1].split("\n")]
            return [head + " |"] + body
        return [head + " " + _scalar(v)]
    if isinstance(v, (dict, list, tuple)):
        if not v:
            return [head + (" {}" if isinstance(v, dict) else " []")]
        return [head] + _lines(v, ind + 2, path)
    raise TypeError(
        "can only dump str, dict and list, got %s at %s (convert with str())"
        % (type(v).__name__, path or "<root>")
    )


def dumps(obj):
    """Serialize dict/list/str trees to canonical miniformat text."""
    if isinstance(obj, tuple):
        obj = list(obj)
    if not isinstance(obj, (dict, list)):
        raise TypeError("document root must be a dict or list")
    if not obj:
        return ("{}" if isinstance(obj, dict) else "[]") + "\n"
    return "\n".join(_lines(obj, 0, "")) + "\n"


def dump(obj, fp):
    fp.write(dumps(obj))
