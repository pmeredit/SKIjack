import pathlib

import pytest

CORPUS = pathlib.Path(__file__).parent / "corpus"

#: every corpus file, as (stem, lexicon, path)
ALL_SOURCES = sorted(
    (p.name.split(".")[0], p.name.split(".")[1], p)
    for p in CORPUS.glob("*.ski")
)

#: stems the expander can compile end to end.  EXAMPLES.md 1-3 need no
#: generation; the three interpreter stems exercise generate.py.  The
#: remaining stems need quotation, which is a later step.
EXPANDABLE = ("sec1-nat", "sec2-c", "sec3-swap")
INTERPRETERS = ("interp-whnff", "interp-whnff-written-loop", "interp-t3")


def source(stem: str, lexicon: str) -> str:
    return (CORPUS / f"{stem}.{lexicon}.ski").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def corpus():
    return {(s, lx): p.read_text(encoding="utf-8") for s, lx, p in ALL_SOURCES}


#: the paper's artifact, used read-only as the test oracle.  Its module
#: body is executed with the ``__main__`` block split off, which is the
#: whole of the dependency: nothing is written back and the artifact's
#: own Environment is never handed to the expander.
ARTIFACT = pathlib.Path("/Users/neal/ski-in-ski/tower_harness.py")


@pytest.fixture(scope="session")
def oracle():
    if not ARTIFACT.exists():                      # pragma: no cover
        pytest.skip(f"artifact not present at {ARTIFACT}")
    head = ARTIFACT.read_text(encoding="utf-8").split("if __name__")[0]
    ns = {"__name__": "skijack_test_oracle"}
    exec(compile(head, str(ARTIFACT), "exec"), ns)

    from aviary_kernel.abstraction import expand as _x

    class Oracle:
        env = ns["env"]
        natP = staticmethod(ns["natP"])
        encP = staticmethod(ns["encP"])
        enc = staticmethod(ns["enc"])
        enc5 = staticmethod(ns["enc5"])
        OMEGA = ns["OMEGA"]

        @staticmethod
        def term(name):
            """The artifact's closed {S,K,I} term for one of its names."""
            return _x(ns["a"](name), ns["env"])

        @staticmethod
        def enc5P(t):
            return _x(ns["enc5"](t), ns["env"])

    return Oracle()
