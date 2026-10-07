import json
import subprocess
import sys

import pytest

from miniformat.cli import main


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "miniformat", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@pytest.fixture
def good(tmp_path):
    p = tmp_path / "good.yaml"
    p.write_text("# c\nb: 2 # n\na:\n  - x\n  - é\n", encoding="utf-8")
    return str(p)


def test_prints_json(good):
    r = run(good)
    assert r.returncode == 0 and r.stderr == ""
    assert json.loads(r.stdout) == {"b": "2", "a": ["x", "é"]}
    assert "é" in r.stdout  # not escaped


def test_fmt_prints_canonical_text(good):
    r = run("--fmt", good)
    assert r.returncode == 0
    assert r.stdout == "b: 2\na:\n  - x\n  - é\n"
    r2 = run(good, "--fmt")  # flag position doesn't matter
    assert r2.stdout == r.stdout


def test_error_goes_to_stderr_with_path_and_line(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("a: 1\nb: [x]\n", encoding="utf-8")
    r = run(str(p))
    assert r.returncode == 1 and r.stdout == ""
    assert "bad.yaml: line 2:" in r.stderr and "b: [x]" in r.stderr


def test_missing_file(tmp_path):
    r = run(str(tmp_path / "nope.yaml"))
    assert r.returncode == 1 and "nope.yaml" in r.stderr and "Traceback" not in r.stderr


@pytest.mark.parametrize("args", [[], ["a", "b"], ["--help"], ["-x"]])
def test_usage_errors(args):
    r = run(*args)
    assert r.returncode == 2 and "usage" in r.stderr


def test_main_is_callable_in_process(good, capsys):
    assert main([good]) == 0
    assert json.loads(capsys.readouterr().out)["b"] == "2"
