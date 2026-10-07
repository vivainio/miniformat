"""Randomised tests.  Seeds are fixed so failures reproduce; raise N to dig."""

import pytest

import miniformat as mf
from helpers import LINE_BITS, mutate, rand_root, rand_text, rng, strload
from miniformat import dumps

SEEDS = range(8)
N = 400


@pytest.mark.parametrize("seed", SEEDS)
def test_dump_then_load_roundtrips_and_yaml_agrees(seed):
    r = rng(seed)
    for _ in range(N):
        obj = rand_root(r)
        text = dumps(obj)
        assert mf.loads(text) == obj, (obj, text)
        assert strload(text) == obj, (obj, text)
        assert dumps(mf.loads(text)) == text


@pytest.mark.parametrize("seed", SEEDS)
def test_whatever_the_loader_accepts_means_the_same_in_yaml(seed):
    r = rng(100 + seed)
    accepted = 0
    for _ in range(N * 5):
        text = rand_text(r)
        try:
            ours = mf.loads(text)
        except mf.MiniFormatError:
            continue
        accepted += 1
        assert strload(text) == ours, text
    assert accepted > 20


@pytest.mark.parametrize("seed", SEEDS)
def test_mutated_documents_never_crash_and_stay_yaml_compatible(seed):
    r = rng(200 + seed)
    for _ in range(N):
        text = mutate(r, dumps(rand_root(r)))
        try:
            ours = mf.loads(text)
        except mf.MiniFormatError as e:
            assert e.line is None or 1 <= e.line <= text.count("\n") + 2, (text, e)
            continue
        assert strload(text) == ours, text
        assert mf.loads(dumps(ours)) == ours


@pytest.mark.parametrize("seed", SEEDS)
def test_garbage_only_ever_raises_miniformat_error(seed):
    r = rng(300 + seed)
    pool = "".join(LINE_BITS) + " \n\t:-#|\"'\\{}[]é\x00\r"
    for _ in range(N * 2):
        text = "".join(r.choice(pool) for _ in range(r.randint(0, 60)))
        try:
            mf.loads(text)
        except mf.MiniFormatError:
            pass


def test_random_unicode_never_crashes():
    r = rng(7)
    for _ in range(N):
        text = "".join(
            chr(
                r.choice(
                    [
                        r.randrange(0x20, 0x300),
                        r.randrange(0x2000, 0x2100),
                        r.randrange(0xD7F0, 0xE010),
                        r.randrange(0xFFF0, 0x10010),
                    ]
                )
            )
            for _ in range(r.randint(0, 30))
        )
        try:
            mf.loads(text)
            mf.loads("k: " + text)
            mf.loads('k: "%s"' % text)
        except mf.MiniFormatError:
            pass


def test_every_rejected_line_number_points_at_a_real_line():
    r = rng(11)
    for _ in range(2000):
        text = rand_text(r)
        try:
            mf.loads(text)
        except mf.MiniFormatError as e:
            if e.line is not None:
                assert 1 <= e.line <= len(text.split("\n")), (text, e)
