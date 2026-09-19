"""The milestone of DESIDERATA.md section 6, item 2: the paper's
interpreter, written in the surface, compiled, and checked against the
artifact atom for atom and count for count.

The oracle is the artifact itself (`~/ski-in-ski/tower_harness.py`),
loaded read-only by the `oracle` fixture.
"""

import pytest
from aviary_kernel.environment import Environment
from aviary_kernel.reduce import Status
from aviary_kernel.terms import App, Atom, pretty

from skijack.expand import expand_program
from skijack.parser import parse
from skijack.probe import fast_reduce

from conftest import source

LEXICONS = ["ascii", "unicode"]
CAP = 400_000


def ap(*ts):
    r = ts[0]
    for t in ts[1:]:
        r = App(r, t)
    return r


S, K, I, ERR = Atom("S"), Atom("K"), Atom("I"), Atom("Err")
OMEGA_OBJ = ap(ap(S, I, I), ap(S, I, I))


@pytest.fixture(scope="module")
def built():
    out = {}
    for stem in ("interp-whnff", "interp-whnff-written-loop", "interp-t3"):
        for lx in LEXICONS:
            out[(stem, lx)] = expand_program(parse(source(stem, lx), lx))
    return out


# --------------------------------------------------------------- whnfF

#: every definition of the base interpreter, against the artifact's name
WHNFF_PAIRS = [
    ("loop", "whnfF"), ("loop1", "wf1"), ("step", "step"),
    ("sp", "sp"), ("spApp", "spApp"), ("resS", "resS"), ("resK", "resK"),
    ("resI", "resI"), ("rb", "rb"), ("rb1", "rb1"),
    ("stepS", "stepS"), ("stepS1", "stepS1"), ("stepS2", "stepS2"),
    ("stepS3", "stepS3"), ("stepK", "stepK"), ("stepK1", "stepK1"),
    ("stepK2", "stepK2"), ("stepI", "stepI"), ("stepI1", "stepI1"),
    ("nil", "nil"), ("cons", "cons"),
    ("Nothing", "nothing"), ("Just", "just"),
    ("S", "encS"), ("K", "encK"), ("I", "encI"), ("App", "encA"),
]


@pytest.mark.parametrize("lx", LEXICONS)
@pytest.mark.parametrize("mine,theirs", WHNFF_PAIRS,
                         ids=[p[0] for p in WHNFF_PAIRS])
def test_every_definition_matches_the_artifact(built, oracle, lx, mine, theirs):
    e = built[("interp-whnff", lx)]
    assert pretty(e.term(mine)) == pretty(oracle.term(theirs))


@pytest.mark.parametrize("lx", LEXICONS)
def test_whnfF_is_618_atoms(built, oracle, lx):
    e = built[("interp-whnff", lx)]
    assert e.size("whnfF") == 618
    assert pretty(e.term("whnfF")) == pretty(oracle.term("whnfF"))


@pytest.mark.parametrize("lx", LEXICONS)
def test_step_is_the_papers_569_atom_step(built, lx):
    assert built[("interp-whnff", lx)].size("step") == 569


@pytest.mark.parametrize("lx", LEXICONS)
def test_the_written_loop_compiles_to_the_generated_one(built, lx):
    gen = built[("interp-whnff", lx)]
    written = built[("interp-whnff-written-loop", lx)]
    assert pretty(written.term("whnfF")) == pretty(gen.term("whnfF"))
    assert written.size("whnfF") == 618


def test_the_two_spellings_compile_to_the_same_term(built):
    a = built[("interp-whnff", "ascii")]
    u = built[("interp-whnff", "unicode")]
    assert pretty(a.term("whnfF")) == pretty(u.term("whnfF"))


# ------------------------------------------------------------------- T0

def test_T0_reaches_whnf_in_exactly_340_contractions(built, oracle):
    """The paper's T0: whnfF 3 <I K>."""
    e = built[("interp-whnff", "ascii")]
    env = Environment()
    inner = ap(e.term("whnfF"), oracle.natP(3), oracle.encP(App(I, K)))
    r = fast_reduce(inner, env, whnf_only=True, max_steps=CAP)
    assert r.status is Status.WHNF
    assert r.steps == 340


def test_T0_decodes_to_Just_K(built, oracle):
    """Read behaviorally: the Maybe selects the `just` marker, and the
    payload -- an encoded object term -- selects the K marker of the four
    the object type has."""
    e = built[("interp-whnff", "ascii")]
    env = Environment()
    inner = ap(e.term("whnfF"), oracle.natP(3), oracle.encP(App(I, K)))
    r = fast_reduce(inner, env, whnf_only=True, max_steps=CAP)
    outer = fast_reduce(ap(r.term, Atom("MNo"), Atom("MJu")), env,
                        whnf_only=True, max_steps=CAP)
    assert isinstance(outer.term, App)
    assert outer.term.fn == Atom("MJu")          # it is a Just
    payload = fast_reduce(
        ap(outer.term.arg, Atom("mS"), Atom("mK"), Atom("mI"), Atom("mA")),
        env, whnf_only=True, max_steps=CAP)
    assert pretty(payload.term) == "mK"          # carrying the encoded K


# ------------------------------------------------------------------- T3

T3_PAIRS = [("wf5Abs", "wf5Abs"), ("wf5Omg", "wf5Omg"),
            ("wf5Abs.step", "st5Abs"), ("wf5Omg.step", "st5Omg"),
            ("wf5Abs.loop1", "wf5Abs1"), ("wf5Omg.loop1", "wf5Omg1"),
            ("sp", "sp5"), ("rb", "rb5"),
            ("stepS", "q5S"), ("stepK", "q5K"), ("stepI", "q5I"),
            ("wf5Abs.stepErr", "errArmAbs"), ("wf5Omg.stepErr", "errArmOmg"),
            ("Stepped", "stepped"), ("Done", "done"), ("Errd", "errd"),
            ("RVal", "rVal"), ("RErr", "rErr"), ("RTime", "rTime")]


