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
    assert d == {"a": 1, "b": 2, "c": 3, "z": 9}
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
        "db": {"host": "h", "ports": [1, 2], "note": "text\nmore\n"},
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
    assert load_file(tmp_path / "main.yaml") == [{"name": "x", "cfg": {"p": 1}}]


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
    assert load_file(tmp_path / "main.yaml") == {"a": 1, "b": 2, "c": 3}


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
    assert load_file(tmp_path / "main.yaml") == {"a": 1, "b": 2}


def test_crlf_and_bom_in_included_file(tmp_path):
    (tmp_path / "i.yaml").write_bytes(b"\xef\xbb\xbfa: 1\r\nb:\r\n  - x\r\n")
    write(tmp_path, {"main.yaml": "#+include i.yaml\n"})
    assert load_file(tmp_path / "main.yaml") == {"a": 1, "b": ["x"]}


def test_empty_included_file_adds_nothing(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "a: 1\n#+include e.yaml\nb:\n  #+include e.yaml\n",
            "e.yaml": "# nothing\n",
        },
    )
    assert load_file(tmp_path / "main.yaml") == {"a": 1, "b": ""}


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
        assert d == {"a": 1, "b": ["x"]}


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
    assert mf.loads(text) == {"a": 1}


def test_pragma_look_alikes_after_a_value_are_plain_comments():
    # only a pragma on a line of its own counts
    assert mf.loads("a: 1 #+include nothing.yaml\nb: x #+bogus\n") == {
        "a": 1,
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
    assert json.loads(r.stdout) == {"a": 1, "b": 2}


# ---------------------------------------------------------------------- globs


def test_glob_includes_every_match_in_sorted_order(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "first: 1\n#+include conf.d/*.yaml\nlast: 9\n",
            "conf.d/20-b.yaml": "b: 2\n",
            "conf.d/10-a.yaml": "a: 1\n",
            "conf.d/30-c.yaml": "c: 3\n",
            "conf.d/ignored.txt": "zzz: no\n",
        },
    )
    d = load_file(tmp_path / "main.yaml")
    assert list(d) == ["first", "a", "b", "c", "last"]


def test_glob_order_is_plain_string_order_not_numeric(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "#+include d/*.yaml\n",
            "d/10-x.yaml": "x: 1\n",
            "d/2-y.yaml": "y: 2\n",
            "d/B.yaml": "b: 3\n",
            "d/a.yaml": "a: 4\n",
        },
    )
    assert list(load_file(tmp_path / "main.yaml")) == ["x", "y", "b", "a"]


def test_glob_with_no_match_is_fine(tmp_path):
    write(
        tmp_path, {"main.yaml": "a: 1\n#+include none/*.yaml\nb:\n  #+include *.nope\n"}
    )
    assert load_file(tmp_path / "main.yaml") == {"a": 1, "b": ""}
    (tmp_path / "empty").mkdir()
    write(tmp_path, {"main2.yaml": "a: 1\n#+include empty/*\n"})
    assert load_file(tmp_path / "main2.yaml") == {"a": 1}


def test_glob_without_magic_still_requires_the_file(tmp_path):
    write(tmp_path, {"main.yaml": "#+include missing.yaml\n"})
    with pytest.raises(mf.MiniFormatError, match="cannot include 'missing.yaml'"):
        load_file(tmp_path / "main.yaml")


def test_glob_takes_the_indent_of_the_pragma(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "servers:\n  - z\n  #+include s/*.yaml\nplugins:\n  #+include p/*.yaml\n",
            "s/a.yaml": "- a\n- b: 1\n",
            "s/b.yaml": "- c\n",
            "p/x.yaml": "x: 1\n",
            "p/y.yaml": "y:\n  - 2\n",
        },
    )
    assert load_file(tmp_path / "main.yaml") == {
        "servers": ["z", "a", {"b": 1}, "c"],
        "plugins": {"x": 1, "y": [2]},
    }


def test_glob_skips_directories_and_dotfiles(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "#+include d/*\n",
            "d/a.yaml": "a: 1\n",
            "d/.hidden.yaml": "h: 2\n",
            "d/sub/inner.yaml": "i: 3\n",
        },
    )
    assert load_file(tmp_path / "main.yaml") == {"a": 1}


def test_glob_question_mark_and_character_classes(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "#+include f?.yaml\n#+include g[12].yaml\n",
            "f1.yaml": "f1: 1\n",
            "f22.yaml": "f22: 1\n",
            "g1.yaml": "g1: 1\n",
            "g2.yaml": "g2: 1\n",
            "g3.yaml": "g3: 1\n",
        },
    )
    assert list(load_file(tmp_path / "main.yaml")) == ["f1", "g1", "g2"]


def test_glob_duplicate_key_names_the_second_file(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "#+include d/*.yaml\n",
            "d/a.yaml": "k: 1\n",
            "d/b.yaml": "x: 1\nk: 2\n",
        },
    )
    with pytest.raises(mf.MiniFormatError, match="duplicate") as e:
        load_file(tmp_path / "main.yaml")
    assert e.value.file.endswith("b.yaml") and e.value.line == 2


