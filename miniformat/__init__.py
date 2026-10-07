"""miniformat -- a strict, tiny subset of YAML where every scalar is a string.

``loader.py`` is self-contained and meant to be vendored on its own;
``dumper.py`` is the optional writer.
"""

from .dumper import dump, dumps
from .loader import MiniFormatError, __version__, get, load, loads

__all__ = ["loads", "load", "dumps", "dump", "get", "MiniFormatError", "__version__"]
