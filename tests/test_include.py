"""``#+include path``: a comment to YAML, replaced by the file's text here."""

import re

import pytest
import yaml

from miniformat import mfloader as mf


def write(tmp_path, files):
    for name, text in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="")
    return tmp_path


def load_file(path):
    with open(path, encoding="utf-8") as f:
        return mf.load(f)


def test_include_at_root_merges_entries(tmp_path):
    write(
        tmp_path,
        {"main.yaml": "a: 1\n#+include more.yaml\nz: 9\n", "more.yaml": "b: 2\nc: 3\n"},
    )
    d = load_file(tmp_path / "main.yaml")
    assert d == {"a": "1", "b": "2", "c": "3", "z": "9"}
    assert list(d) == ["a", "b", "c", "z"]


def test_include_as_the_whole_document(tmp_path):
    write(tmp_path, {"main.yaml": "#+include x.yaml\n", "x.yaml": "k: v\n"})
    assert load_file(tmp_path / "main.yaml") == {"k": "v"}


def test_include_indented_under_a_key(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "db:\n  #+include db.yaml\nother: x\n",
            "db.yaml": "host: h\nports:\n  - 1\n  - 2\nnote: |\n  text\n  more\n",
        },
    )
    assert load_file(tmp_path / "main.yaml") == {
        "db": {"host": "h", "ports": ["1", "2"], "note": "text\nmore\n"},
        "other": "x",
    }


def test_include_into_and_as_a_list(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "items:\n  - a\n  #+include items.yaml\n  - z\n",
            "items.yaml": "- b\n- k: v\n  m: n\n",
        },
    )
    assert load_file(tmp_path / "main.yaml") == {
        "items": ["a", "b", {"k": "v", "m": "n"}, "z"]
    }


def test_include_as_value_of_list_item_key(tmp_path):
    write(
        tmp_path,
        {"main.yaml": "- name: x\n  cfg:\n    #+include c.yaml\n", "c.yaml": "p: 1\n"},
    )
    assert load_file(tmp_path / "main.yaml") == [{"name": "x", "cfg": {"p": "1"}}]


def test_nested_includes_are_relative_to_the_including_file(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "#+include sub/a.yaml\n",
            "sub/a.yaml": "a: 1\n#+include b.yaml\n",
            "sub/b.yaml": "b: 2\n#+include deeper/c.yaml\n",
            "sub/deeper/c.yaml": "c: 3\n",
        },
    )
    assert load_file(tmp_path / "main.yaml") == {"a": "1", "b": "2", "c": "3"}


def test_same_file_may_be_included_twice_in_different_places(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "x:\n  #+include s.yaml\ny:\n  #+include s.yaml\n",
            "s.yaml": "k: v\n",
        },
    )
    assert load_file(tmp_path / "main.yaml") == {"x": {"k": "v"}, "y": {"k": "v"}}


def test_leading_document_marker_and_comments_in_included_file(tmp_path):
    write(
        tmp_path,
        {"main.yaml": "#+include i.yaml\nb: 2\n", "i.yaml": "# c\n---\na: 1\n"},
    )
    assert load_file(tmp_path / "main.yaml") == {"a": "1", "b": "2"}


def test_crlf_and_bom_in_included_file(tmp_path):
    (tmp_path / "i.yaml").write_bytes(b"\xef\xbb\xbfa: 1\r\nb:\r\n  - x\r\n")
    write(tmp_path, {"main.yaml": "#+include i.yaml\n"})
    assert load_file(tmp_path / "main.yaml") == {"a": "1", "b": ["x"]}


def test_empty_included_file_adds_nothing(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "a: 1\n#+include e.yaml\nb:\n  #+include e.yaml\n",
            "e.yaml": "# nothing\n",
        },
    )
    assert load_file(tmp_path / "main.yaml") == {"a": "1", "b": ""}


def test_duplicate_key_across_files_is_an_error_naming_the_file(tmp_path):
    write(tmp_path, {"main.yaml": "a: 1\n#+include d.yaml\n", "d.yaml": "x: 1\na: 2\n"})
    with pytest.raises(mf.MiniFormatError, match="duplicate") as e:
        load_file(tmp_path / "main.yaml")
    assert e.value.line == 2 and e.value.file.endswith("d.yaml")
    assert "d.yaml: line 2" in str(e.value)


