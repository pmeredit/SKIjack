"""Type-generated forms: the interpreter interface of
``SURFACE-LANGUAGE-DESIGN.md`` §6c.

A type declaration generates its constructors and case form (that part
lives in :mod:`skijack.expand`).  When the program declares an *object
type* -- a sum type with one binary self-referential constructor, the
alphabet a virtualizing interpreter walks -- it also generates, here:

* the **spine walker** ``sp`` and the **rebuilder** ``rb`` at that type's
  arity, in the artifact's shape (``resS``/``resK``/``resI``, ``spApp``,
  ``rb1``, tied with the environment's ``Y``);
* **default step arms** for leaf constructors named ``S``, ``K`` and
  ``I``, so that an interpreter which only adds a leaf writes only that
  leaf's arm (§6c, third bullet);
* a **fuel loop** for each interpreter core, from the declared step
  outcome type and result type.

Everything is generated as *surface syntax* -- ``ast.Arm`` declarations
appended to the program -- and then compiled by the ordinary expander.
Nothing here emits a term, so the generated code is exactly as
inspectable (and as renderable) as hand-written source, and the D-forms
it produces are the artifact's.

Any name the program already defines is left alone: a user-written
``sp``, ``step``, ``loop`` or ``stepErr`` overrides the generated one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from . import ast as A

__all__ = [
    "GenerateError", "ObjectType", "LoopTypes", "AnswerType", "PathType",
    "find_object_type", "find_loop_types", "find_answer_type",
    "find_path_type", "is_interpreter_core", "generate", "generated_names",
    "names_generation_adds",
]


class GenerateError(Exception):
    pass


# --------------------------------------------------------------- tiny helpers

def _n(name: str) -> A.Name:
    return A.Name(name)


def _ap(*parts) -> A.Expr:
    out = parts[0] if not isinstance(parts[0], str) else _n(parts[0])
    for p in parts[1:]:
        out = A.App(out, _n(p) if isinstance(p, str) else p)
    return out


def _arm(name: str, binders: Sequence[str], body: A.Expr) -> A.Arm:
    return A.Arm(name, tuple(binders), body)


# ----------------------------------------------------------- shape discovery

@dataclass(frozen=True)
class ObjectType:
    """A declared alphabet for a virtualizing interpreter."""
    decl: A.TypeDecl
    app: A.Ctor                      #: the binary self-referential ctor
    leaves: Tuple[A.Ctor, ...]       #: the nullary ctors, in declaration order

    @property
    def name(self) -> str:
        return self.decl.name

    def leaf_index(self, cname: str) -> int:
        for i, c in enumerate(self.leaves):
            if c.name == cname:
                return i
        raise KeyError(cname)


def find_object_type(program: A.Program) -> Optional[ObjectType]:
    """The program's object type, identified **by shape**: the unique
    declared type holding exactly one constructor with two fields of its
    own type.  Everything else in it must be nullary (a leaf).

    Returns ``None`` when no declared type has that shape -- an ordinary
    program, for which nothing below is generated.  Raises when a type
    has more than one such constructor, or when more than one type does.
    """
    found: List[ObjectType] = []
    for d in program.decls:
        if not isinstance(d, A.TypeDecl):
            continue
        apps = [c for c in d.ctors
                if len(c.fields) == 2 and all(f == d.name for f in c.fields)]
        if not apps:
            continue
        if len(apps) > 1:
            raise GenerateError(
                f"type {d.name!r} has {len(apps)} binary self-referential "
                f"constructors ({', '.join(c.name for c in apps)}); an object "
                f"type must have exactly one, the application constructor")
        others = [c for c in d.ctors if c is not apps[0]]
        bad = [c for c in others if c.fields]
        if bad:
            raise GenerateError(
                f"object type {d.name!r}: constructor(s) "
                f"{', '.join(c.name for c in bad)} carry fields; apart from "
                f"the application constructor every constructor must be a "
                f"leaf")
        found.append(ObjectType(d, apps[0], tuple(others)))
    if not found:
        return None
    if len(found) > 1:
        raise GenerateError(
            "more than one object type declared ("
            + ", ".join(o.name for o in found)
            + "); an interpreter walks one alphabet")
    return found[0]


@dataclass(frozen=True)
class LoopTypes:
    """The step-outcome type ``O`` and the result type ``R`` of a fuel
    loop, and the map between them."""
    outcome: A.TypeDecl
    result: A.TypeDecl
    stepped: A.Ctor          #: O's term-carrying ctor: continue the loop
    done: A.Ctor             #: O's first nullary ctor: no redex, success
    o_rest: Tuple[A.Ctor, ...]    #: O's other non-stepped ctors, in order
    value: A.Ctor            #: R's term-carrying ctor
    timeout: A.Ctor          #: R's last nullary ctor: fuel exhausted
    #: for each ctor of ``o_rest``, the R constructor it maps to
    mapping: Tuple[Tuple[str, str], ...] = ()

    @property
    def same(self) -> bool:
        return self.outcome.name == self.result.name

    def r_of(self, oname: str) -> str:
        for o, r in self.mapping:
            if o == oname:
                return r
        raise KeyError(oname)


def _carrier(d: A.TypeDecl, tname: str) -> Optional[Tuple[A.Ctor, Tuple[A.Ctor, ...]]]:
    """(the unique ctor carrying exactly one field of type ``tname``, the
    rest), or ``None`` if ``d`` does not have that shape.

    The other constructors may be nullary *or* carry fields of some other
    type: ``outcome ≡ SteppedN term5 ∣ DoneN ∣ ErrdN ∣ PendingN path``
    is outcome-shaped, and ``PendingN``'s payload is what makes blocking
    expressible at all.
    """
    if len(d.ctors) < 2:
        return None
    carry = [c for c in d.ctors if len(c.fields) == 1 and c.fields[0] == tname]
    if len(carry) != 1:
        return None
    return carry[0], tuple(c for c in d.ctors if c is not carry[0])


def find_loop_types(program: A.Program, obj: ObjectType) -> LoopTypes:
    """The step-outcome type ``O`` and the result type ``R``.

    A candidate is a declared type other than the object type with
    exactly one constructor carrying a single field of the object type
    and nothing else carrying fields.  The **first** candidate in
    declaration order is ``O``, the **last** is ``R``; with one candidate
    ``O = R``, which is the ``Maybe`` shape of ``whnfF``.
    """
    cands: List[Tuple[A.TypeDecl, A.Ctor, Tuple[A.Ctor, ...]]] = []
    for d in program.decls:
        if not isinstance(d, A.TypeDecl) or d.name == obj.name:
            continue
        got = _carrier(d, obj.name)
        if got is not None:
            cands.append((d, got[0], got[1]))
    if not cands:
        raise GenerateError(
            f"object type {obj.name!r} is declared but no step-outcome type "
            f"is: declare one, e.g. "
            f"'maybe === Nothing | Just {obj.name}'")
    if len(cands) == 1:
        od, stepped, o_rest = cands[0]
        rd, value = od, stepped
    else:
        # The *last two* outcome-shaped declarations are O and R.  A
        # program that also declares an oracle answer type -- which is
        # outcome-shaped too, `oanswer ≡ OJust term5 ∣ ONothing ∣ ONotYet`
        # -- declares it before them.
        od, stepped, o_rest = cands[-2]
        rd, value, _ = cands[-1]
    if len(od.ctors) != len(rd.ctors):
        raise GenerateError(
            f"outcome type {od.name!r} has {len(od.ctors)} constructors and "
            f"result type {rd.name!r} has {len(rd.ctors)}; the loop needs one "
            f"result constructor per outcome constructor (one terminal is "
            f"spent on the timeout)")
    return _build_loop_types(od, stepped, o_rest, rd, value)


def _build_loop_types(od, stepped, o_rest, rd, value) -> LoopTypes:
    """Work out which ``R`` constructor each ``O`` constructor maps to.

    ``SURFACE-LANGUAGE-DESIGN.md`` §6c's rule, extended for an outcome
    constructor that carries a payload:

    * ``O``'s first nullary constructor is "no redex", and yields ``R``'s
      term-carrying constructor applied to the current term;
    * an ``O`` constructor that carries a payload maps to ``R``'s
      constructor **at the same position**, which must carry one too, and
      is handed the same payload (``PendingN p`` -> ``RBlockN p``);
    * ``O``'s remaining nullary constructors map, in order, onto ``R``'s
      nullary constructors other than the timeout;
    * the timeout, returned at ``Zero`` fuel, is ``R``'s last nullary
      constructor.
    """
    r_nullary = [c for c in rd.ctors if not c.fields]
    if not r_nullary:
        raise GenerateError(
            f"result type {rd.name!r} has no nullary constructor, so the "
            f"loop has nothing to return when the fuel runs out")
    timeout = r_nullary[-1]
    spare = [c for c in r_nullary if c is not timeout and c is not value]
    nullary_o = [c for c in o_rest if not c.fields]
    if not nullary_o:
        raise GenerateError(
            f"outcome type {od.name!r} has no nullary constructor, so the "
            f"loop cannot tell when the term has no redex left")
    done = nullary_o[0]
    mapping: List[Tuple[str, str]] = [(done.name, value.name)]
    spare_i = 0
    for c in o_rest:
        if c is done:
            continue
        if c.fields:
            idx = list(od.ctors).index(c)
            if idx >= len(rd.ctors) or len(rd.ctors[idx].fields) != len(c.fields):
                raise GenerateError(
                    f"outcome constructor {c.name!r} carries "
                    f"{len(c.fields)} field(s), so the result type needs a "
                    f"constructor carrying as many at position {idx + 1}")
            mapping.append((c.name, rd.ctors[idx].name))
            continue
        if spare_i >= len(spare):
            raise GenerateError(
                f"outcome constructor {c.name!r} has no result constructor "
                f"left to map onto in {rd.name!r}")
        mapping.append((c.name, spare[spare_i].name))
        spare_i += 1
    return LoopTypes(outcome=od, result=rd, stepped=stepped, done=done,
                     o_rest=tuple(c for c in o_rest if c is not done),
                     value=value, timeout=timeout, mapping=tuple(mapping))


@dataclass(frozen=True)
class AnswerType:
    """The oracle's answer type: what a resolver returns.

    Found by shape, as the outcome-shaped declaration that is neither the
    step outcome nor the result -- `maybe ≡ Nothing ∣ Just term5` for
    `wfQ`, `oanswer ≡ OJust term5 ∣ ONothing ∣ ONotYet` for `wfN`.
    """
    decl: A.TypeDecl
    hit: A.Ctor              #: carries the answer
    notyet: A.Ctor           #: the last nullary ctor: no answer (yet)


def find_answer_type(program: A.Program, obj: ObjectType,
                     lt: LoopTypes) -> Optional[AnswerType]:
    spoken = {lt.outcome.name, lt.result.name}
    cands = []
    for d in program.decls:
        if not isinstance(d, A.TypeDecl) or d.name == obj.name:
            continue
        if d.name in spoken:
            continue
        got = _carrier(d, obj.name)
        if got is not None:
            cands.append((d, got[0]))
    if not cands:
        return None
    if len(cands) > 1:
        raise GenerateError(
            "more than one oracle answer type declared ("
            + ", ".join(d.name for d, _ in cands)
            + "); a namespace literal would not know which to build")
    d, hit = cands[0]
    nullary = [c for c in d.ctors if not c.fields]
    if not nullary:
        raise GenerateError(
            f"answer type {d.name!r} has no nullary constructor for 'no "
            f"answer'")
    return AnswerType(d, hit, nullary[-1])


@dataclass(frozen=True)
class PathType:
    """``path === Nil | Cons seg path``, found by name (``SYNTAX.md`` §6
    fixes the name and the shape)."""
    decl: A.TypeDecl
    nil: A.Ctor
    cons: A.Ctor
    seg: str                 #: the name of the segment type


def find_path_type(program: A.Program) -> Optional[PathType]:
    for d in program.decls:
        if not isinstance(d, A.TypeDecl) or d.name != "path":
            continue
        nils = [c for c in d.ctors if not c.fields]
        conses = [c for c in d.ctors
                  if len(c.fields) == 2 and c.fields[1] == d.name]
        if len(d.ctors) != 2 or len(nils) != 1 or len(conses) != 1:
            raise GenerateError(
                "the path type must be 'path === Nil | Cons seg path': a "
                "nullary constructor and one carrying a segment and a tail "
                "(SYNTAX.md §6)")
        return PathType(d, nils[0], conses[0], conses[0].fields[0])
    return None


def is_interpreter_core(core: A.Core, obj: ObjectType) -> bool:
    """A core is an interpreter core when it writes any part of the
    interface: ``step``, ``loop``, or a step arm for a leaf of the object
    type (``stepErr`` for the leaf ``Err``)."""
    names = {arm.name for arm in core.arms}
    if "step" in names or "loop" in names:
        return True
    # every constructor, not only the leaves, so that `stepApp` is seen
    # and refused by the checker rather than passing unnoticed
    return any("step" + c.name in names for c in obj.decl.ctors)


# ----------------------------------------------------------------- generation

#: the names this module may introduce at program level
def generated_names(obj: ObjectType) -> List[str]:
    out = ["spApp", "sp", "rb1", "rb"]
    out += ["res" + c.name for c in obj.leaves]
    for leaf in ("I", "K", "S"):
        if any(c.name == leaf for c in obj.leaves):
            out += _default_step_names(leaf)
    return out


def _default_step_names(leaf: str) -> List[str]:
    arity = {"I": 1, "K": 2, "S": 3}[leaf]
    return [f"step{leaf}{i}" for i in range(arity, 0, -1)] + [f"step{leaf}"]


def _walker_and_rebuilder(obj: ObjectType) -> List[A.Arm]:
    """``sp``, ``rb`` and their helpers, at this type's arity."""
    leaves = obj.leaves
    conts = [f"c{i}" for i in range(len(leaves))]
    out: List[A.Arm] = []
    # res<C> acc c0 .. cn = c_j acc      -- hand the collected args to the
    # caller's arm for the leaf the spine bottomed out at
    for j, c in enumerate(leaves):
        out.append(_arm("res" + c.name, ["acc"] + conts,
                        _ap(conts[j], "acc")))
    # spApp f acc t u = f t (cons u acc) -- descend the left spine,
    # pushing the argument
    out.append(_arm("spApp", ["f", "acc", "t", "u"],
                    _ap("f", "t", _ap("cons", "u", "acc"))))
    # sp m acc = m <one continuation per constructor, in declaration order>
    slots: List[A.Expr] = []
    for c in obj.decl.ctors:
        if c.name == obj.app.name:
            slots.append(_ap("spApp", "sp", "acc"))
        else:
            slots.append(_ap("res" + c.name, "acc"))
    out.append(_arm("sp", ["m", "acc"], _ap(_n("m"), *slots)))
    # rb1 f h x xs = f (App h x) xs ; rb h args = args h (rb1 rb h)
    out.append(_arm("rb1", ["f", "h", "x", "xs"],
                    _ap("f", _ap(obj.app.name, "h", "x"), "xs")))
    out.append(_arm("rb", ["h", "args"],
                    _ap(_n("args"), _n("h"), _ap("rb1", "rb", "h"))))
    return out


