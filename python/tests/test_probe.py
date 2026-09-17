"""Behavioral checks: values are read by running terms against fresh
marker atoms, never by reading combinator syntax.

These are the "Checks run" of EXAMPLES.md sections 1 to 3.
"""

import pytest
from aviary_kernel.terms import Atom, pretty

from skijack.expand import expand_program
from skijack.parser import parse
from skijack.probe import Prober

from conftest import source

LEXICONS = ["ascii", "unicode"]
FUEL = 20_000


@pytest.fixture(scope="module")
def probers():
    out = {}
    for stem in ("sec1-nat", "sec2-c", "sec3-swap"):
        for lx in LEXICONS:
            e = expand_program(parse(source(stem, lx), lx))
            out[(stem, lx)] = (e, Prober(e))
    return out


NUMERAL_CHECKS = [
    ("inc", (2,), 3),
    ("dec", (3,), 2),
    ("dec", (0,), 0),
    ("add", (2, 3), 5),
    ("add", (0, 4), 4),
    ("sub", (5, 2), 3),
    ("sub", (2, 5), 0),
]


@pytest.mark.parametrize("lx", LEXICONS)
@pytest.mark.parametrize("name,args,want", NUMERAL_CHECKS,
                         ids=[f"{n}{a}" for n, a, _ in NUMERAL_CHECKS])
def test_section1_numeral_probes(probers, lx, name, args, want):
    e, p = probers[("sec1-nat", lx)]
    got = p.read_nat(p.reduce(e.term(name), *[p.nat(k) for k in args],
                              max_steps=FUEL, whnf_only=True).term,
                     max_steps=FUEL)
    assert got == want


@pytest.mark.parametrize("lx", LEXICONS)
def test_dec_three_reaches_whnf_in_fifteen_contractions(probers, lx):
    e, p = probers[("sec1-nat", lx)]
    r = p.reduce(e.term("dec"), p.nat(3), max_steps=FUEL, whnf_only=True)
    assert r.steps == 15


@pytest.mark.parametrize("lx", LEXICONS)
def test_section2_probes(probers, lx):
    e, p = probers[("sec2-c", lx)]
    X1, X2 = p.markers(2)
    assert p.reduce_text(e.term("C"), Atom("K"), X1, X2, max_steps=FUEL) == "X2"
    assert p.apply_markers(e.term("flipK1"), 2, max_steps=FUEL) == "X2"
    assert p.apply_markers(e.term("flipK2"), 2, max_steps=FUEL) == "X2"


@pytest.mark.parametrize("lx", LEXICONS)
def test_section3_probes(probers, lx):
    e, p = probers[("sec3-swap", lx)]
    X1, X2 = p.markers(2)
    cell = p.pair(X1, X2)
    assert p.reduce_text(e.term("flipA"), cell, Atom("K"),
                         max_steps=FUEL) == "X2"


@pytest.mark.parametrize("lx", LEXICONS)
def test_flipA_on_K_I_takes_forty_contractions(probers, lx):
    e, p = probers[("sec3-swap", lx)]
    cell = p.pair(Atom("K"), Atom("I"))
    r = p.reduce(e.term("flipA"), cell, Atom("K"), max_steps=FUEL)
    assert (pretty(r.term), r.steps) == ("I", 40)


def test_the_numeral_reader_refuses_a_non_numeral():
    from skijack.probe import ProbeError
    e = expand_program(parse(source("sec1-nat", "ascii"), "ascii"))
    p = Prober(e)
    with pytest.raises(ProbeError, match="not a Scott numeral"):
        p.read_nat(e.term("pair"), max_steps=FUEL)


def test_markers_are_fresh_and_uninterpreted():
    e = expand_program(parse(source("sec2-c", "ascii"), "ascii"))
    p = Prober(e)
    assert [m.name for m in p.markers(3)] == ["X1", "X2", "X3"]


def test_the_numeral_reader_memoizes_soundly():
    """The reader caches by node identity.  CPython recycles ids, so the
    cache must hold the node itself; reading two numerals must not let
    one's answer leak into the other."""
    e = expand_program(parse(source("sec1-nat", "ascii"), "ascii"))
    p = Prober(e)
    for k in (0, 1, 2, 3, 5, 8):
        assert p.read_nat(p.nat(k), max_steps=FUEL) == k
        assert p.read_nat(p.nat(k), max_steps=FUEL) == k   # now from cache
    assert p._nat_cache, "nothing was memoized"
    for key, (node, value) in p._nat_cache.items():
        assert id(node) == key                # the node pins its own id
        assert p.read_nat(node, max_steps=FUEL) == value


def test_reading_a_numeral_twice_agrees_under_churn():
    e = expand_program(parse(source("sec1-nat", "ascii"), "ascii"))
    p = Prober(e)
    first = [p.read_nat(p.reduce(e.term("dec"), p.nat(k), max_steps=FUEL,
                                 whnf_only=True).term, max_steps=FUEL)
             for k in range(6)]
    assert first == [0, 0, 1, 2, 3, 4]
    junk = [expand_program(parse(source("sec2-c", "ascii"), "ascii"))
            for _ in range(3)]
    second = [p.read_nat(p.reduce(e.term("dec"), p.nat(k), max_steps=FUEL,
                                  whnf_only=True).term, max_steps=FUEL)
              for k in range(6)]
    assert second == first and len(junk) == 3
