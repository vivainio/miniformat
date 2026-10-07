"""Command line: ``miniformat FILE`` prints JSON, ``miniformat --fmt FILE``
prints the canonical form (comments are dropped)."""

import json
import sys

from .mfdumper import dumps
from .mfloader import MiniFormatError, load

USAGE = "usage: miniformat [--fmt] FILE      (prints JSON, or the canonical text with --fmt)"


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    fmt = "--fmt" in args
    args = [a for a in args if a != "--fmt"]
    if len(args) != 1 or args[0].startswith("-"):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        with open(args[0], encoding="utf-8") as f:
            data = load(f)
    except OSError as e:
        print("miniformat: %s" % e, file=sys.stderr)
        return 1
    except MiniFormatError as e:
        print(e if e.file else "%s: %s" % (args[0], e), file=sys.stderr)
        return 1
    if fmt:
        sys.stdout.write(dumps(data))
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