def _default_step_arms(obj: ObjectType, lt: LoopTypes) -> List[A.Arm]:
    """The ISA's own step arms, parameterized over the outcome type:
    "no redex" is O's first terminal and a contraction is wrapped in O's
    term-carrying constructor."""
    stepped, done, app = lt.stepped.name, lt.done.name, obj.app.name
    have = {c.name for c in obj.leaves}
    out: List[A.Arm] = []
    if "I" in have:
        out += [
            _arm("stepI1", ["x", "rest"], _ap(stepped, _ap("rb", "x", "rest"))),
            _arm("stepI", ["args"], _ap(_n("args"), _n(done), _n("stepI1"))),
        ]
    if "K" in have:
        out += [
            _arm("stepK2", ["x", "y", "rest"],
                 _ap(stepped, _ap("rb", "x", "rest"))),
            _arm("stepK1", ["x", "r"],
                 _ap(_n("r"), _n(done), _ap("stepK2", "x"))),
            _arm("stepK", ["args"], _ap(_n("args"), _n(done), _n("stepK1"))),
        ]
    if "S" in have:
        rebuilt = _ap(app, _ap(app, "x", "z"), _ap(app, "y", "z"))
        out += [
            _arm("stepS3", ["x", "y", "z", "rest"],
                 _ap(stepped, _ap("rb", rebuilt, _n("rest")))),
            _arm("stepS2", ["x", "y", "r2"],
                 _ap(_n("r2"), _n(done), _ap("stepS3", "x", "y"))),
            _arm("stepS1", ["x", "r"],
                 _ap(_n("r"), _n(done), _ap("stepS2", "x"))),
            _arm("stepS", ["args"], _ap(_n("args"), _n(done), _n("stepS1"))),
        ]
    return out


