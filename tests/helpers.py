"""Shared helpers: a PyYAML loader that keeps scalars as strings, and random
document generators for the fuzz tests."""

import random
import re

import yaml


def _tagged(loader, suffix, node):
    """'!Name value' -> {"!Name": value}, the way miniformat reads tags."""
    if isinstance(node, yaml.ScalarNode):
        plain = node.style is None  # only plain scalars are typed by their text
        tag = loader.resolve(yaml.ScalarNode, node.value, (plain, not plain))
        value = loader.construct_object(
            yaml.ScalarNode(tag, node.value, node.start_mark, node.end_mark, node.style)
        )
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {"!" + suffix: value}


class TagLoader(yaml.SafeLoader):
    """PyYAML that reads '!Name value' as {"!Name": value}."""


TagLoader.add_multi_constructor("!", _tagged)


class TypedLoader(TagLoader):
    """PyYAML told to type plain scalars the way miniformat does: JSON's
    true / false / null / numbers (64-bit ints, finite floats), nothing else
    (no yes/no, ~, 0x1F, 010, 1_000 ...).  Keys always stay strings."""

    yaml_implicit_resolvers = {}

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            self.flatten_mapping(node)
        out = {}
        for key_node, value_node in node.value:
            if isinstance(key_node, yaml.ScalarNode):
                key = self.construct_scalar(key_node)
            else:
                key = self.construct_object(key_node, deep=True)
            out[key] = self.construct_object(value_node, deep=deep)
        return out


_INT = r"-?(?:0|[1-9][0-9]*)"
_FLOAT = _INT + r"(?:\.[0-9]+(?:[eE][+-]?[0-9]+)?|[eE][+-]?[0-9]+)"
_DIGITS = list("-0123456789")
for _tag, _re, _first in [
    ("bool", r"(?:true|false)\Z", list("tf")),
    ("null", r"null\Z", ["n"]),
    ("int", _INT + r"\Z", _DIGITS),
    ("float", _FLOAT + r"\Z", _DIGITS),
]:
    TypedLoader.add_implicit_resolver(
        "tag:yaml.org,2002:" + _tag, re.compile("^" + _re), _first
    )


def _num(convert):
    def construct(loader, node):
        text = loader.construct_scalar(node)
        v = convert(text)
        if isinstance(v, int) and not -(2**63) <= v < 2**63:
            return text
        if isinstance(v, float) and v - v != 0:
            return text
        return v

    return construct


TypedLoader.add_constructor("tag:yaml.org,2002:int", _num(int))
TypedLoader.add_constructor("tag:yaml.org,2002:float", _num(float))
TypedLoader.add_constructor(
    "tag:yaml.org,2002:bool", lambda ld, n: ld.construct_scalar(n) == "true"
)
TypedLoader.add_constructor("tag:yaml.org,2002:null", lambda ld, n: None)


def typedload(text):
    return yaml.load(text, Loader=TypedLoader)


def same(a, b):
    """Equal including types (1 is not True, 1 is not 1.0) and key order."""
    return repr(a) == repr(b)


ALPHABET = list("abc XYZ019:-#?,[]{}&*!|>'\"%@`\\/\t.~") + [
    "\n",
    "é",
    " ",
    "\x85",
    "\x7f",
    "\U0001f600",
    "\x00",
    "﻿",
    "\xa0",
]
TRICKY = [
    "",
    " ",
    "no",
    "null",
    "1.10",
    "80",
    "-5",
    "true",
    "false",
    "1e3",
    "9223372036854775808",
    "010",
    "-0",
    "Infinity",
    "- x",
    "a: b",
    "a #b",
    "#a",
    "a:",
    ":",
    "-",
    "?",
    "{}",
    "[]",
    "---",
    "...",
    "x\n",
    "x\ny\n",
    "\nx\n",
    " x\n",
    "x\n\n",
    "x \n y\n",
    "a\tb",
    "\ta",
    "a\\b",
    '"q"',
    "'",
    "%x",
    "@x",
    "a\r\nb",
    "a b",
    "  ",
    "x\n  \ny\n",
    "|",
    "|\n",
    ">",
    "&a",
    "*a",
    "!t",
    "<<",
    "a,b",
    "[a]",
    "{a}",
    "x\n\ty\n",
    "\n\n",
    "a\n\nb\n",
    "# c\n",
    "- a\n",
    "k: v\n",
    "---\n",
    "﻿x",
    "x﻿",
]


def rand_str(r):
    if r.random() < 0.3:
        return r.choice(TRICKY)
    return "".join(r.choice(ALPHABET) for _ in range(r.randint(0, 8)))


def rand_scalar(r):
    k = r.random()
    if k < 0.7:
        return rand_str(r)
    return r.choice(
        [
            True,
            False,
            None,
            0,
            1,
            -7,
            80,
            2**63 - 1,
            -(2**63),
            1.5,
            -0.25,
            1e22,
            1e-7,
            5.0,
        ]
    )


def rand_obj(r, depth=0):
    k = r.random()
    if depth > 3 or k < 0.45:
        return rand_scalar(r)
    if k < 0.75:
        return {rand_str(r): rand_obj(r, depth + 1) for _ in range(r.randint(0, 4))}
    return [rand_obj(r, depth + 1) for _ in range(r.randint(0, 4))]


def rand_root(r):
    while True:
        o = rand_obj(r)
        if isinstance(o, (dict, list)):
            return o


LINE_BITS = [
    "a",
    "b c",
    "k: v",
    "k:",
    "- x",
    "- k: v",
    "-",
    "|",
    "k: |",
    '"q"',
    'k: "v"',
    "# c",
    "",
    "{}",
    "[]",
    "k: {}",
    "- []",
    "x: y # c",
    "- &a b",
    "k: [1]",
    'k: ["a", "b"]',
    'k: ["a","b"]',
    '- {"k": "v"}',
    'k: [{"a": ["b", "c"]}, []]',
    'k: ["a: b", "#c"]',
    'k: ["\\u00e9", "\\/"]',
    'k: ["a"] # c',
    'k: ["a", 1]',
    'k: ["\\ud83d\\ude00"]',
    'k: {"a": "1", "a": "2"}',
    "k: 'q'",
    "\tk: v",
    "k: v: w",
    "---",
    "- - a",
    "  text",
    "k: |",
    "k:   # c",
    "- |",
    "- # c",
    '"k": v',
    '- "k": v',
    'k: "a #b"',
    "k: a\tb",
]


def rand_text(r):
    lines = []
    for _ in range(r.randint(1, 8)):
        lines.append(" " * r.choice([0, 0, 2, 2, 4, 6, 1, 3]) + r.choice(LINE_BITS))
    return "\n".join(lines) + "\n"


def mutate(r, text):
    """Randomly damage a valid document."""
    chars = list(text)
    for _ in range(r.randint(1, 4)):
        op = r.random()
        pos = r.randrange(len(chars) + 1)
        if op < 0.4 and chars:
            del chars[min(pos, len(chars) - 1)]
        elif op < 0.8:
            chars.insert(pos, r.choice(ALPHABET + [" ", " ", "\n", "\n", "-", ":"]))
        elif chars:
            chars[min(pos, len(chars) - 1)] = r.choice(ALPHABET)
    return "".join(chars)


def rng(seed):
    return random.Random(seed)
