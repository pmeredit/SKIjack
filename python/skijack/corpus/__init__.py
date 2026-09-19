"""The conformance corpus, shipped with the package.

Seventeen programs, each written in both lexicons, that the test suite
compiles and compares against the hand-built artifact of the companion
paper.  They are package data rather than test fixtures because they are
the specification's examples: a second implementation is correct when it
reproduces these, and a reader who installs the package should get them.

    >>> from skijack import corpus
    >>> src = corpus.read("interp-whnff", "ascii")
    >>> import skijack; skijack.compile(src).sizes["whnfF"]
    618
"""

from __future__ import annotations

import pathlib
from typing import List, Tuple

__all__ = ["DIR", "names", "path", "read"]

#: the directory holding the ``.ski`` sources
DIR = pathlib.Path(__file__).parent


def names() -> List[str]:
    """Every program, once, without its lexicon suffix."""
    return sorted({p.name.split(".")[0] for p in DIR.glob("*.ski")})


def path(stem: str, lexicon: str = "ascii") -> pathlib.Path:
    p = DIR / f"{stem}.{lexicon}.ski"
    if not p.exists():
        raise FileNotFoundError(
            f"no corpus program {stem!r} in {lexicon!r}; "
            f"available: {', '.join(names())}")
    return p


def read(stem: str, lexicon: str = "ascii") -> str:
    return path(stem, lexicon).read_text(encoding="utf-8")
