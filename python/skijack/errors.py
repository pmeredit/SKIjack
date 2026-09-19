"""One base class for everything this package raises.

A caller that wants to fail cleanly on bad input -- the CLI in
:mod:`skijack.__main__`, or any program embedding the compiler -- needs a
single class to catch.  Before this existed the CLI caught
:class:`~skijack.check.CheckError` alone, which is not a base of
:class:`~skijack.expand.ExpandError`, so every expander rejection reached
the user as a traceback.

Each phase keeps its own class (``LexError``, ``ParseError``,
``CheckError`` and the rest) because the phase is worth knowing; they all
derive from :class:`SkijackError` so that catching one thing is enough.
Bad *input* raises one of these.  A bug in the compiler is still an
ordinary exception and should still look like one.
"""

from __future__ import annotations

__all__ = ["SkijackError"]


class SkijackError(Exception):
    """Base of every error this package raises for a bad program."""
