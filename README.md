# miniformat

A tiny, strict config format with YAML syntax. **The promise: any YAML parser
can parse a miniformat file**, so editors, highlighting and existing tooling
keep working. That is all it promises about YAML; what the file *means* is up
to miniformat (see below). The loader is a single stdlib-only Python file you
can copy into your project.

Two things are miniformat's own: **every scalar is a string** (`no`, `8080` and
`1.10` stay exactly as written, no Norway problem), and `#include` pulls in
other files. Convert strings on the consumer side:

```python
import miniformat as mf

cfg = mf.loads(open("app.yaml").read())
port = mf.get(cfg, "db.port", int, default=5432)
debug = mf.get(cfg, "debug", bool, default=False)  # true/false/yes/no/on/off/1/0
host = mf.get(cfg, "servers.0.host")  # lists are indexed by number
```

## Install, or just copy the file

```
pip install miniformat
```

Python 3.10 or newer.

**Vendoring:** the loader is one stdlib-only file with no relative imports.
Copy [`miniformat/loader.py`](miniformat/loader.py) into your project under any
name and import it; it needs nothing else:

```python
from myapp import _vendor_miniformat as mf  # a copy of loader.py

cfg = mf.loads(text)
```

A test (`tests/test_vendoring.py`) keeps this true. The version is in the file
(`__version__`). If you also want the writer, copy `dumper.py` next to the
loader inside a package (it imports `.loader`).

| File | Purpose |
|---|---|
| `miniformat/loader.py` | The loader: `loads`, `load`, `get`, `MiniFormatError`. **Vendor this.** |
| `miniformat/dumper.py` | Optional canonical writer: `dumps`, `dump`. |
| `miniformat/cli.py` | The `miniformat` command. |
| `tests/` | Unit tests, language-neutral fixtures, fuzzing against PyYAML. |

`import miniformat` gives you everything above in one namespace.

```
$ miniformat app.yaml          # print as JSON
$ miniformat --fmt app.yaml    # print the canonical form (comments are dropped)
```

## The format

```yaml
---                       # optional
# comments
name: my-app
port: 8080                # a string: "8080"
quoted: "a: b\tc"         # double quotes, JSON escapes
tags:
  - web
  - prod
db:
  host: localhost
  note: |                 # literal block, one trailing newline
    multi-line
      text
servers:
  - name: a               # list of maps
    ip: "1.2.3.4"
  - name: b
    opts: {}              # {} and [] are the only flow syntax
empty:                    # loads as ""
```

Rules:
- Block maps and lists; indent with spaces. A list under a key is indented
  below it, not at the key's column.
- Tab characters are only allowed in comments and `|` blocks (use `\t` inside
  quotes); anywhere else they are an error.
- Scalars are plain or double-quoted. Plain scalars are one line, may not
  start with `[ ] { } & * ! | > ' " % @ \` # ,` (or `- `, `? `, `: `), and may not contain
  `: `, ` #` or a tab. Quote them instead. Only space and tab count as
  whitespace (a non-breaking space is an ordinary character).
- Multi-line text uses `|` only (clip chomping).
- Root is a map or a list. Empty documents are an error.

A `|` block that ends at the end of the file without a final newline has no
trailing newline either, exactly as in YAML.

Rejected with a line-numbered error: anchors, aliases, tags, `>` folded scalars,
chomp indicators, single quotes, flow syntax other than `{}`/`[]`, duplicate
keys, multiple documents, `a: b: c`, multi-line plain scalars.

```
$ miniformat bad.yaml
bad.yaml: line 1: ': ' inside a plain value; quote it with double quotes
    a: b: c
```

## Writing

```python
from miniformat import dumps

text = dumps({"name": "x", "ports": ["80", "443"]})
```

Only `str`, `dict` (string keys) and `list`/`tuple` can be written; convert
numbers and bools with `str()` first. Output is deterministic and
`loads(dumps(x)) == x`. Lone surrogates can't be written (`ValueError`).

## Includes

A line of its own that reads `#include path` is just a comment to any YAML
parser. Here it is replaced by the text of that file, **indented to the
column of the `#include` line**, so the same file can fill a whole document, a
map, or a list:

```yaml
# app.yaml
name: my-app
db:
  #include db.yaml        # db.yaml's entries become the children of db
servers:
  - a
  #include more-servers.yaml
```

- Paths are relative to the including file, so nested includes work.
  `load(f)` uses the file's directory; `loads(text, base=dir)` is needed to
  use includes with a string (otherwise `#include` is an error).
- It is plain text substitution: duplicate keys are errors, a list can't be
  included into a map, and there is no overriding or merging.
- Included files are trusted input: there is no sandboxing of paths.
- Errors name the right file and line, e.g. `db.yaml: line 3: duplicate key 'a'`.
- Only the exact form `#include path` on its own line counts. `# include x`
  (space after `#`), `#included`, a trailing `a: 1 #include x`, and anything
  inside a quoted string or a `|` block are ordinary text.
- A plain YAML parser ignores the line, so it sees the file without the
  included parts.

## What "YAML-compatible" means

The promise is about syntax: any YAML parser can parse a miniformat file.
Meaning is not promised: a YAML parser types scalars its own way (`no`
becomes `False`, `8080` an int, `key:` `None`), and ignores `#include`. For
documents without includes, the tests also check that PyYAML (with implicit
typing turned off) reads the same structure, on every fixture and on
hundreds of thousands of random and mutated documents. The fixtures in
`tests/cases` are plain files (document + expected JSON, or expected error
line and message), so ports to other languages can run the same suite.

## Development

```
uv run --group dev pytest
uv run --group dev ruff check . && uv run --group dev ruff format --check .
```

Releases: publish a GitHub release tagged `vX.Y.Z`; CI sets `__version__` from
the tag and publishes to PyPI.

## License

MIT, see `LICENSE`.
