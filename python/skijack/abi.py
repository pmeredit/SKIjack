"""What is normative, gathered in one place.

A second implementation --- the C runtime of ``RUNTIME-DESIGN.md`` --- has
to agree with this one on a small number of things and is free to differ
on everything else.  Those things live here, so that an implementor has
one file to read rather than five modules to guess from.

**Normative.** The instruction set is :data:`ISA`.  The combinator names
a program may use beyond it are :data:`TIER1_NAMES`.  Declaration order
is continuation order (``DESIDERATA.md`` §5, and it is the one mistake
that is silent rather than loud).  The published dictionary's version
prefix is :data:`skijack.dictionary.VERSION`.

**Not normative.** Everything in :mod:`skijack.expand` about backend name
mangling, the ``\\x00``-prefixed sentinels used by the prober and the
quoter, and the order in which declarations happen to be compiled.  No
source program can spell those and no emitted term contains them.

The reason :data:`TIER1_NAMES` is written out rather than taken from the
host reducer's registry: ``DESIDERATA.md`` §5 makes the Tier 1 table a
versioned artifact, and a change to it a version change.  Taking it from
``aviary_kernel.birds.BY_NAME`` made the set of legal source names a
function of the installed dependency, so an upstream release adding a
combinator would have been an unrecorded ABI change.
"""

from __future__ import annotations

__all__ = ["ISA", "TIER1_NAMES"]

#: The instruction set.  Reserved in both directions: these three names
#: denote the combinators at level 0 even when an object type declares
#: leaves of the same names, and they always lower back to atoms.
ISA = ("S", "K", "I")

#: Tier 1 (``DESIDERATA.md`` §3): closed terms over the ISA with a fixed
#: meaning and a fixed expansion, which a program may name directly.
#: Adding one is a version change.
TIER1_NAMES = frozenset(("B", "C", "W", "Y"))
