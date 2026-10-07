import random

import pytest
import yaml

import miniformat as mf
from miniformat_dump import dumps


class StrLoader(yaml.SafeLoader):
    """PyYAML with implicit typing switched off: plain scalars stay str."""


StrLoader.yaml_implicit_resolvers = {}


def strload(text):
    return yaml.load(text, Loader=StrLoader)


def same_shape(ours, theirs):
    """Same nesting/keys/order.  Where YAML typed a scalar (no -> False,
    1 -> int, empty -> None) only require that it is a scalar; where YAML
    kept a str it must equal ours."""
    if isinstance(ours, dict):
        return (isinstance(theirs, dict) and len(ours) == len(theirs)
                and all(same_shape(ok, tk) and same_shape(ov, tv)
                        for (ok, ov), (tk, tv) in zip(ours.items(), theirs.items())))
    if isinstance(ours, list):
        return (isinstance(theirs, list) and len(ours) == len(theirs)
                and all(same_shape(a, b) for a, b in zip(ours, theirs)))
    if isinstance(theirs, (dict, list)):
        return False
    return ours == theirs if isinstance(theirs, str) else True


DOC = '''---
# comment
name: my-app   # trailing
port: 8080
tags:
  - web
  - prod
db:
  host: localhost
  note: |
    hello
      world

    bye
servers:
  - name: a
    ip: "1.2.3.4"
  - name: b
    opts: {}
empty:
"quoted key": x
'''


def test_basic():
    d = mf.loads(DOC)
    assert d["port"] == "8080" and d["tags"] == ["web", "prod"]
    assert d["db"]["note"] == "hello\n  world\n\nbye\n"
    assert d["servers"][1] == {"name": "b", "opts": {}}
    assert d["empty"] == "" and d["quoted key"] == "x"


def test_doc_is_valid_yaml_and_same_structure():
    assert strload(DOC) == mf.loads(DOC)
    assert same_shape(mf.loads(DOC), yaml.safe_load(DOC))  # default typing: shape only


@pytest.mark.parametrize("text,frag", [
    ("a: 1\n\tb: 2\n", "tab"),
    ("a: &x 1\n", "anchors"),
    ("a: *x\n", "aliases"),
    ("a: !!str 1\n", "tags"),
    ("a: >\n  x\n", "folded"),
    ("a: |-\n  x\n", "block scalar header"),
    ("a: 'x'\n", "single quotes"),
    ("a: [1, 2]\n", "flow"),
    ("a: {b: 1}\n", "flow"),
    ("a: 1\na: 2\n", "duplicate"),
    ("a: b: c\n", "quote"),
    ("a: 1\n---\nb: 2\n", "document markers"),
    ("a:\n- x\n", "indent list items"),
    ("a: 1\n  b: 2\n", "unexpected indentation"),
    ("- a\nb: 1\n", "expected '- '"),
    ('a: "x" y\n', "after quoted"),
    ('a: "x\n', "unterminated"),
    ('a: "\\q"\n', "escape"),
    ("a: x\x85y\n", "unsupported character"),
    ("", "empty document"),
    ("# only a comment\n", "empty document"),
    ("-  a\n", "one space"),
    ("- - a\n", "plain value cannot start"),
    ("just text\n", "key: value"),
])
def test_rejected(text, frag):
    with pytest.raises(mf.MiniFormatError) as e:
        mf.loads(text)
    assert frag in str(e.value)


def test_error_has_line_and_source():
    with pytest.raises(mf.MiniFormatError) as e:
        mf.loads("a: 1\nb: [x]\n")
    assert e.value.line == 2 and "b: [x]" in str(e.value)


def test_root_forms():
    assert mf.loads("[]\n") == [] and mf.loads("{}") == {}
    assert mf.loads("- a\n- b: 1\n  c: 2\n-\n  - x\n") == ["a", {"b": "1", "c": "2"}, ["x"]]


def test_crlf_and_bom():
    assert mf.loads("\ufeffa: 1\r\nb: 2\r\n") == {"a": "1", "b": "2"}


def test_block_scalar_edges():
    assert mf.loads("a: |\n  x\n\n\nb: 1\n") == {"a": "x\n", "b": "1"}
    assert mf.loads("a: |\n\n  x\n") == {"a": "\nx\n"}
    assert mf.loads("a: |\nb: 1\n") == {"a": "", "b": "1"}
    assert mf.loads("- |\n  # not a comment\n  x\n") == ["# not a comment\nx\n"]


