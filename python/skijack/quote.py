"""Quotation: a term encoded as Scott data over a declared object type.

``SURFACE-LANGUAGE-DESIGN.md`` §6a, step 2.  This generalizes the
artifact's ``enc`` (four constructors), ``enc5`` (five) and
``scry_harness.py``'s ``encQ`` to any declared object type: the encoding
is a structural fold that maps every leaf atom to that leaf's
constructor and every application node to the application constructor.

**The level-1 symbol table** (§6b), as far as this step implements it.
Inside ``< >``:

* a name that is a **leaf constructor of the target object type** is
  that constructor -- so ``Err`` inside ``<K I Err>`` is ``term5``'s
  leaf, and ``S``, ``K``, ``I`` are the object type's leaves of those
  names rather than the ISA;
* **juxtaposition is the application constructor**;
* any other level-0 name (``UQ``, ``whnfF``, ``flipA``, ``Suc``) is
  **inlined as its expanded level-0 term and then quoted**, exactly as
  the artifact writes ``encP(A(UP, encP(IK)))``.  This is the decision
  this step takes; §6b's shared quoted subject ``⟨subject⟩``, with
  library names resolving to axes into it, is deferred.

Nested quotation is allowed: the inner ``<I K>`` of ``<UQ <I K>>``
compiles to a datum, which is a closed level-0 term, which the outer
quote then inlines and encodes like any other.

Nothing here reduces or bracket-abstracts: :func:`quote` folds over an
already-expanded term, iteratively, because a level-2 datum is tens of
thousands of nodes deep.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from aviary_kernel.terms import App, Atom, Term

from . import ast as A
from .generate import ObjectType

__all__ = ["QuoteError", "Encoder", "quote", "OBJECT_LEAF_PREFIX"]


class QuoteError(Exception):
    pass


#: Leaves of the object type that have no level-0 meaning (``Err``) are
#: carried through the level-0 code generator as atoms under this prefix,
#: so they cannot collide with a real combinator name.
OBJECT_LEAF_PREFIX = "\x00leaf:"


class Encoder:
    """The Scott encoder for one object type.

    ``leaf_terms`` maps a leaf's *level-0 atom name* to the closed term of
    that leaf's constructor; ``app_term`` is the application
    constructor's.  Both are already expanded to ``{S,K,I}``.
    """

    def __init__(self, obj: ObjectType, term_of: Callable[[str], Term]):
        self.obj = obj
        self.app_term = term_of(obj.app.name)
        self.leaf_terms: Dict[str, Term] = {}
        for c in obj.leaves:
            t = term_of(c.name)
            self.leaf_terms[c.name] = t
            self.leaf_terms[OBJECT_LEAF_PREFIX + c.name] = t

    def leaf(self, name: str) -> Optional[Term]:
        return self.leaf_terms.get(name)

    def quote(self, term: Term) -> Term:
        """Encode ``term`` structurally.  Iterative: a level-2 datum is
        far deeper than the Python stack."""
        out: List[Term] = []
        work: List[Tuple[Term, bool]] = [(term, False)]
        while work:
            x, done = work.pop()
            if isinstance(x, Atom):
                enc = self.leaf(x.name)
                if enc is None:
                    raise QuoteError(
                        f"cannot quote the atom {x.name!r}: the object type "
                        f"{self.obj.name!r} has no leaf constructor for it "
                        f"(its leaves are "
                        f"{', '.join(c.name for c in self.obj.leaves)})")
                out.append(enc)
                continue
            if not done:
                work.append((x, True))
                work.append((x.arg, False))
                work.append((x.fn, False))
            else:
                r = out.pop()
                l = out.pop()
                out.append(App(App(self.app_term, l), r))
        return out.pop()


def quote(term: Term, obj: ObjectType, term_of: Callable[[str], Term]) -> Term:
    """``quote(term, object_type)``: the closed datum for ``term``."""
    return Encoder(obj, term_of).quote(term)


def level1_names(obj: ObjectType) -> Dict[str, str]:
    """The level-1 table for ``obj``: leaf constructor name -> the atom
    the level-0 code generator should emit for it inside ``< >``."""
    return {c.name: OBJECT_LEAF_PREFIX + c.name for c in obj.leaves}
