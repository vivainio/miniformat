# miniformat

A strict, tiny subset of YAML for config files. **Every file it accepts is
also valid YAML**, so editors, highlighting and any YAML parser can still read
it. The loader is a single stdlib-only Python file you can copy into your project.

The one semantic difference: **every scalar is a string.** `no`, `8080` and
`1.10` stay exactly as written (no Norway problem). Convert on the consumer
side:

```python
import miniformat as mf

cfg = mf.loads(open("app.yaml").read())
port = mf.get(cfg, "db.port", int, default=5432)
debug = mf.get(cfg, "debug", bool, default=False)   # true/false/yes/no/on/off/1/0
host = mf.get(cfg, "servers.0.host")                # lists are indexed by number
```

## Files

| File | Purpose |
|---|---|
| `miniformat.py` | The loader (`loads`, `load`, `get`, `MiniFormatError`). Vendor just this. |
| `miniformat_dump.py` | Optional canonical writer (`dumps`, `dump`). Needs `miniformat.py`. |
| `test_miniformat.py` | Tests, including fuzzing against PyYAML (PyYAML needed for tests only). |

CLI: `python miniformat.py FILE` prints JSON; `python miniformat_dump.py FILE`
prints the canonical form (comments are dropped).

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
- Block maps and lists; indent with spaces (tabs are an error). A list under a
  key is indented below it, not at the key's column.
- Scalars are plain or double-quoted. Plain scalars are one line, may not
  start with `[ ] { } & * ! | > ' " % @ \` # ,` (or `- `, `? `, `: `), and may not contain
  `: `, ` #` or a tab. Quote them instead.
- Multi-line text uses `|` only (clip chomping).
- Root is a map or a list. Empty documents are an error.

Rejected with a line-numbered error: anchors, aliases, tags, `>` folded scalars,
chomp indicators, single quotes, flow syntax other than `{}`/`[]`, duplicate
keys, multiple documents, `a: b: c`, multi-line plain scalars.

```
$ python miniformat.py bad.yaml
bad.yaml: line 1: ': ' inside a plain value; quote it with double quotes
    a: b: c
```

## Writing

```python
from miniformat_dump import dumps
text = dumps({"name": "x", "ports": ["80", "443"]})
```

Only `str`, `dict` (string keys) and `list`/`tuple` can be written; convert
numbers and bools with `str()` first. Output is deterministic and
`loads(dumps(x)) == x`.

## Compatibility with YAML

The promise is about syntax, not types: a YAML parser reads the same
structure, but types them its own way (`no` becomes `False`, `8080` an int,
`key:` `None`). The tests check this against PyYAML with implicit typing
turned off, on thousands of random documents.

## License

MIT, see `LICENSE`.