@pytest.mark.parametrize("mine,theirs", T3_PAIRS, ids=[p[0] for p in T3_PAIRS])
def test_T3_definitions_match_the_artifact(built, oracle, mine, theirs):
    e = built[("interp-t3", "ascii")]
    assert pretty(e.term(mine)) == pretty(oracle.term(theirs))


def test_T3_sizes_are_768_and_771(built):
    e = built[("interp-t3", "ascii")]
    assert (e.size("wf5Abs"), e.size("wf5Omg")) == (768, 771)


def test_omega_is_the_artifacts_omega(built, oracle):
    e = built[("interp-t3", "ascii")]
    assert pretty(e.term("omega")) == pretty(oracle.OMEGA)


def test_the_two_T3_spellings_compile_to_the_same_terms(built):
    a, u = built[("interp-t3", "ascii")], built[("interp-t3", "unicode")]
    for n in ("wf5Abs", "wf5Omg", "wf5Abs.step", "wf5Omg.step"):
        assert pretty(a.term(n)) == pretty(u.term(n))


def _t3_run(exp, oracle, which, obj, cap=CAP):
    """Return (tag, contractions).  The tag is read by probing the
    three-way result with three markers; "CAP" means the host reducer hit
    its step cap, i.e. the emulator diverged on the host."""
    env = Environment()
    inner = ap(exp.term(which), oracle.natP(20), oracle.enc5P(obj))
    r = fast_reduce(inner, env, whnf_only=True, max_steps=cap)
    if r.status is not Status.WHNF:
        return "CAP", r.steps
    d = fast_reduce(ap(r.term, Atom("mV"), Atom("mE"), Atom("mT")), env,
                    whnf_only=True, max_steps=cap)
    head = d.term
    while isinstance(head, App):
        head = head.fn
    return {"mV": "VAL", "mE": "ERR", "mT": "TIME"}[head.name], r.steps


#: the paper's T3 table
T3_TABLE = [
    ("Err", ERR, "ERR", "CAP"),
    ("Err K", ap(ERR, K), "ERR", "CAP"),
    ("K I Err", ap(K, I, ERR), "VAL", "VAL"),
    ("I K", ap(I, K), "VAL", "VAL"),
    ("Omega", OMEGA_OBJ, "TIME", "TIME"),
]


@pytest.mark.parametrize("label,obj,want_abs,want_omg", T3_TABLE,
                         ids=[r[0] for r in T3_TABLE])
def test_T3_table(built, oracle, label, obj, want_abs, want_omg):
    e = built[("interp-t3", "ascii")]
    assert _t3_run(e, oracle, "wf5Abs", obj)[0] == want_abs
    assert _t3_run(e, oracle, "wf5Omg", obj)[0] == want_omg


@pytest.mark.parametrize("label,obj", [("K I Err", ap(K, I, ERR)),
                                       ("I K", ap(I, K))])
def test_the_two_interpreters_are_indistinguishable_where_Err_never_fires(
        built, oracle, label, obj):
    """Faithfulness: the one differing equation is unreachable for these two,
    so both the answer and the contraction count agree."""
    e = built[("interp-t3", "ascii")]
    assert _t3_run(e, oracle, "wf5Abs", obj) == _t3_run(e, oracle, "wf5Omg", obj)


def test_the_absorbing_arm_reports_a_crash_the_other_hides(built, oracle):
    """The single authored site: `stepErr acc = Errd` turns a crash into
    a value; `stepErr acc = omega` turns it into host divergence."""
    e = built[("interp-t3", "ascii")]
    assert _t3_run(e, oracle, "wf5Abs", ERR) == ("ERR", 127)
    tag, steps = _t3_run(e, oracle, "wf5Omg", ERR)
    assert tag == "CAP" and steps >= CAP


# ------------------------------- the interpreter with nothing generated

@pytest.mark.parametrize("lx", LEXICONS)
def test_the_fully_written_interpreter_compiles_to_the_same_term(oracle, lx):
    """`interp-whnff-written.*.ski` is exactly what
    `render(generate(parse(interp-whnff)))` prints, kept as ordinary user
    source.  Compiled with generation *off* it must give the same
    618-atom term -- which is the claim that generate.py emits surface
    syntax and adds no semantics of its own."""
    e = expand_program(parse(source("interp-whnff-written", lx), lx),
                       generate_forms=False)
    assert e.size("whnfF") == 618
    assert pretty(e.term("whnfF")) == pretty(oracle.term("whnfF"))


def test_the_written_source_is_what_generation_prints():
    """The corpus file is regenerated, not hand-copied: parsing it back
    gives the same tree as generating from the short source."""
    from skijack.generate import generate
    from skijack.render import render
    for lx in LEXICONS:
        want = generate(parse(source("interp-whnff", lx), lx))
        got = parse(source("interp-whnff-written", lx), lx)
        assert got == want


@pytest.mark.parametrize("lx", LEXICONS)
def test_T0_on_the_fully_written_interpreter(built, oracle, lx):
    """And it runs: the paper's T0, 340 contractions, from a program with
    nothing generated at all."""
    e = expand_program(parse(source("interp-whnff-written", lx), lx),
                       generate_forms=False)
    env = Environment()
    inner = ap(e.term("whnfF"), oracle.natP(3), oracle.encP(App(I, K)))
    r = fast_reduce(inner, env, whnf_only=True, max_steps=CAP)
    assert r.status is Status.WHNF
    assert r.steps == 340
