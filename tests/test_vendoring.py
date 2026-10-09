"""The point of the layout: any subset of the package can be copied elsewhere.

mfloader.py alone                        reading
mfloader.py + mfdumper.py (in a package)   reading and writing
the whole miniformat/ directory        everything, incl. the command line
__init__.py is empty, so nothing couples the files except mfdumper -> mfloader
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import miniformat
from miniformat import mfloader

PKG = Path(miniformat.__file__).parent


def run_py(code, cwd, *argv):
    return subprocess.run(
        [sys.executable, "-I", "-c", code, *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def copy_files(dest, *names):
    dest.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy(PKG / name, dest / name)
    return dest


PRELUDE = "import sys; sys.path.insert(0, sys.argv[1]); "


# -- mfloader.py on its own ------------------------------------------------------


def test_loader_alone_as_top_level_module(tmp_path):
    shutil.copy(PKG / "mfloader.py", tmp_path / "mini.py")
    code = PRELUDE + "import mini; print(mini.loads('a: 1\\nb:\\n  - x\\n'))"
    r = run_py(code, tmp_path, str(tmp_path))
    assert r.returncode == 0 and "{'a': '1', 'b': ['x']}" in r.stdout, r.stderr


def test_loader_alone_inside_someone_elses_package(tmp_path):
    pkg = tmp_path / "myapp" / "_vendor"
    copy_files(pkg)
    (tmp_path / "myapp" / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    shutil.copy(PKG / "mfloader.py", pkg / "miniformat.py")
    code = PRELUDE + "from myapp._vendor import miniformat as m; print(m.loads('- x'))"
    r = run_py(code, tmp_path, str(tmp_path))
    assert r.returncode == 0 and "['x']" in r.stdout, r.stderr


def test_loader_imports_only_stdlib_modules():
    src = (PKG / "mfloader.py").read_text(encoding="utf-8")
    imports = [
        ln.split()[1] for ln in src.splitlines() if ln.startswith(("import ", "from "))
    ]
    assert sorted(imports) == ["glob", "json", "os", "re"]
    assert "from ." not in src and "import miniformat" not in src


def test_loader_has_no_import_time_side_effects(tmp_path):
    shutil.copy(PKG / "mfloader.py", tmp_path / "mini.py")
    code = (
        PRELUDE
        + "import mini; print(sorted(m for m in sys.modules if m.startswith('mini')))"
    )
    r = run_py(code, tmp_path, str(tmp_path))
    assert r.stdout.strip() == "['mini']", r.stderr


def test_loader_is_small():
    assert len((PKG / "mfloader.py").read_text().splitlines()) < 550


# -- the directory, in various states of completeness ------------------------------

LAYOUTS = {
    "whole directory": [
        "__init__.py",
        "__main__.py",
        "cli.py",
        "mfdumper.py",
        "mfloader.py",
    ],
    "no cli": ["__init__.py", "mfdumper.py", "mfloader.py"],
    "loader only": ["__init__.py", "mfloader.py"],
}


@pytest.mark.parametrize("layout", LAYOUTS)
def test_copied_directory_loader_works(tmp_path, layout):
    copy_files(tmp_path / "vend" / "mf", *LAYOUTS[layout])
    (tmp_path / "vend" / "__init__.py").write_text("")
    code = (
        PRELUDE
        + "from vend.mf import mfloader; print(mfloader.loads('a:\\n  - x\\n  - y: z\\n'))"
    )
    r = run_py(code, tmp_path, str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "{'a': ['x', {'y': 'z'}]}" in r.stdout


@pytest.mark.parametrize("layout", ["whole directory", "no cli"])
def test_copied_directory_with_dumper_works(tmp_path, layout):
    copy_files(tmp_path / "vend" / "mf", *LAYOUTS[layout])
    (tmp_path / "vend" / "__init__.py").write_text("")
    code = (
        PRELUDE
        + "from vend.mf import mfdumper, mfloader; "
        + "print(repr(mfdumper.dumps(mfloader.loads('a: [] '))))"
    )
    r = run_py(code, tmp_path, str(tmp_path))
    assert r.returncode == 0 and "'a: []\\n'" in r.stdout, r.stderr


def test_copied_whole_directory_still_has_a_command_line(tmp_path):
    copy_files(tmp_path / "mf", *LAYOUTS["whole directory"])
    (tmp_path / "in.yaml").write_text("a: 1\n")
    r = subprocess.run(
        [sys.executable, "-m", "mf", str(tmp_path / "in.yaml")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0 and '"a": "1"' in r.stdout, r.stderr


def test_dumper_without_loader_fails_clearly(tmp_path):
    copy_files(tmp_path / "mf", "__init__.py", "mfdumper.py")
    code = PRELUDE + "from mf import mfdumper"
    r = run_py(code, tmp_path, str(tmp_path))
    assert r.returncode != 0 and "mf.mfloader" in r.stderr


# -- how the files depend on each other ---------------------------------------------


def test_init_is_nothing_but_a_docstring():
    import ast

    body = ast.parse((PKG / "__init__.py").read_text()).body
    assert len(body) == 1 and isinstance(body[0], ast.Expr)  # just the docstring


def test_dumper_depends_only_on_loader():
    src = (PKG / "mfdumper.py").read_text(encoding="utf-8")
    assert "from .mfloader import" in src
    assert [ln for ln in src.splitlines() if ln.startswith("import ")] == []


def test_cli_depends_only_on_loader_and_dumper():
    src = (PKG / "cli.py").read_text(encoding="utf-8")
    assert "from .mfdumper import" in src and "from .mfloader import" in src
    assert "from . import" not in src


def test_version_is_single_sourced_in_the_loader():
    assert mfloader.__version__
    text = (PKG / "mfloader.py").read_text()
    assert f'__version__ = "{mfloader.__version__}"' in text
    assert "__version__" not in (PKG / "mfdumper.py").read_text()


def test_public_names():
    for name in ["loads", "load", "MiniFormatError"]:
        assert hasattr(mfloader, name)
    assert set(mfloader.__all__) == {"loads", "load", "MiniFormatError"}
    from miniformat import mfdumper

    assert set(mfdumper.__all__) == {"dumps", "dump", "flatten"}
