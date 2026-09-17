"""The package API and `python3 -m skijack`."""

import io
import contextlib

import pytest

import skijack
from skijack.__main__ import main
from skijack.parser import parse_ascii

from conftest import CORPUS, source

WHNFF = str(CORPUS / "interp-whnff.ascii.ski")
SCRYNS = str(CORPUS / "scry-ns.ascii.ski")
BAD = str(CORPUS / "sec4-interp.ascii.ski")


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


# ------------------------------------------------------------- the API

def test_compile_runs_the_whole_pipeline():
    e = skijack.compile(source("interp-whnff", "ascii"))
    assert e.sizes["whnfF"] == 618


def test_compile_takes_either_lexicon():
    a = skijack.compile(source("interp-whnff", "ascii"), "ascii")
    u = skijack.compile(source("interp-whnff", "unicode"), "unicode")
    assert a.sizes["whnfF"] == u.sizes["whnfF"] == 618


def test_compile_checks_by_default():
    """With checking on, Stage A rejects first, with its own class; with
    it off the expander's own backstop still refuses -- the output is
    never wrong, only the message is coarser."""
    with pytest.raises(skijack.ScopeError):
        skijack.compile("f x = x nowhere\n")
    with pytest.raises(skijack.ExpandError):
        skijack.compile("f x = x nowhere\n", check=False)


def test_the_package_exposes_the_pipeline():
    for name in ("compile", "check", "lift", "lower", "run_level1",
                 "run_policy", "run_with_namespace", "from_expansion",
                 "structural_hash", "render_ascii", "parse_ascii"):
        assert hasattr(skijack, name), name


# ------------------------------------------------------------- the CLI

def test_summary_is_the_default():
    code, out, _ = run(WHNFF)
    assert code == 0
    assert "Stage A clean" in out and "compiled terms" in out


def test_check_reports_clean():
    code, out, _ = run(WHNFF, "--check")
    assert code == 0 and "Stage A clean" in out


def test_check_reports_problems_and_fails():
    code, _out, err = run(BAD, "--check")
    assert code == 1 and "ScopeError" in err and "errd" in err


def test_expand_prints_terms_with_sizes():
    code, out, _ = run(WHNFF, "--expand")
    assert code == 0
    assert any(line.split()[:2] == ["618", "whnfF"] for line in out.splitlines())


def test_dictionary_prints_the_versioned_table():
    code, out, _ = run(WHNFF, "--dictionary")
    assert code == 0
    assert out.startswith(f"# {skijack.DICTIONARY_VERSION}:")
    assert any(" Y " in line and "14" in line for line in out.splitlines())


def test_lift_prints_named_source():
    code, out, _ = run(WHNFF, "--lift", "step")
    assert code == 0
    assert out.strip() == "S (S (S (S sp (K K)) (K stepS)) (K stepK)) (K stepI)"


def test_render_round_trips_through_the_cli():
    code, out, _ = run(WHNFF, "--render", "unicode")
    assert code == 0
    from skijack.parser import parse, parse_ascii as pa
    assert parse(out, "unicode") == pa(source("interp-whnff", "ascii"))


def test_run_a_level_1_declaration():
    code, out, _ = run(SCRYNS, "--run", "answer")
    assert code == 0 and out.startswith("RValN K")


def test_run_overrides_the_fuel():
    code, out, _ = run(SCRYNS, "--run", "answer", "--fuel", "1")
    assert code == 0 and out.startswith("RTimeN")


def test_run_a_level_0_name_prints_its_term():
    code, out, _ = run(WHNFF, "--run", "sp")
    assert code == 0 and out.split()[0] == "126"


def test_an_unknown_name_fails():
    code, _out, err = run(WHNFF, "--run", "nope")
    assert code == 1 and "no declaration named" in err
