"""Shared helpers: a PyYAML loader that keeps scalars as strings, and random
document generators for the fuzz tests."""

import random

import yaml


def _tagged(loader, suffix, node):
    """'!Name value' -> {"!Name": value}, the way miniformat reads tags."""
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {"!" + suffix: value}


class TagLoader(yaml.SafeLoader):
    """PyYAML that reads '!Name value' as {"!Name": value}."""


TagLoader.add_multi_constructor("!", _tagged)


class StrLoader(TagLoader):
    """PyYAML with implicit typing switched off: plain scalars stay str."""


StrLoader.yaml_implicit_resolvers = {}


def strload(text):
    return yaml.load(text, Loader=StrLoader)


def same_shape(ours, theirs):
    """Same nesting, key order and strings, ignoring YAML's scalar typing
    (no -> False, 1 -> int, empty -> None).  Where YAML kept a str it must
    equal ours."""
    if isinstance(ours, dict):
        return (
            isinstance(theirs, dict)
            and len(ours) == len(theirs)
            and all(
                same_shape(ok, tk) and same_shape(ov, tv)
                for (ok, ov), (tk, tv) in zip(ours.items(), theirs.items())
            )
        )
    if isinstance(ours, list):
        return (
            isinstance(theirs, list)
            and len(ours) == len(theirs)
            and all(same_shape(a, b) for a, b in zip(ours, theirs))
        )
    if isinstance(theirs, (dict, list)):
        return False
    return ours == theirs if isinstance(theirs, str) else True


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


def rand_obj(r, depth=0):
    k = r.random()
    if depth > 3 or k < 0.45:
        return rand_str(r)
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
