"""Language-neutral fixtures in tests/cases:

  valid/NAME.yaml + NAME.json   the document and its expected tree (all strings)
  invalid/NAME.yaml + NAME.err  first line: expected error line number ('-' for
                                none), second line: text the message must contain

A port in another language can run the same files.
"""

import json
from pathlib import Path

import pytest
import yaml

from helpers import same_shape, strload
from miniformat import mfloader as mf
from miniformat.mfdumper import dumps

CASES = Path(__file__).parent / "cases"
VALID = sorted(p.stem for p in (CASES / "valid").glob("*.yaml"))
INVALID = sorted(p.stem for p in (CASES / "invalid").glob("*.yaml"))


def read_valid(name):
    text = (CASES / "valid" / f"{name}.yaml").read_bytes().decode("utf-8")
    expected = json.loads((CASES / "valid" / f"{name}.json").read_text("utf-8"))
    return text, expected


def test_fixture_counts():
    assert len(VALID) >= 50 and len(INVALID) >= 60


@pytest.mark.parametrize("name", VALID)
def test_valid_loads_as_expected(name):
    text, expected = read_valid(name)
    got = mf.loads(text)
    assert got == expected
    assert json.dumps(got) == json.dumps(expected)  # key order too


@pytest.mark.parametrize("name", VALID)
def test_valid_is_valid_yaml_with_same_meaning(name):
    text, expected = read_valid(name)
    assert strload(text) == expected
    assert same_shape(expected, yaml.safe_load(text))


@pytest.mark.parametrize("name", VALID)
def test_valid_survives_the_dumper(name):
    _, expected = read_valid(name)
    out = dumps(expected)
    assert mf.loads(out) == expected
    assert strload(out) == expected
    assert dumps(mf.loads(out)) == out  # canonical form is a fixed point


@pytest.mark.parametrize("name", INVALID)
def test_invalid_is_rejected_with_line_and_reason(name):
    text = (CASES / "invalid" / f"{name}.yaml").read_text("utf-8")
    line, fragment = (
        (CASES / "invalid" / f"{name}.err").read_text("utf-8").splitlines()[:2]
    )
    with pytest.raises(mf.MiniFormatError) as e:
        mf.loads(text)
    assert e.value.line == (None if line == "-" else int(line)), str(e.value)
    assert fragment in str(e.value), str(e.value)
    assert isinstance(e.value, ValueError)