def test_error_line_numbers_after_an_include_stay_correct(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "a: 1\n#+include i.yaml\n\nb: [bad]\n",
            "i.yaml": "x: 1\ny: 2\nz: 3\n",
        },
    )
    with pytest.raises(mf.MiniFormatError) as e:
        load_file(tmp_path / "main.yaml")
    assert e.value.line == 4 and e.value.file is None and "b: [bad]" in str(e.value)


def test_syntax_error_inside_included_file_points_there(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "ok: 1\n#+include bad.yaml\n",
            "bad.yaml": "fine: 1\nbroken: &anchor x\n",
        },
    )
    with pytest.raises(mf.MiniFormatError, match="anchors") as e:
        load_file(tmp_path / "main.yaml")
    assert e.value.line == 2 and e.value.file.endswith("bad.yaml")


def test_bad_character_inside_included_file_points_there(tmp_path):
    write(
        tmp_path, {"main.yaml": "#+include bad.yaml\n", "bad.yaml": "a: 1\nb: x\x01y\n"}
    )
    with pytest.raises(mf.MiniFormatError, match="unsupported character") as e:
        load_file(tmp_path / "main.yaml")
    assert e.value.line == 2 and e.value.file.endswith("bad.yaml")


def test_included_text_must_fit_where_it_is_placed(tmp_path):
    write(tmp_path, {"main.yaml": "a: 1\n#+include l.yaml\n", "l.yaml": "- x\n"})
    with pytest.raises(mf.MiniFormatError, match="list item inside a map"):
        load_file(tmp_path / "main.yaml")


def test_missing_file(tmp_path):
    write(tmp_path, {"main.yaml": "a: 1\n#+include nope.yaml\n"})
    with pytest.raises(mf.MiniFormatError, match="cannot include 'nope.yaml'") as e:
        load_file(tmp_path / "main.yaml")
    assert e.value.line == 2


def test_directory_and_non_utf8_are_errors_not_crashes(tmp_path):
    (tmp_path / "d").mkdir()
    (tmp_path / "bin.yaml").write_bytes(b"a: \xff\xfe\n")
    for name in ["d", "bin.yaml"]:
        write(tmp_path, {"main.yaml": "#+include %s\n" % name})
        with pytest.raises(mf.MiniFormatError, match="cannot include"):
            load_file(tmp_path / "main.yaml")


def test_include_loop_is_an_error_not_a_hang(tmp_path):
    write(tmp_path, {"a.yaml": "#+include b.yaml\n", "b.yaml": "#+include a.yaml\n"})
    with pytest.raises(mf.MiniFormatError, match="too many includes"):
        load_file(tmp_path / "a.yaml")
    write(tmp_path, {"self.yaml": "#+include self.yaml\n"})
    with pytest.raises(mf.MiniFormatError, match="too many includes"):
        load_file(tmp_path / "self.yaml")


def test_included_text_takes_the_indent_of_the_include_line(tmp_path):
    write(tmp_path, {"i.yaml": "a: 1\nb:\n  - x\n"})
    for pad, text in [
        (0, "{pad}#+include i.yaml\n"),
        (2, "r:\n{pad}#+include i.yaml\n"),
        (6, "r:\n  s:\n    t:\n{pad}#+include i.yaml\n"),
    ]:
        d = mf.loads(text.format(pad=" " * pad), base=str(tmp_path))
        while "r" in d or "s" in d or "t" in d:
            d = d[next(iter(d))]
        assert d == {"a": "1", "b": ["x"]}


def test_loads_needs_a_base_directory(tmp_path):
    write(tmp_path, {"i.yaml": "k: v\n"})
    with pytest.raises(mf.MiniFormatError, match="base"):
        mf.loads("#+include i.yaml\n")
    assert mf.loads("#+include i.yaml\n", base=str(tmp_path)) == {"k": "v"}


def test_file_objects_without_a_name_have_no_base():
    import io

    with pytest.raises(mf.MiniFormatError, match="base"):
        mf.load(io.StringIO("#+include x.yaml\n"))


def test_ordinary_comments_are_never_pragmas():
    text = (
        "#include nothing.yaml\n"
        "# include nothing.yaml\n"
        "# +include nothing.yaml\n"
        "#+ include nothing.yaml\n"
        "#+ text\n"
        "#+\n"
        "#+\tx\n"
        "# #+include nothing.yaml\n"
        "#included nothing.yaml\n"
        "#Include nothing.yaml\n"
        "#TODO fix\n"
        "#!shebang\n"
        "#-\n"
        "#\n"
        "a: 1\n"
    )
    assert mf.loads(text) == {"a": "1"}


