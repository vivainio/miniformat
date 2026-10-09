import pytest

from helpers import rand_root, rng, same, typedload
from miniformat import mfloader as mf
from miniformat.mfdumper import dump, dumps


@pytest.mark.parametrize(
    "obj,expected",
    [
        ({}, "{}\n"),
        ([], "[]\n"),
        ({"a": 1}, "a: 1\n"),
        ({"a": "1"}, 'a: "1"\n'),
        ({"a": {"b": "c"}}, "a:\n  b: c\n"),
        ({"a": ["x", "y"]}, "a:\n  - x\n  - y\n"),
        (["x", "y"], "- x\n- y\n"),
        ([{"a": 1, "b": 2}, {"c": 3}], "- a: 1\n  b: 2\n- c: 3\n"),
        ([["a", "b"], ["c"]], "-\n  - a\n  - b\n-\n  - c\n"),
        ({"a": {}, "b": [], "c": ["z"]}, "a: {}\nb: []\nc:\n  - z\n"),
        ([{}, []], "- {}\n- []\n"),
        ({"a": {"!Ref": "x"}}, "a: !Ref x\n"),
        ({"a": {"!Ref": ""}}, 'a: !Ref ""\n'),
        ({"a": {"!Sub": "l\nm\n"}}, "a: !Sub |\n  l\n  m\n"),
        ({"a": {"!If": ["c", {"!Ref": "y"}]}}, "a: !If\n  - c\n  - !Ref y\n"),
        ({"a": {"!A": {}}}, "a: !A {}\n"),
        ({"a": {"!A": {"!B": "x"}}}, 'a: !A\n  "!B": x\n'),
        ({"!Ref": "x"}, '"!Ref": x\n'),
        ({"a": {"!Ref": "x", "b": "y"}}, 'a:\n  "!Ref": x\n  b: y\n'),
        ({"a": {"!a b": "x"}}, 'a:\n  "!a b": x\n'),
        ([{"!Ref": "x"}, {"!Ref": "x", "k": "v"}], '- !Ref x\n- "!Ref": x\n  k: v\n'),
        ({"a": ""}, 'a: ""\n'),
        ({"": "x"}, '"": x\n'),
        ({"a": "multi\nline\n"}, "a: |\n  multi\n  line\n"),
        ({"a": ["x\ny\n"]}, "a:\n  - |\n    x\n    y\n"),
        ([{"k": "x\ny\n", "m": 1}], "- k: |\n    x\n    y\n  m: 1\n"),
        ({"a": "\nlead\n"}, "a: |\n\n  lead\n"),
        ({"a": "x\n\ny\n"}, "a: |\n  x\n\n  y\n"),
        ({"a": {"b": {"c": "x\n"}}}, "a:\n  b:\n    c: |\n      x\n"),
        (
            {"a": "no", "b": "8080", "c": "1.10", "d": "yes", "e": "010"},
            'a: no\nb: "8080"\nc: "1.10"\nd: yes\ne: 010\n',
        ),  # plain unless it would read back as a number, bool or null
        (
            {"i": 80, "f": 1.5, "t": True, "n": None, "s": "true"},
            'i: 80\nf: 1.5\nt: true\nn: null\ns: "true"\n',
        ),
        ([1, -2.5, False, None], "- 1\n- -2.5\n- false\n- null\n"),
        ({"a": {"!Ref": 80}}, "a: !Ref 80\n"),
        ({"url": "http://x:80/a"}, "url: http://x:80/a\n"),
        ({"z": 1, "a": 2}, "z: 1\na: 2\n"),  # insertion order kept
        ({"é": "日本"}, "é: 日本\n"),
        ((("a", "b")), "- a\n- b\n"),
    ],
)
def test_canonical_output(obj, expected):
    assert dumps(obj) == expected
    assert mf.loads(dumps(obj)) == (list(obj) if isinstance(obj, tuple) else obj)


@pytest.mark.parametrize(
    "value,quoted",
    [
        ("x y ", '"x y "'),
        (" x", '" x"'),
        ("a: b", '"a: b"'),
        ("a #b", '"a #b"'),
        ("#a", '"#a"'),
        ("- a", '"- a"'),
        ("-", '"-"'),
        ("?", '"?"'),
        (":", '":"'),
        ("a:", '"a:"'),
        ("{}", '"{}"'),
        ("[]", '"[]"'),
        ("[a]", '"[a]"'),
        ("{a}", '"{a}"'),
        ("|", '"|"'),
        (">", '">"'),
        ("&a", '"&a"'),
        ("*a", '"*a"'),
        ("!t", '"!t"'),
        ("%x", '"%x"'),
        ("@x", '"@x"'),
        ("`x", '"`x"'),
        (",x", '",x"'),
        ("'x", '"\'x"'),
        ('"x', '"\\"x"'),
        ("1", '"1"'),
        ("-5", '"-5"'),
        ("1.10", '"1.10"'),
        ("1e3", '"1e3"'),
        ("true", '"true"'),
        ("false", '"false"'),
        ("null", '"null"'),
        ("a\tb", '"a\\tb"'),
        ("\ufeff", '"\\ufeff"'),
        ("x\ufeffy", '"x\\ufeffy"'),
        ("\x00", '"\\u0000"'),
        ("\x7f", '"\\u007f"'),
        ("\x85", '"\\u0085"'),
        ("a\u2028b", '"a\\u2028b"'),
        ("a\nb", '"a\\nb"'),
        ("a\r\nb", '"a\\r\\nb"'),
        ("x\n\n", '"x\\n\\n"'),
        (" x\n", '" x\\n"'),
        ("x\n \ny\n", '"x\\n \\ny\\n"'),
        ("\tx\n", '"\\tx\\n"'),
    ],
)
def test_values_that_need_quotes(value, quoted):
    assert dumps({"k": value}) == "k: %s\n" % quoted
    assert mf.loads(dumps({"k": value})) == {"k": value}
    assert dumps([value]) == "- %s\n" % quoted


