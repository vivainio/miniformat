import pytest

import miniformat as mf


def test_returns_plain_python_types():
    d = mf.loads("a: 1\nb:\n  - x\n  - y: z\n")
    assert type(d) is dict and type(d["b"]) is list and type(d["a"]) is str


def test_error_is_a_valueerror_with_attributes():
    with pytest.raises(ValueError) as e:
        mf.loads("a: 1\nb: [x]\n")
    err = e.value
    assert isinstance(err, mf.MiniFormatError)
    assert err.line == 2 and "flow" in err.msg
    assert "line 2:" in str(err) and "b: [x]" in str(err)


def test_error_line_numbers_count_blank_and_comment_lines():
    with pytest.raises(mf.MiniFormatError) as e:
        mf.loads("# c\n\na: 1\n\n# c\nb: 'x'\n")
    assert e.value.line == 6


def test_error_source_line_is_stripped_of_indent():
    with pytest.raises(mf.MiniFormatError) as e:
        mf.loads("a:\n      b: &x 1\n")
    assert str(e.value).endswith("\n    b: &x 1")


def test_load_from_file(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text("a: é\n", encoding="utf-8")
    with open(p, encoding="utf-8") as f:
        assert mf.load(f) == {"a": "é"}


def test_loads_does_not_mutate_or_share_state():
    text = "- k: v\n- k: w\n"
    assert mf.loads(text) == mf.loads(text) == [{"k": "v"}, {"k": "w"}]


def test_inline_map_in_list_is_not_confused_by_quoted_values():
    assert mf.loads('- "a: b"\n- "k": v\n') == ["a: b", {"k": "v"}]


def test_list_item_comment_then_nested():
    assert mf.loads("-  # c\n  - a\n") == [["a"]]


def test_deep_but_reasonable_nesting():
    n = 200
    text = "".join(" " * i + "k:\n" for i in range(n)) + " " * n + "v: 1\n"
    d = mf.loads(text)
    for _ in range(n):
        d = d["k"]
    assert d == {"v": "1"}


def test_large_document():
    text = "".join("k%d:\n  - a%d\n  - b: %d\n" % (i, i, i) for i in range(5000))
    d = mf.loads(text)
    assert len(d) == 5000 and d["k4999"][1] == {"b": "4999"}


def test_block_scalar_at_eof_without_newline_matches_yaml():
    assert mf.loads("a: |\n  x") == {"a": "x"}
    assert mf.loads("a: |\n  x\n") == {"a": "x\n"}
    assert mf.loads("- |\n  x\n  y") == ["x\ny"]


def test_mixed_line_endings():
    assert mf.loads("a: 1\r\nb: 2\nc: 3\r") == {"a": "1", "b": "2", "c": "3"}


@pytest.mark.parametrize("text", ["a: 1", "a: 1\n", "a: 1\n\n\n", "\n\na: 1"])
def test_trailing_newlines_dont_matter(text):
    assert mf.loads(text) == {"a": "1"}


@pytest.mark.parametrize(
    "bad",
    [
        "\x00",
        "\x08",
        "\x0b",
        "\x0c",
        "\x1b",
        "\x7f",
        "\x85",
        "\u2028",
        "\u2029",
        "\ufffe",
        "\uffff",
    ],
)
def test_unprintable_characters_rejected_everywhere(bad):
    for text in [
        "a: x%sy\n" % bad,
        "k%s: v\n" % bad,
        "# c%s\na: 1\n" % bad,
        "a: |\n  x%s\n" % bad,
    ]:
        with pytest.raises(mf.MiniFormatError, match="unsupported character"):
            mf.loads(text)


@pytest.mark.parametrize(
    "ok", ["\xa0", "é", "日本", "\U0001f600", "\u2027", "\u202a", "\ue000", "\ufffd"]
)
def test_printable_unicode_accepted(ok):
    assert mf.loads('a: "x%sy"\n' % ok) == {"a": "x%sy" % ok}


# ------------------------------------------------------------------ get()

DATA = mf.loads(
    "db:\n  port: 5432\n  on: yes\n  ratio: 0.5\n  name: x\nl:\n  - a\n  - b\n  - k: v\n"
)


def test_get_paths_and_types():
    assert mf.get(DATA, "db.port") == "5432"
    assert mf.get(DATA, "db.port", int) == 5432
    assert mf.get(DATA, "db.ratio", float) == 0.5
    assert mf.get(DATA, "l.1") == "b"
    assert mf.get(DATA, "l.2.k") == "v"


def test_get_str_cast_on_containers_stringifies():
    # the default cast is str(); ask for `dict`/`list` (or `lambda v: v`) to keep containers
    assert mf.get(DATA, "db", dict) == DATA["db"]
    assert mf.get(DATA, "l", list)[0] == "a"


@pytest.mark.parametrize(
    "word,expected",
    [
        ("true", True),
        ("True", True),
        ("YES", True),
        ("on", True),
        ("1", True),
        ("false", False),
        ("No", False),
        ("OFF", False),
        ("0", False),
    ],
)
def test_get_bool_words(word, expected):
    assert mf.get({"x": word}, "x", bool) is expected


@pytest.mark.parametrize("word", ["", "2", "y", "maybe", "null"])
def test_get_bool_rejects_other_words(word):
    with pytest.raises(ValueError, match="x"):
        mf.get({"x": word}, "x", bool)


def test_get_missing_and_defaults():
    for path in ["nope", "db.nope", "l.9", "l.x", "db.port.deeper", ""]:
        with pytest.raises(KeyError):
            mf.get(DATA, path)
        assert mf.get(DATA, path, int, default=7) == 7
    assert mf.get(DATA, "nope", default=None) is None


def test_get_default_is_not_cast():
    assert mf.get(DATA, "nope", int, default="d") == "d"


def test_get_bad_conversion_names_the_path():
    with pytest.raises(ValueError, match=r"db\.name.*'x'"):
        mf.get(DATA, "db.name", int)


def test_get_custom_callable():
    assert mf.get({"a": "1,2,3"}, "a", lambda s: s.split(",")) == ["1", "2", "3"]
    assert mf.get({"a": "x"}, "a", len) == 1


@pytest.mark.parametrize("ws", ["\xa0", "\u2003", "\u3000", "\u200b", "\u00a0\u00a0"])
def test_only_space_and_tab_are_whitespace(ws):
    # unicode spaces are ordinary characters, never trimmed or treated as blank
    assert mf.loads("a: x%s\n" % ws) == {"a": "x" + ws}
    assert mf.loads("a: %sx\n" % ws) == {"a": ws + "x"}
    assert mf.loads("- %s\n" % ws) == [ws]
    assert mf.loads("k%s: v\n" % ws) == {"k" + ws: "v"}
    assert mf.loads("a: |\n  x\n  %s\n" % ws) == {"a": "x\n%s\n" % ws}
    assert mf.loads("%sa: 1\n" % ws) == {
        ws + "a": "1"
    }  # not indentation: part of the key
    assert mf.loads("a:\n%sb: 1\n" % ws) == {"a": "", ws + "b": "1"}