def test_pragma_look_alikes_after_a_value_are_plain_comments():
    # only a pragma on a line of its own counts
    assert mf.loads("a: 1 #+include nothing.yaml\nb: x #+bogus\n") == {
        "a": "1",
        "b": "x",
    }
    assert mf.loads("- a #+bogus\n") == ["a"]


@pytest.mark.parametrize(
    "text,line,fragment",
    [
        ("#+bogus\n", 1, "unknown pragma '#+bogus'"),
        ("a: 1\n  #+inlcude x.yaml\n", 2, "unknown pragma '#+inlcude'"),
        ("a: 1\n#+include-all x.yaml\n", 2, "unknown pragma '#+include-all'"),
        ("#+bogus with args\na: 1\n", 1, "unknown pragma"),
        ("#+Include x.yaml\na: 1\n", 1, "malformed pragma"),
        ("#+1abc\na: 1\n", 1, "malformed pragma"),
        ("#++include x\na: 1\n", 1, "malformed pragma"),
        ("#+include\na: 1\n", 1, "needs a path"),
        ("a: 1\n#+include   \n", 2, "needs a path"),
    ],
)
def test_unknown_and_malformed_pragmas_are_errors(text, line, fragment):
    with pytest.raises(mf.MiniFormatError, match=re.escape(fragment)) as e:
        mf.loads(text, base=".")
    assert e.value.line == line and e.value.file is None


def test_error_shows_the_pragma_line():
    with pytest.raises(mf.MiniFormatError) as e:
        mf.loads("a: 1\n  #+bogus  x\n")
    assert str(e.value).endswith("\n    #+bogus  x")


def test_unknown_pragma_inside_an_included_file_names_that_file(tmp_path):
    write(
        tmp_path, {"main.yaml": "a: 1\n#+include i.yaml\n", "i.yaml": "b: 2\n#+oops\n"}
    )
    with pytest.raises(mf.MiniFormatError, match="unknown pragma") as e:
        load_file(tmp_path / "main.yaml")
    assert e.value.line == 2 and e.value.file.endswith("i.yaml")


def test_pragma_syntax_is_still_just_comments_to_yaml():
    text = "a: 1\n#+bogus\n#+++ nonsense ++\nb: 2\n"
    assert yaml.safe_load(text) == {"a": 1, "b": 2}


def test_pragmas_inside_a_block_scalar_are_just_text():
    assert mf.loads("a: |\n  #+bogus\n  x\n") == {"a": "#+bogus\nx\n"}


def test_include_inside_a_block_scalar_is_just_text():
    assert mf.loads("a: |\n  #+include nothing.yaml\n  x\n") == {
        "a": "#+include nothing.yaml\nx\n"
    }


def test_include_line_in_a_quoted_or_plain_value_is_not_special():
    assert mf.loads('a: "#+include x"\nb: "x #+include y"\n') == {
        "a": "#+include x",
        "b": "x #+include y",
    }


def test_pragma_files_still_parse_as_yaml(tmp_path):
    # the point of the syntax: any YAML parser reads the file (the include is
    # simply a comment to it)
    text = "a: 1\n#+include more.yaml\nb:\n  #+include more.yaml\n  c: 2\n"
    assert yaml.safe_load(text) == {"a": 1, "b": {"c": 2}}


def test_cli_reports_included_file_errors(tmp_path):
    import subprocess
    import sys

    write(tmp_path, {"main.yaml": "#+include bad.yaml\n", "bad.yaml": "a: 1\na: 2\n"})
    r = subprocess.run(
        [sys.executable, "-m", "miniformat", str(tmp_path / "main.yaml")],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1 and "bad.yaml: line 2: duplicate key" in r.stderr
    assert "main.yaml: " not in r.stderr.split("bad.yaml")[0]


def test_cli_follows_includes(tmp_path):
    import json
    import subprocess
    import sys

    write(tmp_path, {"main.yaml": "a: 1\n#+include i.yaml\n", "i.yaml": "b: 2\n"})
    r = subprocess.run(
        [sys.executable, "-m", "miniformat", str(tmp_path / "main.yaml")],
        capture_output=True,
        text=True,
    )
    assert json.loads(r.stdout) == {"a": "1", "b": "2"}
