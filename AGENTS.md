# Agent Instructions

Guidelines for AI agents working on this codebase.

## What this is

`miniformat` is a small, strict config format with YAML syntax: every scalar is a string, and `#include` pulls in other files. Two rules shape every change:

1. **Everything the loader accepts must parse as YAML.** That is the one promise made to users (`#include` is just a comment to a YAML parser). Matching YAML's *meaning* is not promised, but without includes the PyYAML cross-check in the tests keeps the structure identical, so a mismatch there is worth a look.
2. **`miniformat/loader.py` must stay a single stdlib-only file** (`json`, `re` only; no relative imports, no CLI). People vendor it by copying that one file. Don't make it depend on the dumper, the CLI or `__init__`.

`dumper.py` is the optional writer and depends only on `loader.py`. `cli.py` is the command line.

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
- `test_fuzz.py` cross-checks against PyYAML with implicit typing disabled. A fuzz failure is usually a real YAML-compatibility bug; fix the loader (make it stricter) rather than the test.

## Releases

Create a GitHub release tagged `vX.Y.Z`; the publish workflow sets `__version__` in `miniformat/loader.py` from the tag and publishes to PyPI. The version lives in `loader.py` so the vendored file carries it.
