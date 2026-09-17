"""The code generator: syntax tree -> closed ``{S,K,I}`` terms.

Scope of this step: no types (Stage B, ``DESIDERATA.md`` item 11) and no
quotation / level-1 packaging (``SURFACE-LANGUAGE-DESIGN.md`` §6a).  A
``Quote``, ``Scry`` or ``NsLit`` reaching the code generator is a clear
:class:`ExpandError`.

The passes, in order:

1. **macro expansion** -- ``:=*`` macros are rewritten at each use site
   with all parameters supplied; substitution is capture avoiding.
   ``:=!`` is refused.
2. **case forms** -- ``x |> { C1 bs1 b1 ; ... }`` becomes ``x`` applied
   to one continuation per constructor *in declaration order*, each
   continuation the body abstracted over its binders.
3. **cells and picks** -- ``[a b]`` is ``pair a b``; ``2@p`` is ``hd p``
   and ``3@p`` is ``tl p``, and axis ``n`` in general is the chain of
   heads and tails Nock's numbering gives.
4. **cores** -- per-arm fixpoints: a self-recursive arm becomes
   ``Y gen`` where ``gen`` takes the arm itself as its first parameter,
   the way ``tower_harness.py`` writes ``wfGen``/``whnfF``.  A
   non-recursive arm is a plain ``D``.  Every lambda (a case branch with
   binders, or a ``\\x.e``) is lambda-lifted into its own supercombinator
   over the enclosing binders that occur free in it.
5. **bracket abstraction** -- ``aviary_kernel.abstraction.expand`` by way
   of the artifact's ``D`` / ``AL`` idiom.  Nothing here reimplements it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from aviary_kernel.abstraction import expand as _ski_expand
from aviary_kernel.birds import BY_NAME
from aviary_kernel.environment import Environment
from aviary_kernel.terms import Atom, App as KApp, Term, pretty, size

from . import ast as A
from .generate import generate as _generate

__all__ = ["ExpandError", "Expansion", "expand_program", "PRELUDE_NAMES",
           "ISA_NAMES"]


class ExpandError(Exception):
    pass


def a(name: str) -> Atom:
    return Atom(name)


v = a


def K_(*terms: Term) -> Term:
    r = terms[0]
    for t in terms[1:]:
        r = KApp(r, t)
    return r


#: names the expander installs before the program is seen.  ``pair`` /
#: ``hd`` / ``tl`` are the Scott pair and its projections
#: (``SURFACE-LANGUAGE-DESIGN.md`` §2); the rest are the aviary kernel's
#: own built-ins, reached by name.
PRELUDE_NAMES = ("pair", "hd", "tl", "nil", "cons")

#: the three primitives.  ``SURFACE-LANGUAGE-DESIGN.md`` §6b keeps two
#: symbol tables: outside quotation these names are the ISA, inside it
#: they are the object type's constructors.  Quotation is a later step,
#: so here they are always the ISA -- which is what ``EXAMPLES.md`` §4
#: means by "outside it they would be the level-0 combinators" even
#: though ``term5 === S | K | I | ...`` declares constructors of those
#: names.
ISA_NAMES = ("S", "K", "I")

#: aviary kernel built-ins a program may name directly
_BUILTIN_OK = set(BY_NAME)


# ---------------------------------------------------------------- utilities

def free_names(e: A.Expr) -> Set[str]:
    """Names occurring free in an expression (binders of ``Lambda`` and of
    case branches bind)."""
    if isinstance(e, A.Name):
        return {e.name}
    if isinstance(e, A.App):
        return free_names(e.fn) | free_names(e.arg)
    if isinstance(e, A.Cell):
        out: Set[str] = set()
        for x in e.items:
            out |= free_names(x)
        return out
    if isinstance(e, A.Pick):
        return free_names(e.expr)
    if isinstance(e, A.Lambda):
        return free_names(e.body) - {e.param}
    if isinstance(e, A.Case):
        out = free_names(e.scrutinee)
        for cname, binders, body in e.branches:
            out |= {cname}
            out |= (free_names(body) - set(binders))
        return out
    if isinstance(e, A.Quote):
        out = free_names(e.expr)
        if e.interp is not None:
            out |= free_names(e.interp)
        return out
    if isinstance(e, A.Scry):
        return _path_names(e.path)
    if isinstance(e, A.NsLit):
        out = set()
        for p, val in e.facts:
            out |= _path_names(p) | free_names(val)
        return out
    raise TypeError(f"free_names: {e!r}")


def _path_names(p: A.Path) -> Set[str]:
    out: Set[str] = set()
    for seg in p.segments:
        if seg.payload is not None:
            out |= free_names(seg.payload)
    return out


def _fresh(base: str, taken: Set[str]) -> str:
    if base not in taken:
        return base
    i = 0
    while f"{base}{i}" in taken:
        i += 1
    return f"{base}{i}"


def substitute(e: A.Expr, sub: Dict[str, A.Expr]) -> A.Expr:
    """Capture-avoiding substitution of names by expressions."""
    if not sub:
        return e
    if isinstance(e, A.Name):
        return sub.get(e.name, e)
    if isinstance(e, A.App):
        return A.App(substitute(e.fn, sub), substitute(e.arg, sub))
    if isinstance(e, A.Cell):
        return A.Cell(tuple(substitute(x, sub) for x in e.items))
    if isinstance(e, A.Pick):
        return A.Pick(e.axis, substitute(e.expr, sub))
    if isinstance(e, A.Lambda):
        param, body = _rename_binders(e.param, e.body, sub)
        inner = {k: t for k, t in sub.items() if k != param}
        return A.Lambda(param, substitute(body, inner))
    if isinstance(e, A.Case):
        branches = []
        for cname, binders, body in e.branches:
            nb = list(binders)
            for i, b in enumerate(binders):
                nb[i], body = _rename_binders(b, body, sub)
            inner = {k: t for k, t in sub.items() if k not in nb}
            branches.append((cname, tuple(nb), substitute(body, inner)))
        return A.Case(substitute(e.scrutinee, sub), tuple(branches))
    if isinstance(e, A.Quote):
        return A.Quote(substitute(e.expr, sub), e.fuel,
                       None if e.interp is None else substitute(e.interp, sub))
    if isinstance(e, (A.Scry, A.NsLit)):
        raise ExpandError(
            "quotation, scry and namespace literals are not handled by this "
            "step of the expander")
    raise TypeError(f"substitute: {e!r}")


def _rename_binders(binder: str, body: A.Expr, sub: Dict[str, A.Expr]):
    """Alpha-rename ``binder`` if it would capture a name free in one of
    the substituted expressions."""
    danger: Set[str] = set()
    for k, t in sub.items():
        if k == binder:
            continue
        if k in free_names(body):
            danger |= free_names(t)
    if binder not in danger:
        return binder, body
    taken = danger | free_names(body) | set(sub)
    fresh = _fresh(binder + "_", taken)
    return fresh, substitute(body, {binder: A.Name(fresh)})


# ------------------------------------------------------------- pass 1: macros

_MACRO_FUEL = 100


def _spine(e: A.Expr) -> Tuple[A.Expr, List[A.Expr]]:
    args: List[A.Expr] = []
    while isinstance(e, A.App):
        args.append(e.arg)
        e = e.fn
    args.reverse()
    return e, args


def expand_macros(e: A.Expr, macros: Dict[str, A.Macro], depth: int = 0) -> A.Expr:
    if depth > _MACRO_FUEL:
        raise ExpandError("macro expansion did not reach a fixpoint")
    if isinstance(e, A.Name):
        if e.name in macros:
            m = macros[e.name]
            if m.params:
                raise ExpandError(
                    f"macro {m.name!r} takes {len(m.params)} parameter(s); "
                    f"partial application of a macro is an error")
            return expand_macros(m.body, macros, depth + 1)
        return e
    if isinstance(e, A.App):
        head, args = _spine(e)
        if isinstance(head, A.Name) and head.name in macros:
            m = macros[head.name]
            if m.capturing:
                raise ExpandError(
                    f"macro {m.name!r} is declared capturing (':=!'); the "
                    f"capturing form is not implemented")
            n = len(m.params)
            if len(args) < n:
                raise ExpandError(
                    f"macro {m.name!r} takes {n} parameter(s) but got "
                    f"{len(args)}; partial application of a macro is an error")
            args = [expand_macros(x, macros, depth + 1) for x in args]
            body = substitute(m.body, dict(zip(m.params, args[:n])))
            out = expand_macros(body, macros, depth + 1)
            for extra in args[n:]:
                out = A.App(out, extra)
            return out
        return A.App(expand_macros(e.fn, macros, depth + 1),
                     expand_macros(e.arg, macros, depth + 1))
    if isinstance(e, A.Cell):
        return A.Cell(tuple(expand_macros(x, macros, depth + 1) for x in e.items))
    if isinstance(e, A.Pick):
        return A.Pick(e.axis, expand_macros(e.expr, macros, depth + 1))
    if isinstance(e, A.Lambda):
        inner = {k: m for k, m in macros.items() if k != e.param}
        return A.Lambda(e.param, expand_macros(e.body, inner, depth + 1))
    if isinstance(e, A.Case):
        branches = []
        for cname, binders, body in e.branches:
            inner = {k: m for k, m in macros.items() if k not in binders}
            branches.append((cname, binders,
                             expand_macros(body, inner, depth + 1)))
        return A.Case(expand_macros(e.scrutinee, macros, depth + 1),
                      tuple(branches))
    if isinstance(e, (A.Quote, A.Scry, A.NsLit)):
        raise ExpandError(
            "quotation, scry and namespace literals are out of scope for "
            "this step of the expander")
    raise TypeError(f"expand_macros: {e!r}")


# ------------------------------------------ pass 2 and 3: cases, cells, picks

def axis_chain(n: int) -> List[str]:
    """The head/tail chain for Nock axis ``n``, outermost last.

    Axis 1 is the whole; axis ``2n`` is the head of axis ``n`` and
    ``2n+1`` its tail, so the bits of ``n`` below the leading one spell
    the walk from the root: 0 for ``hd``, 1 for ``tl``.
    """
    if n < 1:
        raise ExpandError(f"axis {n} does not exist; axes start at 1")
    bits = bin(n)[3:]          # drop '0b1'
    return ["hd" if b == "0" else "tl" for b in bits]


def lower(e: A.Expr, ctors: Dict[str, Tuple[str, int, int]],
          types: Dict[str, A.TypeDecl]) -> A.Expr:
    """Passes 2 and 3: case forms, cells and picks become applications."""
    if isinstance(e, A.Name):
        return e
    if isinstance(e, A.App):
        return A.App(lower(e.fn, ctors, types), lower(e.arg, ctors, types))
    if isinstance(e, A.Lambda):
        return A.Lambda(e.param, lower(e.body, ctors, types))
    if isinstance(e, A.Cell):
        items = [lower(x, ctors, types) for x in e.items]
        out = items[-1]
        for x in reversed(items[:-1]):
            out = A.App(A.App(A.Name("pair"), x), out)
        return out
    if isinstance(e, A.Pick):
        out = lower(e.expr, ctors, types)
        for step in axis_chain(e.axis):
            out = A.App(A.Name(step), out)
        return out
    if isinstance(e, A.Case):
        return _lower_case(e, ctors, types)
    raise ExpandError(f"cannot compile {type(e).__name__} in this step")


def _lower_case(e: A.Case, ctors, types) -> A.Expr:
    if not e.branches:
        raise ExpandError("a case form needs at least one branch")
    first = e.branches[0][0]
    if first not in ctors:
        raise ExpandError(f"undeclared constructor {first!r} in a case branch")
    tname = ctors[first][0]
    decl = types[tname]
    seen: Dict[str, Tuple[Tuple[str, ...], A.Expr]] = {}
    for cname, binders, body in e.branches:
        if cname not in ctors or ctors[cname][0] != tname:
            raise ExpandError(
                f"case branch {cname!r} is not a constructor of {tname!r}")
        if cname in seen:
            raise ExpandError(f"case branch {cname!r} appears twice")
        seen[cname] = (binders, body)
    missing = [c.name for c in decl.ctors if c.name not in seen]
    if missing:
        raise ExpandError(
            f"case over {tname!r} is missing branch(es) for "
            f"{', '.join(missing)}; case must be complete "
            f"(DESIDERATA.md item 11, Stage A)")
    out = lower(e.scrutinee, ctors, types)
    for c in decl.ctors:                     # declaration order is the ABI
        binders, body = seen[c.name]
        k = lower(body, ctors, types)
        for b in reversed(binders):
            k = A.Lambda(b, k)
        out = A.App(out, k)
    return out


# --------------------------------------------------- passes 4 and 5: codegen

@dataclass
class Expansion:
    """The result of :func:`expand_program`."""
    terms: Dict[str, Term] = field(default_factory=dict)
    sizes: Dict[str, int] = field(default_factory=dict)
    helpers: Dict[str, Term] = field(default_factory=dict)
    backend: Dict[str, str] = field(default_factory=dict)
    env: Optional[Environment] = None
    types: Dict[str, A.TypeDecl] = field(default_factory=dict)
    ctors: Dict[str, Tuple[str, int, int]] = field(default_factory=dict)

    def term(self, name: str) -> Term:
        return self.terms[name]

    def size(self, name: str) -> int:
        return self.sizes[name]

    def text(self, name: str) -> str:
        return pretty(self.terms[name])


class _Codegen:
    def __init__(self, env: Environment, resolve, helper_names=None):
        self.env = env
        self.resolve = resolve          # source name -> backend Atom, or None
        self.helper_names: List[str] = ([] if helper_names is None
                                        else helper_names)

    def with_resolver(self, resolve) -> "_Codegen":
        """The same code generator under a different name environment --
        one per core, so a core's arms see their siblings first."""
        return _Codegen(self.env, resolve, self.helper_names)

    def gen(self, e: A.Expr, scope: Sequence[str], owner: str) -> Term:
        """Compile ``e``; ``scope`` is the enclosing binder list in order."""
        if isinstance(e, A.Name):
            if e.name in scope:
                return v(e.name)
            t = self.resolve(e.name)
            if t is None:
                raise ExpandError(
                    f"unresolved name {e.name!r} in {owner!r}; free variables "
                    f"do not exist at runtime (SYNTAX.md §8)")
            return t
        if isinstance(e, A.App):
            return KApp(self.gen(e.fn, scope, owner),
                        self.gen(e.arg, scope, owner))
        if isinstance(e, A.Lambda):
            return self.lift(e, scope, owner)
        raise ExpandError(f"cannot compile {type(e).__name__} in {owner!r}")

    def lift(self, lam: A.Lambda, scope: Sequence[str], owner: str) -> Term:
        """Lambda-lift a lambda chain into its own supercombinator."""
        params: List[str] = []
        body: A.Expr = lam
        while isinstance(body, A.Lambda):
            params.append(body.param)
            body = body.body
        fv = free_names(body) - set(params)
        captured = [s for s in scope if s in fv]
        name = _fresh_name(f"{owner}_b", self.env, len(self.helper_names))
        inner_scope = list(captured) + params
        term = self.gen(body, inner_scope, owner)
        self.env.define_rule(name, tuple(inner_scope), term)
        self.helper_names.append(name)
        out: Term = a(name)
        for c in captured:
            out = KApp(out, v(c))
        return out


