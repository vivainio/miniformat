# Agent Instructions

Guidelines for AI agents working on this codebase.

## What this is

`miniformat` is a small, strict config format with YAML syntax: plain scalars are typed like JSON (`true`, `false`, `null`, JSON numbers; everything else, and anything quoted, is a string), and `#+include` pulls in other files. Two rules shape every change:

1. **Everything the loader accepts must parse as YAML.** That is the one promise made to users (`#+include` is just a comment to a YAML parser). Matching YAML's *meaning* is not promised, but without includes the PyYAML cross-check in the tests (PyYAML with miniformat's typing rules plugged in) keeps the values identical, so a mismatch there is worth a look.
2. **`miniformat/mfloader.py` must stay a single stdlib-only file** (`json`, `os`, `re` only; no relative imports, no CLI). People vendor it by copying that one file.
3. **`miniformat/__init__.py` stays empty** (a docstring only), so any subset of the files can be copied elsewhere. `mfdumper.py` may import only `.mfloader`; `cli.py` may import only `.mfloader` and `.dumper`. `tests/test_vendoring.py` enforces all of this.

New features may add semantics (like `#+include` does) but must never make a file unparseable by a YAML parser. Add them as pragmas: `#+name args` on a line of its own. `#+` immediately followed by a non-space character is reserved for that, so unknown or malformed pragmas are errors; every other comment (including `#+` alone or `#+ text`, `#TODO`, `#include`) must stay a plain comment. Each new pragma needs a README entry, fixtures in `tests/cases`, and a check that a YAML parser still parses files that use it.

Users write `from miniformat import mfloader` / `from miniformat import mfdumper`.

## Checks

Run before committing:

```bash
ruff check .
ruff format .
pytest
```

Format is enforced by the pre-commit hook (`git config core.hooksPath .githooks`, needs `hookmaster`).

## Tests

- `tests/cases/valid/NAME.yaml` + `NAME.json`: documents and their expected trees. Write expected values by hand, never by running the loader.
- `tests/cases/invalid/NAME.yaml` + `NAME.err`: first line is the expected error line number (`-` for none), second is text the message must contain. These fixtures are language-neutral; keep them free of Python-specific expectations.
- When the loader's behaviour changes, add a fixture before touching the unit tests.
- `test_fuzz.py` cross-checks against PyYAML with implicit typing replaced by miniformat's rules (`TypedLoader` in `tests/helpers.py`). A fuzz failure is usually a real YAML-compatibility bug; fix the loader (make it stricter) rather than the test.

## Releases

Create a GitHub release tagged `vX.Y.Z`; the publish workflow sets `__version__` in `miniformat/mfloader.py` from the tag and publishes to PyPI. The version lives in `mfloader.py` so the vendored file carries it.
