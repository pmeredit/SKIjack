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
    "GenerateError", "ObjectType", "LoopTypes",
    "find_object_type", "find_loop_types", "is_interpreter_core",
    "generate", "generated_names",
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
    """The step-outcome type and the result type of a fuel loop."""
    outcome: A.TypeDecl
    result: A.TypeDecl
    stepped: A.Ctor          #: O's term-carrying ctor: continue the loop
    done: A.Ctor             #: O's first terminal: no redex, success
    o_rest: Tuple[A.Ctor, ...]    #: O's remaining terminals, in order
    value: A.Ctor            #: R's term-carrying ctor
    r_rest: Tuple[A.Ctor, ...]    #: R's terminals, in order
    timeout: A.Ctor          #: R's last terminal: fuel exhausted

    @property
    def same(self) -> bool:
        return self.outcome.name == self.result.name


def _carrier(d: A.TypeDecl, tname: str) -> Optional[Tuple[A.Ctor, Tuple[A.Ctor, ...]]]:
    """(the unique ctor carrying one field of type ``tname``, the rest),
    or ``None`` if ``d`` does not have that shape."""
    if len(d.ctors) < 2:
        return None
    carry = [c for c in d.ctors if len(c.fields) == 1 and c.fields[0] == tname]
    if len(carry) != 1:
        return None
    rest = tuple(c for c in d.ctors if c is not carry[0])
    if any(c.fields for c in rest):
        return None
    return carry[0], rest


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
    if len(cands) > 2:
        raise GenerateError(
            "more than two outcome-shaped types declared ("
            + ", ".join(d.name for d, _, _ in cands)
            + "); this generator supports the two shapes the artifact uses: "
              "O = R = Maybe, or O = Stepped|Done|Errd with "
              "R = RVal|RErr|RTime")
    od, stepped, o_rest = cands[0]
    rd, value, r_rest = cands[-1]
    if len(od.ctors) != len(rd.ctors):
        raise GenerateError(
            f"outcome type {od.name!r} has {len(od.ctors)} constructors and "
            f"result type {rd.name!r} has {len(rd.ctors)}; the loop needs one "
            f"result constructor per outcome constructor (one terminal is "
            f"spent on the timeout)")
    return LoopTypes(outcome=od, result=rd, stepped=stepped, done=o_rest[0],
                     o_rest=o_rest[1:], value=value, r_rest=r_rest,
                     timeout=r_rest[-1])


def is_interpreter_core(core: A.Core, obj: ObjectType) -> bool:
    """A core is an interpreter core when it writes any part of the
    interface: ``step``, ``loop``, or a step arm for a leaf of the object
    type (``stepErr`` for the leaf ``Err``)."""
    names = {arm.name for arm in core.arms}
    if "step" in names or "loop" in names:
        return True
    return any("step" + c.name in names for c in obj.leaves)


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


def _core_step_arm(obj: ObjectType) -> A.Arm:
    """``step m = sp m nil stepC1 ... stepCn``, leaves in declaration
    order -- which is the order the walker hands them over."""
    return _arm("step", ["m"],
                _ap(_n("sp"), _n("m"), _n("nil"),
                    *[_n("step" + c.name) for c in obj.leaves]))


def _core_loop_arms(lt: LoopTypes) -> List[A.Arm]:
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
    conts: List[A.Expr] = []
    rest_iter = list(lt.r_rest)
    for c in lt.outcome.ctors:
        if c.name == lt.stepped.name:
            conts.append(_ap("f", "n2"))
        elif c.name == lt.done.name:
            conts.append(_ap(lt.value.name, "m"))
        else:
            idx = [x.name for x in lt.o_rest].index(c.name)
            conts.append(_n(rest_iter[idx].name))
    return [
        _arm("loop1", ["f", "m", "n2"], _ap(_n("step"), _n("m"), *conts)),
        _arm("loop", ["n", "m"],
             _ap(_n("n"), _n(lt.timeout.name), _ap("loop1", "loop", "m"))),
    ]


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
        added.append(_core_step_arm(obj))
    if "loop" not in have:
        if "loop1" in have:
            raise GenerateError(
                f"core {core.name!r} writes 'loop1' but not 'loop'; write "
                f"both or neither")
        added += _core_loop_arms(lt)
    return A.Core(core.name, tuple(list(core.arms) + added))