@pytest.mark.parametrize(
    "value",
    [
        "a-b",
        "a:b",
        "a#b",
        "a b",
        "x[1]",
        "no",
        "yes",
        "~",
        "010",
        "0x1F",
        "+1",
        ".5",
        "1.",
        "True",
        "NaN",
        "1_000",
        "9223372036854775808",
        "1e999",
        "é",
        "a'b",
        'a"b',
        "a,b",
        "-x",
        "?x",
        ":x",
        "a\u00a0b",
        "a\\b",
        "C:\\dir",
    ],
)
def test_values_that_stay_plain(value):
    assert dumps({"k": value}) == "k: %s\n" % value


@pytest.mark.parametrize("bad", ["\ud800", "x\udfffy"])
def test_lone_surrogates_cannot_be_written(bad):
    for obj in [{"k": bad}, [bad], {bad: "v"}]:
        with pytest.raises(ValueError, match="surrogate"):
            dumps(obj)


def test_keys_are_quoted_like_values():
    obj = {"a: b": 1, "- x": 2, "": 3, "multi\nline": 4, "ok key": 5}
    out = dumps(obj)
    assert out == '"a: b": 1\n"- x": 2\n"": 3\n"multi\\nline": 4\nok key: 5\n'
    assert same(mf.loads(out), obj)


def test_dumping_is_idempotent_on_loaded_text():
    text = "# c\nb: 2  # note\na:\n- x\n".replace("- x", "  - x")
    once = dumps(mf.loads(text))
    assert once == "b: 2\na:\n  - x\n"
    assert dumps(mf.loads(once)) == once


@pytest.mark.parametrize(
    "bad",
    [
        {"a": b"x"},
        {"a": {"b": [b"y"]}},
        {"a": {1, 2}},
        ["x", 2**63],
        ["x", -(2**63) - 1],
        {"a": float("nan")},
        {"a": float("inf")},
        {"a": -float("inf")},
        {1: "x"},
        {None: "x"},
        {("t",): "x"},
    ],
)
def test_non_string_leaves_and_keys_are_type_errors(bad):
    with pytest.raises(TypeError):
        dumps(bad)


def test_type_error_names_the_path():
    with pytest.raises(TypeError, match=r"a\.b\[1\]"):
        dumps({"a": {"b": ["ok", 2**70]}})
    with pytest.raises(TypeError, match="64 bits"):
        dumps({"a": 2**64})
    with pytest.raises(TypeError, match="finite"):
        dumps({"a": float("inf")})


@pytest.mark.parametrize("root", ["x", 1, None, 3.5, b"x"])
def test_root_must_be_container(root):
    with pytest.raises(TypeError, match="root"):
        dumps(root)


def test_dump_to_file(tmp_path):
    p = tmp_path / "o.yaml"
    with open(p, "w", encoding="utf-8") as f:
        dump({"a": ["é"]}, f)
    assert p.read_text("utf-8") == "a:\n  - é\n"


def test_output_always_ends_with_single_newline():
    for obj in [{"a": "x"}, ["x"], {"a": "x\n"}, {"a": ["y\n"]}, {}, []]:
        out = dumps(obj)
        assert out.endswith("\n") and not out.endswith("\n\n")


def test_no_trailing_whitespace_in_output():
    obj = {"a": "x \ny\n", "b": ["p q", "r\n\ns\n"], "c": {"d": "t\n"}}
    for line in dumps(obj).split("\n"):
        assert line == line.rstrip() or line.startswith(" ") and "x " in line


def test_deeply_nested_roundtrip():
    obj = "leaf\n"
    for i in range(60):
        obj = {"k": obj} if i % 2 else [obj]
    assert mf.loads(dumps(obj)) == obj
    assert same(typedload(dumps(obj)), obj)


def test_every_fuzz_object_is_valid_yaml_and_stable():
    r = rng(5)
    for _ in range(300):
        obj = rand_root(r)
        out = dumps(obj)
        assert dumps(mf.loads(out)) == out


def _tag_some(r, obj):
    """Randomly wrap values in one-key tag maps."""
    if isinstance(obj, dict):
        obj = {k: _tag_some(r, v) for k, v in obj.items()}
    elif isinstance(obj, list):
        obj = [_tag_some(r, v) for v in obj]
    return {r.choice(["!A", "!Fn::B", "!c"]): obj} if r.random() < 0.3 else obj


def test_tagged_trees_roundtrip_and_yaml_agrees():
    r = rng(5)
    for _ in range(300):
        obj = _tag_some(r, rand_root(r))
        if not isinstance(obj, (dict, list)):
            continue
        text = dumps(obj)
        assert same(mf.loads(text), obj), (obj, text)
        assert same(typedload(text), obj), (obj, text)
        assert dumps(mf.loads(text)) == text


def test_typed_values_roundtrip():
    obj = {
        "i": [0, -1, 2**63 - 1, -(2**63)],
        "f": [1.5, -0.0, 1e22, 1e-7, 5.0],
        "b": [True, False],
        "n": None,
        "s": ["1", "1.5", "true", "null", "-0", "e5", "1e5"],
    }
    out = dumps(obj)
    assert same(mf.loads(out), obj)
    assert same(typedload(out), obj)