def test_glob_error_inside_one_file_names_that_file(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "#+include d/*.yaml\n",
            "d/a.yaml": "a: 1\n",
            "d/b.yaml": "b: &anchor 2\n",
        },
    )
    with pytest.raises(mf.MiniFormatError, match="anchors") as e:
        load_file(tmp_path / "main.yaml")
    assert e.value.file.endswith("b.yaml") and e.value.line == 1


def test_glob_unreadable_match_is_an_error_naming_it(tmp_path):
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "bin.yaml").write_bytes(b"a: \xff\n")
    write(tmp_path, {"main.yaml": "#+include d/*.yaml\n"})
    with pytest.raises(mf.MiniFormatError, match=r"cannot include '.*bin\.yaml'"):
        load_file(tmp_path / "main.yaml")


def test_glob_inside_an_included_file_is_relative_to_that_file(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "#+include sub/entry.yaml\n",
            "sub/entry.yaml": "e: 1\n#+include parts/*.yaml\n",
            "sub/parts/p1.yaml": "p1: 1\n",
            "sub/parts/p2.yaml": "p2: 2\n",
            "parts/wrong.yaml": "wrong: 1\n",
        },
    )
    assert list(load_file(tmp_path / "main.yaml")) == ["e", "p1", "p2"]


def test_glob_characters_in_the_base_directory_are_not_magic(tmp_path):
    odd = tmp_path / "we[ir]d*dir"
    write(odd, {"main.yaml": "#+include c/*.yaml\n", "c/a.yaml": "a: 1\n"})
    assert load_file(odd / "main.yaml") == {"a": 1}
    assert mf.loads("#+include c/*.yaml\n", base=str(odd)) == {"a": 1}


def test_glob_works_with_loads_and_base(tmp_path):
    write(tmp_path, {"c/a.yaml": "a: 1\n", "c/b.yaml": "b: 2\n"})
    assert mf.loads("#+include c/*.yaml\n", base=str(tmp_path)) == {"a": 1, "b": 2}


def test_glob_without_a_base_directory_is_an_error():
    with pytest.raises(mf.MiniFormatError, match="base"):
        mf.loads("#+include c/*.yaml\n")


def test_glob_include_cap_counts_every_file(tmp_path):
    write(tmp_path, {"main.yaml": "#+include d/*.yaml\n"})
    d = tmp_path / "d"
    d.mkdir()
    for n in range(1001):
        (d / ("f%04d.yaml" % n)).write_text("k%d: 1\n" % n)
    with pytest.raises(mf.MiniFormatError, match="too many includes"):
        load_file(tmp_path / "main.yaml")


def test_file_with_a_glob_pragma_is_still_plain_yaml(tmp_path):
    text = "a: 1\n#+include conf.d/*.yaml\nb:\n  #+include more/*.yaml\n  c: 2\n"
    assert yaml.safe_load(text) == {"a": 1, "b": {"c": 2}}


def test_double_star_matches_any_depth_including_none(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "#+include c/**/*.yaml\n",
            "c/top.yaml": "top: 1\n",
            "c/a/mid.yaml": "mid: 2\n",
            "c/a/b/deep.yaml": "deep: 3\n",
            "c/a/skip.txt": "no: 1\n",
            "c/.hidden/h.yaml": "h: 1\n",
        },
    )
    d = load_file(tmp_path / "main.yaml")
    # c/a/b/deep.yaml < c/a/mid.yaml < c/top.yaml (full path string order)
    assert list(d) == ["deep", "mid", "top"]


def test_double_star_order_is_by_full_path_string(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "#+include c/**/*.yaml\n",
            "c/a.yaml": "a: 1\n",
            "c/a/x.yaml": "ax: 1\n",
            "c/b.yaml": "b: 1\n",
            "c/a/z/y.yaml": "azy: 1\n",
        },
    )
    # '.' sorts before '/', so c/a.yaml < c/a/x.yaml < c/a/z/y.yaml < c/b.yaml
    assert list(load_file(tmp_path / "main.yaml")) == ["a", "ax", "azy", "b"]


def test_plain_star_does_not_descend(tmp_path):
    write(
        tmp_path,
        {
            "main.yaml": "#+include c/*.yaml\n",
            "c/a.yaml": "a: 1\n",
            "c/s/b.yaml": "b: 1\n",
        },
    )
    assert load_file(tmp_path / "main.yaml") == {"a": 1}


def test_flatten_expands_includes(tmp_path):
    from miniformat.mfdumper import flatten

    write(tmp_path, {"a.yaml": "x: 1\n#+include b.yaml\n", "b.yaml": "y: 2\n"})
    text = (tmp_path / "a.yaml").read_text()
    flat = flatten(text, str(tmp_path))
    assert flat == "x: 1\ny: 2\n"
    assert "#+include" not in flat
    assert mf.loads(flat) == mf.loads(text, str(tmp_path))
