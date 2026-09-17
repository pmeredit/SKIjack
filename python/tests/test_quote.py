"""quote.py: the Scott encoding of a term over a declared object type,
and the level-1 symbol table.

Checked against the artifact's own encoders: ``encP`` (four
constructors) and ``enc5`` (five).
"""

import pytest
from aviary_kernel.terms import App, Atom, pretty

from skijack.check import DataError, InterfaceError, SymbolTableError
from skijack.expand import ExpandError, expand_program
from skijack.generate import find_object_type
from skijack.parser import parse, parse_ascii
from skijack.quote import Encoder, QuoteError, level1_names

from conftest import source

BASE = ("term === S | K | I | App term term\n"
        "maybe === Nothing | Just term\n"
        "whnfF := { step m = sp m nil stepS stepK stepI }\n")


@pytest.fixture(scope="module")
def flipa():
    return expand_program(parse_ascii(source("level1-flipa", "ascii")))


@pytest.fixture(scope="module")
def tower():
    return expand_program(parse_ascii(source("tower", "ascii")))


@pytest.fixture(scope="module")
def t3():
    return expand_program(parse_ascii(
        source("interp-t3", "ascii") + "d := <K I Err>\n"))


# ------------------------------------------------- against the artifact

def test_a_bare_quote_is_a_datum_not_a_run(tower):
    """SYNTAX.md section 2: quotation emits the Scott encoding; a datum,
    not run.  So it lands in `terms`, not in `level1`."""
    e = expand_program(parse_ascii(BASE + "d := <I K>\n"))
    assert "d" in e.terms and "d" not in e.level1


def test_four_constructor_encoding_matches_encP(oracle):
    e = expand_program(parse_ascii(BASE + "d := <I K>\n"))
    assert pretty(e.term("d")) == pretty(oracle.encP(App(Atom("I"), Atom("K"))))


def test_five_constructor_encoding_matches_enc5(oracle, t3):
    want = oracle.enc5P(App(App(Atom("K"), Atom("I")), Atom("Err")))
    assert pretty(t3.term("d")) == pretty(want)


def test_nested_quotation_matches_the_artifacts_tower_datum(oracle, tower):
    """`<UQ <I K>>` is exactly the artifact's encP(A(UP, encP(I K)))."""
    e = expand_program(parse_ascii(
        source("tower", "ascii") + "d := <UQ <I K>>\n"))
    ik = App(Atom("I"), Atom("K"))
    want = oracle.encP(App(oracle.term("UQ"), oracle.encP(ik)))
    assert pretty(e.term("d")) == pretty(want)


def test_the_quoted_flipA_program_is_1809_atoms(flipa):
    """EXAMPLES.md section 3: `<flipA [K I] K>` is 1,809 atoms for a
    49-atom program."""
    assert flipa.sizes["flipA"] == 29
    assert flipa.sizes["prog"] == 1809


# ------------------------------------------------- the level-1 table

def test_inside_a_quote_a_leaf_name_is_the_constructor(t3):
    """`Err` has no level-0 meaning; inside < > it is term5's leaf."""
    obj = t3.object_type
    assert [c.name for c in obj.leaves] == ["S", "K", "I", "Err"]
    assert level1_names(obj)["Err"].endswith("Err")


def test_the_two_symbol_tables_are_kept_apart(oracle):
    """Inside < > juxtaposition is the App constructor and `S`/`K`/`I`
    are the object type's leaves; outside, juxtaposition is the host's
    application and those three names are the ISA.  Every *other*
    constructor means the same thing at both levels -- a Scott
    constructor -- which is why the rebuilder can apply `App`."""
    e = expand_program(parse_ascii(
        source("interp-t3", "ascii") + "d := <Err>\ntwo := <K I>\n"
        "level0two = K I\nlevel0err = Err\n"))
    assert pretty(e.term("d")) == pretty(oracle.enc5P(Atom("Err")))
    assert pretty(e.term("two")) == pretty(
        oracle.enc5P(App(Atom("K"), Atom("I"))))
    # the three reserved names differ between the levels ...
    assert pretty(e.term("level0two")) == "K I"
    assert pretty(e.term("level0two")) != pretty(e.term("two"))
    # ... and every other constructor does not
    assert pretty(e.term("level0err")) == pretty(e.term("d"))
    # a name in neither table is still refused
    with pytest.raises(SymbolTableError, match="names neither table"):
        expand_program(parse_ascii(
            source("interp-t3", "ascii") + "bad := <nowhere>\n"))