def _core_step_arm(obj: ObjectType, core: A.Core) -> A.Arm:
    """``step m = sp m nil stepC1 ... stepCn``, leaves in declaration
    order -- which is the order the walker hands them over.

    A step arm the *core* defines is passed the core's parameters, since
    an arm reference is raw; a program-level default arm is not.  That is
    the artifact's ``spQ m nil stepSQ stepKQ stepIQ (stepScQ e)``.
    """
    mine = {arm.name for arm in core.arms}
    slots = []
    for c in obj.leaves:
        nm = "step" + c.name
        slots.append(_ap(nm, *core.params) if nm in mine else _n(nm))
    return _arm("step", ["m"],
                _ap(_n("sp"), _n("m"), _n("nil"), *slots))


def _core_loop_arms(lt: LoopTypes, core: A.Core) -> List[A.Arm]:
    """The fuel loop, from O and R.

    ``loop1 f m n2 = step m <one continuation per O constructor, in
    declaration order>``: O's term-carrying constructor continues the
    loop with the new term and the remaining fuel; O's first terminal is
    "no redex", so the loop is done and returns R's term-carrying
    constructor applied to the current term; O's further terminals map
    one for one onto R's terminals.  ``loop n m = n <timeout>
    (loop1 loop m)`` peels one ``Suc`` per attempt and returns R's last
    terminal when the fuel is ``Zero``.
    """
    ps = list(core.params)
    conts: List[A.Expr] = []
    for c in lt.outcome.ctors:
        if c.name == lt.stepped.name:
            conts.append(_ap(_n("f"), *[_n(x) for x in ps], _n("n2")))
        elif c.name == lt.done.name:
            conts.append(_ap(lt.value.name, "m"))
        else:
            conts.append(_n(lt.r_of(c.name)))
    return [
        _arm("loop1", ["f", "m", "n2"],
             _ap(_ap("step", *ps), _n("m"), *conts)),
        _arm("loop", ["n", "m"],
             _ap(_n("n"), _n(lt.timeout.name),
                 _ap(_ap("loop1", *ps), _n("loop"), _n("m")))),
    ]


