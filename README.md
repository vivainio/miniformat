# miniformat

A tiny, strict config format with YAML syntax. **The promise: any YAML parser
can parse a miniformat file**, so editors, highlighting and existing tooling
keep working. That is all it promises about YAML; what the file *means* is up
to miniformat (see below). The loader is a single stdlib-only Python file you
can copy into your project.

Two things are miniformat's own: **every scalar is a string** (`no`, `8080` and
`1.10` stay exactly as written, no Norway problem), and `#+include` pulls in
other files.

## Reading values

Given this file:

```yaml
# app.yaml
name: my-app
db:
  port: 5432
debug: yes
servers:
  - host: a.example.com
```

`loads` returns what `json.load` would: nested dicts, lists and strings, with
the one difference that every scalar is a string. Nothing is converted:

```python
from miniformat import mfloader

cfg = mfloader.loads(open("app.yaml").read())
# {'name': 'my-app', 'db': {'port': '5432'}, 'debug': 'yes',
#  'servers': [{'host': 'a.example.com'}]}

cfg["servers"][0]["host"]  # 'a.example.com'
cfg["db"].get("timeout", "30")  # a default, with the plain dict method
int(cfg["db"]["port"])  # 5432: you convert the string where you use it
```

### Typed values with pydantic

To get real `int`s and `bool`s without converting by hand, validate the result
against a [pydantic](https://docs.pydantic.dev/) model. Its default (lax) mode
coerces strings: `"5432"` becomes `5432`, `"yes"` becomes `True`. pydantic is
not a dependency of miniformat; this is just a recipe.

```python
from pydantic import BaseModel, ConfigDict
from miniformat import mfloader


class Db(BaseModel):
    port: int


class Server(BaseModel):
    host: str


class App(BaseModel):
    model_config = ConfigDict(extra="forbid")  # reject unknown keys

    name: str
    db: Db
    debug: bool = False
    servers: list[Server]


app = App.model_validate(mfloader.loads(open("app.yaml").read()))
app.db.port  # 5432 (an int)
app.debug  # True
```

Plain `@dataclass` types work too, via `pydantic.TypeAdapter(MyDataclass).validate_python(cfg)`.

## Why

- **YAML is the only reasonably readable syntax that also nests well.** JSON is
  noisy (quotes, commas, no comments), INI is flat, and TOML turns into a
  verbose mess as soon as the data nests (repeated `[a.b.c]` headers,
  `[[arrays of tables]]`); even XML is easier to read at depth. Config files
  are for people to read and edit, and YAML is the one that stays pleasant at
  depth.
- **But depending on PyYAML is annoying**, especially when it would be your
  only dependency: a package to install, pin and audit just to read one file.
  The loader here is a single stdlib-only file you can copy into your project.
- **And YAML itself has sharp edges**: implicit typing (`no` becomes `False`,
  `1.10` a float), anchors, tags, several ways to write the same thing.
  miniformat keeps the syntax people like and drops those.

Because the files stay parseable as YAML, you don't lose the tooling: editors,
highlighting and linters keep working, and you can still read the files with a
real YAML parser when you want to.

## Install, or just copy the files

```
pip install miniformat
```

Python 3.10 or newer. `miniformat/__init__.py` is empty on purpose: import the
parts you use, which also means you can copy any of them on their own.

| File | Purpose |
|---|---|
| `miniformat/mfloader.py` | The loader: `loads`, `load`, `MiniFormatError`. Stdlib only, no relative imports. **This is the file to vendor.** |
| `miniformat/mfdumper.py` | Optional canonical writer: `dumps`, `dump`. Imports `.mfloader`. |
| `miniformat/cli.py`, `__main__.py` | The `miniformat` command. |

**Vendoring**, from smallest to largest:

- **One file.** Copy `mfloader.py` to your project (`import mfloader`). It needs
  nothing else.
- **The directory, trimmed to what you use.** Copy `miniformat/` into your app
  and delete what you don't need. `__init__.py` plus `mfloader.py` is a complete
  reader; add `mfdumper.py` for writing, `cli.py` and `__main__.py` for the
  command.
- **The whole directory.** Copy `miniformat/` as it is.

```python
from myapp._vendor.miniformat import mfloader  # or: from miniformat import mfloader
```

`tests/test_vendoring.py` checks each of these layouts. The version is in
`mfloader.py` (`mfloader.__version__`), so the vendored file carries it.

```
$ miniformat app.yaml          # print as JSON
$ miniformat --fmt app.yaml    # print the canonical form (comments are dropped)
```

## File names

Use **`.yml` or `.yaml`**, like any other YAML file. There is no special
extension, on purpose: since any YAML parser can read the files, editors,
syntax highlighting, schema tools and CI linters pick them up as they are.
`#+include` paths are written with the real file names too
(`#+include db.yaml`).

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

Rejected with a line-numbered error: anchors, aliases, `!!` tags, tags on keys, `>` folded scalars,
chomp indicators, single quotes, flow syntax other than `{}`/`[]`, duplicate
keys, multiple documents, `a: b: c`, multi-line plain scalars.

```
$ miniformat bad.yaml
bad.yaml: line 1: ': ' inside a plain value; quote it with double quotes
    a: b: c
```

### Syntax by example

Each pair shows a document and what `mfloader.loads` returns for it. Every scalar
is a string.

**Scalars are never converted:**

```yaml
port: 8080
debug: yes
version: 1.10
nothing: null
```

```python
{"port": "8080", "debug": "yes", "version": "1.10", "nothing": "null"}
```

**Plain and quoted strings.** `:` and `#` are fine inside a plain value unless
followed by a space (colon) or preceded by one (hash); quote anything else
awkward. Quotes are double only, with JSON escapes:

```yaml
plain: hello world
url: http://example.com:8080/a#frag
quoted: "a: b"
hash: "# not a comment"
bang: "!not-a-tag"
escapes: "tab\there\nnew line, \u00e9"
```

```python
{
    "plain": "hello world",
    "url": "http://example.com:8080/a#frag",
    "quoted": "a: b",
    "hash": "# not a comment",
    "bang": "!not-a-tag",
    "escapes": "tab\there\nnew line, \u00e9",
}
```

**Empty values:**

```yaml
a:
b: ""
c: {}
d: []
```

```python
{"a": "", "b": "", "c": {}, "d": []}
```

**Comments** are dropped (` #` starts one, so `a#b` is just text):

```yaml
name: my-app    # a comment
```

```python
{"name": "my-app"}
```

**Maps and lists nest by indentation**, and a list is always indented below its key:

```yaml
db:
  host: localhost
  ports:
    - "5432"
    - "5433"
```

```python
{"db": {"host": "localhost", "ports": ["5432", "5433"]}}
```

**Lists of maps** (the first key may follow the dash):

```yaml
servers:
  - name: a
    ip: "1.2.3.4"
  - name: b
    tags:
      - web
      - prod
```

```python
{
    "servers": [
        {"name": "a", "ip": "1.2.3.4"},
        {"name": "b", "tags": ["web", "prod"]},
    ]
}
```

**Lists of lists** use a bare `-` with the inner list indented below it
(`- - a` is not supported):

```yaml
-
  - a
  - b
-
  - c
```

```python
[["a", "b"], ["c"]]
```

**Literal blocks** (`|`) keep line breaks and extra indentation, and end with
one newline:

```yaml
note: |
  first line
    indented
  last line
next: x
```

```python
{"note": "first line\n  indented\nlast line\n", "next": "x"}
```

They also work as list items:

```yaml
items:
  - |
    one
    two
  - three
```

```python
{"items": ["one\ntwo\n", "three"]}
```

**Tags** become one-key maps (details [below](#tags)):

```yaml
queue: !Ref MyQueue
name: !Sub "${Env}-queue"
choice: !If
  - HasQueue
  - !Ref Q
```

```python
{
    "queue": {"!Ref": "MyQueue"},
    "name": {"!Sub": "${Env}-queue"},
    "choice": {"!If": ["HasQueue", {"!Ref": "Q"}]},
}
```

### Tags

A value may start with a YAML tag: `!Name`, a space, then the value. It loads as
a one-key map, `{"!Name": value}`. This keeps tag-heavy files such as AWS
CloudFormation templates readable without giving up "every scalar is a string":

```yaml
queue: !Ref MyQueue
arn: !GetAtt Q.Arn
name: !Sub "${Env}-queue"
policy: !Sub |
  line ${A}
choice: !If
  - HasQueue
  - !Ref Q
```

```python
{
    "queue": {"!Ref": "MyQueue"},
    "arn": {"!GetAtt": "Q.Arn"},
    "name": {"!Sub": "${Env}-queue"},
    "policy": {"!Sub": "line ${A}\n"},
    "choice": {"!If": ["HasQueue", {"!Ref": "Q"}]},
}
```

- What follows the tag is any value: a plain or quoted scalar, a `|` block, `{}`
  or `[]`, or a nested map or list on the next lines. `key: !Tag` with nothing
  after it is `{"!Tag": ""}`.
- One tag per value, and none on keys or at the document root. `!!str`-style
  tags and flow collections (`!Join [a, b]`) are errors.
- A one-key map whose key looks like a tag is the same thing: `"!Ref": x`
  (quoted key) and `!Ref x` both load as `{"!Ref": "x"}`. The dumper writes
  such a map as a tag, so `--fmt` normalizes to the tag form.
- Plain YAML parsers see a tagged value. PyYAML's `safe_load` refuses unknown
  tags, so register a constructor that returns `{tag: value}`; the tests do it
  with `add_multi_constructor("!", ...)` to check the structure still matches.

## Writing

```python
from miniformat import mfdumper

text = mfdumper.dumps({"name": "x", "ports": ["80", "443"]})
```

Only `str`, `dict` (string keys) and `list`/`tuple` can be written; convert
numbers and bools with `str()` first. Output is deterministic and
`loads(dumps(x)) == x`. Lone surrogates can't be written (`ValueError`).

## Pragmas and includes

`#+` immediately followed by a character (no space) is **reserved**: a line of
its own that starts that way is a *pragma*. To a YAML parser it is just a
comment; miniformat gives it a meaning. Today there is one pragma:

### `#+include path`

The line is replaced by the text of that file, **indented to the column of the
`#+include` line**, so the same file can fill a whole document, a map, or a
list:

```yaml
# app.yaml
name: my-app
db:
  #+include db.yaml
servers:
  - a
  #+include more-servers.yaml
plugins:
  # every plugin file, in sorted order (a comment goes on its own line)
  #+include conf.d/*.yaml
```

- The path is the rest of the line (no trailing comment). Paths are relative
  to the including file, so nested includes work. `load(f)` uses the file's
  directory; `loads(text, base=dir)` is needed to use includes with a string
  (otherwise `#+include` is an error).
- **Globs:** a path containing `*`, `?` or `[` includes every matching file
  (not directories, not dotfiles), sorted by path (plain string order, so
  `10-x.yaml` comes before `2-y.yaml`). Each file is placed at the pragma's
  indent, one after the other. Matching nothing is fine, so an empty
  `conf.d/` works. `**` matches any depth of directories, so
  `conf.d/**/*.yaml` also picks up files in subdirectories.
- It is plain text substitution: duplicate keys are errors, a list can't be
  included into a map, and there is no overriding or merging.
- Included files are trusted input: there is no sandboxing of paths.
- Errors name the right file and line, e.g. `db.yaml: line 3: duplicate key 'a'`.
- A plain YAML parser ignores the line, so it sees the file without the
  included parts.

### The reserved `#+` namespace

- **Unknown or malformed pragmas are errors**, with a line number: `#+inlcude
  x.yaml` (a typo), `#+Include x.yaml` (names are lowercase), `#+include`
  (no path). A typo can't silently drop part of your config, and an older
  loader that meets a newer pragma fails instead of misreading the file.
- **`#+` followed by a space is still free.** `#+ like this`, a bare `#+`, and
  every other comment (`# text`, `#TODO`, `#include <x.h>`) are ordinary
  comments. Only `#+x...` is reserved.
- A pragma must be on a line of its own. `a: 1 #+include x`, and anything
  inside a quoted string or a `|` block, is ordinary text.

## Future additions

miniformat reserves the right to add more pragmas like `#+include`: they don't
break YAML syntax (any YAML parser can still parse the file) but do change
what a file means to miniformat. They are always `#+name`, never new syntax a
YAML parser would reject. New ones will be listed in this README and shipped
with fixtures in `tests/cases`.

## What "YAML-compatible" means

The promise is about syntax: any YAML parser can parse a miniformat file.
Meaning is not promised: a YAML parser types scalars its own way (`no`
becomes `False`, `8080` an int, `key:` `None`), and ignores `#+` pragmas. For
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