def test_a_non_constructor_name_inside_a_quote_is_inlined(oracle, tower):
    """The decision this step takes: `UQ` inside < > is its expanded
    level-0 term, quoted -- not a name looked up in a quoted subject."""
    assert pretty(tower.term("UQ")) == pretty(oracle.term("UQ"))
    assert tower.sizes["UQ"] == 43


def test_S_K_and_I_inside_a_quote_are_the_object_types_leaves(oracle):
    e = expand_program(parse_ascii(BASE + "d := <S>\n"))
    assert pretty(e.term("d")) == pretty(oracle.encP(Atom("S")))


def test_quoting_into_an_alphabet_that_cannot_express_the_ISA_is_refused():
    """An object type whose leaves are not named S, K, I cannot carry an
    inlined level-0 term, and says so."""
    src = ("t === Ess | Kay | Eye | App t t\n"
           "m === No | Yes t\n"
           "c := {\n  stepEss a = No\n  stepKay a = No\n  stepEye a = No\n}\n"
           "lvl0 x = x\n"
           "d := <lvl0>\n")
    with pytest.raises(QuoteError, match="no leaf constructor for it"):
        expand_program(parse_ascii(src))


def test_a_nested_quote_may_not_carry_fuel():
    with pytest.raises(DataError, match="may not carry fuel"):
        expand_program(parse_ascii(BASE + "d := <I <K>@3>\n"))


# ------------------------------------------------- packaging

def test_level1_packaging_shape(flipa):
    p = flipa.level1["answer"]
    assert p.interp == "whnfF"
    assert p.fuel == 41
    assert p.object_type.name == "term"
    assert p.result_type.name == "maybe"
    # the executable is interp fuel datum
    t = p.term
    assert isinstance(t, App) and isinstance(t.fn, App)
    assert pretty(t.fn.fn) == pretty(flipa.term("whnfF"))
    assert pretty(t.arg) == pretty(flipa.term("prog"))


def test_the_fuel_numeral_is_the_artifacts_scott_numeral(oracle, flipa):
    p = flipa.level1["answer"]
    for k in (0, 1, 5, 41):
        assert pretty(p.numeral(k)) == pretty(oracle.natP(k))


def test_elided_fuel_has_no_closed_term_but_has_a_placeholder(flipa):
    from skijack.expand import FUEL_PLACEHOLDER
    p = flipa.level1["policy"]
    assert p.fuel == "policy"
    assert "policy" not in flipa.terms
    with pytest.raises(ExpandError, match="elided fuel"):
        _ = p.term
    assert pretty(p.placeholder).count(FUEL_PLACEHOLDER.name) == 1
    assert pretty(p.with_fuel(41)) == pretty(flipa.level1["answer"].term)


def test_an_unknown_interpreter_is_refused():
    with pytest.raises(InterfaceError, match="not a core in this program"):
        expand_program(parse_ascii(BASE + "d := nope |- <I K>@3\n"))


def test_an_interpreter_must_get_all_its_parameters():
    """`whnfF` takes none; over-applying it is an error, and so is
    under-applying a core that takes one."""
    with pytest.raises(InterfaceError, match="takes 0 parameter"):
        expand_program(parse_ascii(BASE + "d := whnfF x |- <I K>@3\n"))


def test_default_interpreter_is_a_core_named_whnfF(flipa):
    e = expand_program(parse_ascii(BASE + "d := <I K>@3\n"))
    assert e.level1["d"].interp == "whnfF"
    with pytest.raises(ExpandError, match="no core named 'whnfF'"):
        expand_program(parse_ascii(
            source("interp-t3", "ascii") + "d := <K I Err>@3\n"))


@pytest.mark.parametrize("stem", ["level1-flipa", "tower"])
def test_the_two_spellings_produce_the_same_data(stem):
    a = expand_program(parse(source(stem, "ascii"), "ascii"))
    u = expand_program(parse(source(stem, "unicode"), "unicode"))
    for name, prog in a.level1.items():
        assert pretty(prog.datum) == pretty(u.level1[name].datum), name
        assert prog.fuel == u.level1[name].fuel