def test_get():
    d = mf.loads("db:\n  port: 5432\n  on: yes\nl:\n  - a\n  - b\n")
    assert mf.get(d, "db.port", int) == 5432
    assert mf.get(d, "db.on", bool) is True
    assert mf.get(d, "l.1") == "b"
    assert mf.get(d, "db.nope", int, default=7) == 7
    with pytest.raises(KeyError):
        mf.get(d, "db.nope")
    with pytest.raises(ValueError, match="db.on"):
        mf.get(d, "db.on", int)


def test_dump_basics_and_errors():
    assert dumps({}) == "{}\n"
    with pytest.raises(TypeError, match="a.b"):
        dumps({"a": {"b": 1}})
    with pytest.raises(TypeError):
        dumps("x")
    with pytest.raises(TypeError):
        dumps({1: "x"})


def test_canonical_roundtrip_of_sample():
    d = mf.loads(DOC)
    assert mf.loads(dumps(d)) == d
    assert dumps(mf.loads(dumps(d))) == dumps(d)


# ---------------------------------------------------------------- fuzzing

ALPHABET = list("abc XYZ019:-#?,[]{}&*!|>'\"%@`\\/\t.~") + ["\n", "é", "\u2028", "\x85", "\x7f", "\U0001f600", "\x00"]
TRICKY = ["", " ", "no", "null", "1.10", "- x", "a: b", "a #b", "#a", "a:", ":", "-", "?", "{}", "[]", "---",
          "...", "x\n", "x\ny\n", "\nx\n", " x\n", "x\n\n", "x \n y\n", "a\tb", "\ta", "a\\b", '"q"', "'", "%x", "@x",
          "a\r\nb", "a\u2028b", "  ", "x\n  \ny\n"]


def rand_str(r):
    if r.random() < 0.3:
        return r.choice(TRICKY)
    return "".join(r.choice(ALPHABET) for _ in range(r.randint(0, 8)))


def rand_obj(r, depth=0):
    k = r.random()
    if depth > 3 or k < 0.45:
        return rand_str(r)
    if k < 0.75:
        return {rand_str(r): rand_obj(r, depth + 1) for _ in range(r.randint(0, 4))}
    return [rand_obj(r, depth + 1) for _ in range(r.randint(0, 4))]


def rand_root(r):
    while True:
        o = rand_obj(r)
        if isinstance(o, (dict, list)):
            return o


def test_fuzz_roundtrip_and_yaml_compat():
    r = random.Random(1234)
    for n in range(3000):
        obj = rand_root(r)
        text = dumps(obj)
        assert mf.loads(text) == obj, (obj, text)
        # the writer's output must be valid YAML with identical structure
        # for everything except scalar types (strings in, stringified out)
        assert strload(text) == obj, (obj, text)


# Random *structured text* the loader accepts must also parse as YAML.
LINE_BITS = ["a", "b c", "k: v", "k:", "- x", "- k: v", "-", "|", "k: |", '"q"', 'k: "v"', "# c", "", "{}", "[]",
             "k: {}", "- []", "x: y # c", "- &a b", "k: [1]", "k: 'q'", "\tk: v", "k: v: w", "---", "- - a"]


def test_fuzz_accepted_text_is_valid_yaml():
    r = random.Random(99)
    accepted = 0
    for n in range(20000):
        lines = []
        for _ in range(r.randint(1, 7)):
            lines.append(" " * r.choice([0, 0, 2, 2, 4, 6, 1]) + r.choice(LINE_BITS))
        text = "\n".join(lines) + "\n"
        try:
            ours = mf.loads(text)
        except mf.MiniFormatError:
            continue
        accepted += 1
        assert strload(text) == ours, (text, ours)
    assert accepted > 300


def test_tabs_regressions():
    for s in ["a\tb", "\ta", "x\n\ty\n"]:
        assert mf.loads(dumps({s: s, "l": [s]})) == {s: s, "l": [s]}
    with pytest.raises(mf.MiniFormatError):
        mf.loads("a\tb: 1\n")
    with pytest.raises(mf.MiniFormatError):
        mf.loads("a: |\n  \tx\n")


def test_loader_is_standalone(tmp_path):
    import shutil, subprocess, sys
    shutil.copy(mf.__file__, tmp_path / "miniformat.py")
    code = "import sys; sys.path.insert(0, sys.argv[1]); import miniformat; print(miniformat.loads('a: 1'))"
    out = subprocess.run([sys.executable, "-I", "-c", code, str(tmp_path)], cwd=tmp_path, capture_output=True, text=True)
    assert out.returncode == 0 and "'a': '1'" in out.stdout, out.stderr
