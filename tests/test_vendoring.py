"""The point of the package layout: loader.py works as a lone file."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import miniformat

PKG = Path(miniformat.__file__).parent


def run_py(code, cwd, *argv):
    return subprocess.run(
        [sys.executable, "-I", "-c", code, *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_loader_alone_as_top_level_module(tmp_path):
    shutil.copy(PKG / "loader.py", tmp_path / "mini.py")
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); import mini; "
        "print(mini.loads('a: 1')['a'], mini.get(mini.loads('p: 80'), 'p', int))"
    )
    r = run_py(code, tmp_path, str(tmp_path))
    assert r.returncode == 0 and r.stdout.split() == ["1", "80"], r.stderr


def test_loader_alone_inside_someone_elses_package(tmp_path):
    pkg = tmp_path / "myapp" / "_vendor"
    pkg.mkdir(parents=True)
    (tmp_path / "myapp" / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    shutil.copy(PKG / "loader.py", pkg / "miniformat.py")
    code = "import sys; sys.path.insert(0, sys.argv[1]); from myapp._vendor import miniformat as m; print(m.loads('- x'))"
    r = run_py(code, tmp_path, str(tmp_path))
    assert r.returncode == 0 and "['x']" in r.stdout, r.stderr


def test_loader_imports_only_stdlib_modules():
    src = (PKG / "loader.py").read_text(encoding="utf-8")
    imports = [
        ln.split()[1] for ln in src.splitlines() if ln.startswith(("import ", "from "))
    ]
    assert sorted(imports) == ["json", "os", "re"]
    assert "from ." not in src and "import miniformat" not in src


def test_loader_has_no_import_time_side_effects_beyond_regex_compilation(tmp_path):
    shutil.copy(PKG / "loader.py", tmp_path / "mini.py")
    code = "import sys; sys.path.insert(0, sys.argv[1]); import mini; print(sorted(m for m in sys.modules if m.startswith('mini')))"
    r = run_py(code, tmp_path, str(tmp_path))
    assert r.stdout.strip() == "['mini']", r.stderr


def test_dumper_works_as_a_sibling_of_the_vendored_loader(tmp_path):
    pkg = tmp_path / "vend"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    shutil.copy(PKG / "loader.py", pkg / "loader.py")
    shutil.copy(PKG / "dumper.py", pkg / "dumper.py")
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); from vend.dumper import dumps; from vend.loader import loads; "
        "print(repr(dumps(loads('a: [] '))))"
    )
    r = run_py(code, tmp_path, str(tmp_path))
    assert r.returncode == 0 and "'a: []\\n'" in r.stdout, r.stderr


def test_dumper_depends_only_on_loader():
    src = (PKG / "dumper.py").read_text(encoding="utf-8")
    assert "from .loader import" in src
    assert [ln for ln in src.splitlines() if ln.startswith("import ")] == []


def test_loader_is_small():
    assert len((PKG / "loader.py").read_text().splitlines()) < 500


def test_version_is_single_sourced():
    assert miniformat.__version__
    assert (
        f'__version__ = "{miniformat.__version__}"' in (PKG / "loader.py").read_text()
    )


@pytest.mark.skipif(sys.version_info < (3, 8), reason="n/a")
def test_public_api():
    assert set(miniformat.__all__) == {
        "loads",
        "load",
        "dumps",
        "dump",
        "get",
        "MiniFormatError",
        "__version__",
    }
    for name in miniformat.__all__:
        assert hasattr(miniformat, name)