_counter = {"n": 0}


def _fresh_name(base: str, env: Environment, _i: int) -> str:
    _counter["n"] += 1
    name = f"{base}{_counter['n']}"
    while env.lookup(name) is not None:
        _counter["n"] += 1
        name = f"{base}{_counter['n']}"
    return name


def _mangle(name: str, used: Set[str]) -> str:
    """A backend name for a source name.

    The aviary kernel refuses to shadow a built-in bird, so an arm called
    ``C`` is defined as ``Cc`` (the form recorded in ``EXAMPLES.md``'s
    codegen notes).  The mangling never changes the compiled term.
    """
    cand = name
    while cand in BY_NAME or cand in used:
        cand = cand + name[0].lower()
    return cand


# -------------------------------------------------------------- the driver

def expand_program(program: A.Program, env: Optional[Environment] = None,
                   generate_forms: bool = True) -> Expansion:
    """Compile a program to closed ``{S,K,I}`` terms, one per name.

    With ``generate_forms`` (the default), :func:`skijack.generate.generate`
    first adds the type-generated forms -- the walker, the rebuilder, the
    default ISA step arms and each interpreter core's ``step`` and fuel
    loop -- as surface declarations.
    """
    if env is None:
        env = Environment()
    _counter["n"] = 0
    if generate_forms:
        program = _generate(program)

    # --- collect declarations
    types: Dict[str, A.TypeDecl] = {}
    ctors: Dict[str, Tuple[str, int, int]] = {}
    macros: Dict[str, A.Macro] = {}
    arms: List[Tuple[str, A.Arm, Optional[str]]] = []   # (name, arm, core)
    cores: Dict[str, A.Core] = {}
    defs: List[A.Def] = []
    for d in program.decls:
        if isinstance(d, A.TypeDecl):
            if d.name in types:
                raise ExpandError(f"type {d.name!r} declared twice")
            types[d.name] = d
            for idx, c in enumerate(d.ctors):
                if c.name in ctors:
                    raise ExpandError(f"constructor {c.name!r} declared twice")
                ctors[c.name] = (d.name, idx, len(c.fields))
        elif isinstance(d, A.Macro):
            macros[d.name] = d
        elif isinstance(d, A.Sig):
            pass                       # Stage B; parsed, kept, ignored
        elif isinstance(d, A.Arm):
            arms.append((d.name, d, None))
        elif isinstance(d, A.Core):
            if d.name in cores:
                raise ExpandError(f"core {d.name!r} declared twice")
            cores[d.name] = d
            seen_arm: Set[str] = set()
            for arm in d.arms:
                if arm.name in seen_arm:
                    raise ExpandError(
                        f"core {d.name!r} defines arm {arm.name!r} twice")
                seen_arm.add(arm.name)
                arms.append((arm.name, arm, d.name))
        elif isinstance(d, A.Def):
            defs.append(d)
        else:
            raise ExpandError(f"unknown declaration {d!r}")

    # --- the prelude: the Scott pair and its projections
    backend: Dict[str, str] = {}
    used: Set[str] = set()
    for nm in PRELUDE_NAMES:
        backend[nm] = nm
        used.add(nm)
    env.define_rule("pair", ("x", "y", "c"), K_(v("c"), v("x"), v("y")))
    env.define_rule("hd", ("p",), K_(v("p"), a("K")))
    env.define_rule("tl", ("p",), K_(v("p"), K_(a("K"), a("I"))))
    env.define_rule("nil", ("n", "c"), v("n"))
    env.define_rule("cons", ("h", "t", "n", "c"), K_(v("c"), v("h"), v("t")))

    # --- backend names.  Program-level names (constructors, top-level
    # arms, definitions, the prelude) share one namespace; a core's arms
    # get their own, so two interpreter cores can each have a `step`.
    source_names: List[str] = []
    for tdecl in types.values():
        for c in tdecl.ctors:
            source_names.append(c.name)
    for name, _arm, core in arms:
        if core is None:
            source_names.append(name)
    for d in defs:
        source_names.append(d.name)
    seen_source: Set[str] = set()
    for nm in source_names:
        if nm in seen_source:
            raise ExpandError(f"{nm!r} is defined twice")
        seen_source.add(nm)
        if nm in PRELUDE_NAMES:
            # the program supplies its own pair / hd / tl / nil / cons; keep
            # the name so cells, picks and the walker still reach it, and let
            # the definition below replace the prelude's.
            continue
        backend[nm] = _mangle(nm, used)
        used.add(backend[nm])

    #: (core, arm) -> backend name, and core -> {arm name}
    arm_backend: Dict[Tuple[str, str], str] = {}
    core_arms: Dict[str, Set[str]] = {c: set() for c in cores}
    for name, _arm, core in arms:
        if core is None:
            continue
        core_arms[core].add(name)
        arm_backend[(core, name)] = _mangle(f"{core}_{name}", used)
        used.add(arm_backend[(core, name)])

    # an interpreter core's own name denotes its fuel loop
    for cname, core in cores.items():
        if (cname, "loop") in arm_backend and cname not in backend:
            backend[cname] = arm_backend[(cname, "loop")]

    def resolver(core: Optional[str]):
        """Name resolution inside ``core`` (``None`` at top level):
        binders, then this core's sibling arms, then program-level names,
        then the aviary built-ins.  ``S``, ``K`` and ``I`` are always the
        ISA at level 0 (``SURFACE-LANGUAGE-DESIGN.md`` §6b)."""
        def resolve(nm: str) -> Optional[Term]:
            if nm in ISA_NAMES:
                return a(nm)
            if core is not None and nm in core_arms[core]:
                return a(arm_backend[(core, nm)])
            if nm in backend:
                return a(backend[nm])
            if nm in _BUILTIN_OK:
                return a(nm)
            return None
        return resolve

    resolve = resolver(None)

    # --- the constructors, from the type declarations
    for tdecl in types.values():
        n = len(tdecl.ctors)
        conts = [f"c{i}" for i in range(n)]
        for idx, c in enumerate(tdecl.ctors):
            fields = [f"f{i}" for i in range(len(c.fields))]
            body: Term = v(conts[idx])
            for f in fields:
                body = KApp(body, v(f))
            env.define_rule(backend[c.name], tuple(fields + conts), body)

    cg = _Codegen(env, resolve)

    # --- passes 1..3 on every arm body, then codegen
    lowered: Dict[Tuple[Optional[str], str], A.Arm] = {}
    for name, arm, core in arms:
        body = expand_macros(arm.body, macros)
        body = lower(body, ctors, types)
        lowered[(core, name)] = A.Arm(name, arm.binders, body)

    def _key_of(core: Optional[str], nm: str):
        """Which arm a name refers to from inside ``core``: a sibling
        first, then a top-level arm."""
        if core is not None and nm in core_arms[core] and (core, nm) in lowered:
            return (core, nm)
        if (None, nm) in lowered:
            return (None, nm)
        return None

    def _dep_keys(key):
        core, _name = key
        arm = lowered[key]
        free = free_names(arm.body) - set(arm.binders)
        out_ = set()
        for nm in free:
            if nm in ISA_NAMES:
                continue
            k = _key_of(core, nm)
            if k is not None:
                out_.add(k)
        return out_

    # --- pass 4: recursion.  Per-arm fixpoint; mutual recursion is refused.
    for key in lowered:
        for okey in _dep_keys(key):
            if okey == key:
                continue
            if key in _dep_keys(okey):
                raise ExpandError(
                    f"arms {key[1]!r} and {okey[1]!r} are mutually recursive; "
                    f"this expander ties one fixpoint per arm and cannot "
                    f"compile mutual recursion yet")

    for key, arm in lowered.items():
        core, name = key
        bname = backend[name] if core is None else arm_backend[key]
        gen = cg.with_resolver(resolver(core))
        recursive = key in _dep_keys(key)
        if recursive:
            selfp = _fresh("f", set(arm.binders) | free_names(arm.body))
            body = substitute(arm.body, {name: A.Name(selfp)})
            scope = [selfp] + list(arm.binders)
            gen_name = _mangle(bname + "Gen", used)
            used.add(gen_name)
            term = gen.gen(body, scope, bname)
            env.define_rule(gen_name, tuple(scope), term)
            env.define_alias(bname, K_(a("Y"), a(gen_name)))
        else:
            scope = list(arm.binders)
            term = gen.gen(arm.body, scope, bname)
            env.define_rule(bname, tuple(scope), term)

    # --- plain definitions (``name := expr``)
    for d in defs:
        body = expand_macros(d.expr, macros)
        body = lower(body, ctors, types)
        term = cg.gen(body, [], backend[d.name])
        env.define_alias(backend[d.name], term)

    # --- pass 5: bracket abstraction
    out = Expansion(env=env, backend=dict(backend), types=dict(types),
                    ctors=dict(ctors))
    names = list(dict.fromkeys(list(source_names) + list(PRELUDE_NAMES)))
    for nm in names:
        t = _ski_expand(a(backend[nm]), env)
        out.terms[nm] = t
        out.sizes[nm] = size(t)
    # core arms are always reachable as "core.arm", and as the bare name
    # when that name is unambiguous across the whole program
    bare_count: Dict[str, int] = {}
    for (core, name) in lowered:
        if core is not None:
            bare_count[name] = bare_count.get(name, 0) + 1
    for (core, name), _arm in lowered.items():
        if core is None:
            continue
        t = _ski_expand(a(arm_backend[(core, name)]), env)
        out.terms[f"{core}.{name}"] = t
        out.sizes[f"{core}.{name}"] = size(t)
        if bare_count[name] == 1 and name not in out.terms:
            out.terms[name] = t
            out.sizes[name] = size(t)
    # an interpreter core's name denotes its fuel loop
    for cname in cores:
        if (cname, "loop") in lowered:
            out.terms[cname] = out.terms[f"{cname}.loop"]
            out.sizes[cname] = out.sizes[f"{cname}.loop"]
    for h in cg.helper_names:
        out.helpers[h] = _ski_expand(a(h), env)
    return out
