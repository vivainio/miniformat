import pytest

from helpers import rand_root, rng, strload
from miniformat import mfloader as mf
from miniformat.mfdumper import dump, dumps


@pytest.mark.parametrize(
    "obj,expected",
    [
        ({}, "{}\n"),
        ([], "[]\n"),
        ({"a": "1"}, "a: 1\n"),
        ({"a": {"b": "c"}}, "a:\n  b: c\n"),
        ({"a": ["x", "y"]}, "a:\n  - x\n  - y\n"),
        (["x", "y"], "- x\n- y\n"),
        ([{"a": "1", "b": "2"}, {"c": "3"}], "- a: 1\n  b: 2\n- c: 3\n"),
        ([["a", "b"], ["c"]], "-\n  - a\n  - b\n-\n  - c\n"),
        ({"a": {}, "b": [], "c": ["z"]}, "a: {}\nb: []\nc:\n  - z\n"),
        ([{}, []], "- {}\n- []\n"),
        ({"a": ""}, 'a: ""\n'),
        ({"": "x"}, '"": x\n'),
        ({"a": "multi\nline\n"}, "a: |\n  multi\n  line\n"),
        ({"a": ["x\ny\n"]}, "a:\n  - |\n    x\n    y\n"),
        ([{"k": "x\ny\n", "m": "1"}], "- k: |\n    x\n    y\n  m: 1\n"),
        ({"a": "\nlead\n"}, "a: |\n\n  lead\n"),
        ({"a": "x\n\ny\n"}, "a: |\n  x\n\n  y\n"),
        ({"a": {"b": {"c": "x\n"}}}, "a:\n  b:\n    c: |\n      x\n"),
        (
            {"a": "no", "b": "8080", "c": "1.10"},
            "a: no\nb: 8080\nc: 1.10\n",
        ),  # plain: strings stay readable
        ({"url": "http://x:80/a"}, "url: http://x:80/a\n"),
        ({"z": "1", "a": "2"}, "z: 1\na: 2\n"),  # insertion order kept
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
        "1",
        "no",
        "null",
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
    obj = {"a: b": "1", "- x": "2", "": "3", "multi\nline": "4", "ok key": "5"}
    out = dumps(obj)
    assert out == '"a: b": 1\n"- x": 2\n"": 3\n"multi\\nline": 4\nok key: 5\n'
    assert mf.loads(out) == obj


def test_dumping_is_idempotent_on_loaded_text():
    text = "# c\nb: 2  # note\na:\n- x\n".replace("- x", "  - x")
    once = dumps(mf.loads(text))
    assert once == "b: 2\na:\n  - x\n"
    assert dumps(mf.loads(once)) == once


@pytest.mark.parametrize(
    "bad",
    [
        {"a": 1},
        {"a": None},
        {"a": True},
        {"a": 1.5},
        {"a": b"x"},
        {"a": {"b": [1]}},
        {"a": {1, 2}},
        ["x", 3],
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
        dumps({"a": {"b": ["ok", 5]}})
    with pytest.raises(TypeError, match="str()"):
        dumps({"a": 1})


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
    assert strload(dumps(obj)) == obj


def test_every_fuzz_object_is_valid_yaml_and_stable():
    r = rng(5)
    for _ in range(300):
        obj = rand_root(r)
        out = dumps(obj)
        assert dumps(mf.loads(out)) == out
