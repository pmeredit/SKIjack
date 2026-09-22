"""The three worked examples added after the paper: words to numbers two
ways, full ASCII as a type with a digit parser, and an event type with a
kernel the runtime pokes.  Every number here was measured on this
expander; values are read behaviourally, never by inspecting syntax.
"""

import pytest
from aviary_kernel.terms import App, Atom

import skijack
from skijack import corpus
from skijack.parser import parse
from skijack.probe import Prober
from skijack.render import render_ascii
from skijack.run import decode, peel, run_level0, run_level1

LEXICONS = ["ascii", "unicode"]


def build(stem, lx):
    return skijack.compile(corpus.read(stem, lx), lexicon=lx)


def yes_or_no(term):
    r = run_level0(App(App(term, Atom("yes")), Atom("no")), 100_000)
    assert isinstance(r.term, Atom)
    return r.term.name


# ------------------------------------------------ words to numbers, two ways

@pytest.mark.parametrize("lx", LEXICONS)
def test_words_to_numbers_case_at_level_0(lx):
    e = build("words-to-numbers", lx)
    assert (e.sizes["toNum"], e.sizes["three"]) == (58, 61)
    assert Prober(e).read_nat(e.terms["three"]) == 3
    assert run_level0(e.terms["three"], 100_000).steps == 10


@pytest.mark.parametrize("lx", LEXICONS)
def test_words_to_numbers_namespace_at_level_1(lx):
    """The same three facts as a namespace: two orders of magnitude more
    atoms, tens of thousands of contractions, and an encoded term back."""
    e = build("words-to-numbers", lx)
    assert (e.sizes["nums"], e.sizes["n3"]) == (6_691, 9_081)
    p = e.level1["n3"]
    out = run_level1(p, 5_000_000)
    ctor, fields = peel(out.term, p.result_type, max_steps=5_000_000)
    assert (ctor, out.steps) == ("RValN", 22_280)
    # what comes back is the *encoding* of Suc (Suc (Suc Zero)), not a numeral
    assert render_ascii(decode(fields[0], p.object_type, max_steps=5_000_000)).startswith("K (S (K (S I)) K")


# ---------------------------------------------- full ASCII as a type; digits

@pytest.mark.parametrize("lx", LEXICONS)
def test_full_ascii_is_a_type_and_a_character_is_a_datum(lx):
    e = build("ascii-digits", lx)
    assert (e.sizes["C0"], e.sizes["C48"], e.sizes["C127"]) == (379, 283, 128)
    # a 128-way case is a few hundred atoms, not a few hundred thousand
    assert (e.sizes["isDigit"], e.sizes["digitValue"]) == (503, 745)
    assert yes_or_no(e.terms["yes"]) == "yes"      # isDigit C55 ('7')
    assert yes_or_no(e.terms["no"]) == "no"        # isDigit C65 ('A')


@pytest.mark.parametrize("lx", LEXICONS)
def test_digits_fold_to_a_numeral(lx):
    e = build("ascii-digits", lx)
    assert (e.sizes["add"], e.sizes["mul"], e.sizes["parseDigits"]) == (42, 77, 1_000)
    pr = Prober(e)
    assert pr.read_nat(e.terms["twelve"]) == 12        # "12"
    assert pr.read_nat(e.terms["fortyTwo"]) == 42      # "42"
    assert run_level0(e.terms["twelve"], 2_000_000).steps == 592


# ------------------------------------------- an event type and a kernel

@pytest.mark.parametrize("lx", LEXICONS)
def test_a_runtime_can_poke_the_kernel_with_events_it_builds(lx):
    """RUNTIME-DESIGN.md section 3b's loop, from the runtime's side: build
    each event datum from the program's own constructors, apply poke to
    the state and the event, install the new state, read the effects."""
    e = build("kernel-events", lx)
    assert (e.sizes["kernel.poke"], e.sizes["Tick"], e.sizes["Poke"], e.sizes["Log"]) == (146, 1, 8, 5)
    pr = Prober(e)
    src = (corpus.DIR / f"kernel-events.{lx}.ski").read_text()
    decl = {d.name: d for d in parse(src, lx).decls if hasattr(d, "ctors")}
    hd, tl, poke = e.terms["hd"], e.terms["tl"], e.terms["kernel.poke"]

    def inject(state, event):
        out = run_level0(App(App(poke, pr.nat(state)), event), 200_000)
        new_state = pr.read_nat(App(hd, out.term))
        ctor, fields = peel(App(tl, out.term), decl["effects"])
        effect = None
        if fields:
            name, payload = peel(fields[0], decl["effect"])
            effect = (name, pr.read_nat(payload[0]))
        return out.steps, new_state, ctor, effect

    assert inject(0, e.terms["Tick"]) == (24, 1, "Nil", None)
    assert inject(1, App(e.terms["Poke"], pr.nat(5))) == (35, 6, "Cons", ("Log", 1))
    assert inject(6, e.terms["Tick"]) == (24, 7, "Nil", None)
