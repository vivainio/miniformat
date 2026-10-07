import pytest

from miniformat import mfloader as mf


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
