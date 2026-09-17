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