def names_generation_adds(program: A.Program):
    """What :func:`generate` will supply, without generating it: the
    program-level names, and the extra arms of each interpreter core.

    The checker needs this so it can be a pass over the *parsed* program
    -- it must not call an arm undefined when generation is about to
    define it.
    """
    obj = find_object_type(program)
    if obj is None:
        return set(), {}
    taken = set()
    for d in program.decls:
        if isinstance(d, A.TypeDecl):
            taken.update(c.name for c in d.ctors)
        elif isinstance(d, (A.Arm, A.Macro, A.Def, A.Core)):
            taken.add(d.name)
    top = {n for n in generated_names(obj) if n not in taken}
    per_core = {}
    for d in program.decls:
        if isinstance(d, A.Core) and is_interpreter_core(d, obj):
            have = {arm.name for arm in d.arms}
            extra = set()
            if "step" not in have:
                extra.add("step")
            if "loop" not in have:
                extra |= {"loop", "loop1"}
            per_core[d.name] = extra
    return top, per_core


def generate(program: A.Program) -> A.Program:
    """Return ``program`` with the type-generated forms added.

    A no-op when the program declares no object type.
    """
    obj = find_object_type(program)
    if obj is None:
        return program
    lt = find_loop_types(program, obj)

    taken: Set[str] = set()
    for d in program.decls:
        if isinstance(d, A.TypeDecl):
            taken.update(c.name for c in d.ctors)
        elif isinstance(d, (A.Sig,)):
            pass
        elif isinstance(d, (A.Arm, A.Macro, A.Def, A.Core)):
            taken.add(d.name)

    extra = [x for x in _walker_and_rebuilder(obj) + _default_step_arms(obj, lt)
             if x.name not in taken]

    decls: List[A.Decl] = []
    for d in program.decls:
        if isinstance(d, A.Core) and is_interpreter_core(d, obj):
            decls.append(_fill_core(d, obj, lt))
        else:
            decls.append(d)
    return A.Program(tuple(decls + extra))


def _fill_core(core: A.Core, obj: ObjectType, lt: LoopTypes) -> A.Core:
    have = {arm.name for arm in core.arms}
    added: List[A.Arm] = []
    if "step" not in have:
        added.append(_core_step_arm(obj, core))
    if "loop" not in have:
        if "loop1" in have:
            raise GenerateError(
                f"core {core.name!r} writes 'loop1' but not 'loop'; write "
                f"both or neither")
        added += _core_loop_arms(lt, core)
    return A.Core(core.name, tuple(list(core.arms) + added), core.params)
