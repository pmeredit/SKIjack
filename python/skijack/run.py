"""Running a compiled program, at level 0 and at level 1.

``SURFACE-LANGUAGE-DESIGN.md`` §6: level 0 hands the term to the host
reducer as is; level 1 hands it ``interp fuel <program>`` and reads the
interpreter's outcome type.

Everything that reads a value here reads it **behaviorally** -- by
applying it to fresh marker atoms and seeing which one comes back --
never by inspecting combinator syntax.  :func:`decode` walks a quoted
datum that way and rebuilds the surface term, memoizing by node identity
with the node held (the id-recycling trap fixed in :mod:`skijack.probe`).

:func:`run_policy` is the fuel policy of ``RUNTIME-DESIGN.md`` §3c for
elided fuel ``<t>@[]``: iterative deepening, doubling the budget until a
value or a configured cap, with the cap reported as the timeout outcome
and never hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from aviary_kernel.environment import Environment
from aviary_kernel.reduce import Status
from aviary_kernel.terms import App, Atom, Term, pretty

from . import ast as A
from .expand import Expansion, Level1Program, resolver_term
from .generate import ObjectType
from .probe import fast_reduce
from .render import render_ascii

__all__ = ["RunError", "Outcome", "PolicyResult", "NamespaceRun",
           "run_level0", "run_level1", "peel", "decode", "run_policy",
           "make_resolver", "run_with_namespace", "block_constructor",
           "timeout_constructor", "DEFAULT_CAP"]


from .errors import SkijackError

class RunError(SkijackError):
    pass


#: the runtime's default ceiling for iterative deepening
DEFAULT_CAP = 4096


@dataclass
class Outcome:
    """What the host reducer did, plus what it produced."""
    term: Term
    status: Status
    steps: int

    @property
    def whnf(self) -> bool:
        return self.status in (Status.WHNF, Status.NORMAL)


def _ap(*ts: Term) -> Term:
    r = ts[0]
    for t in ts[1:]:
        r = App(r, t)
    return r


def _fresh_env() -> Environment:
    """Reduction happens with no definitions at all: the terms are closed
    ``{S,K,I}``, so the only atoms that can appear in a result are the
    three primitives and the markers we supplied."""
    return Environment()


def run_level0(term: Term, max_steps: int = 100_000, *,
               whnf_only: bool = True, env: Optional[Environment] = None
               ) -> Outcome:
    """Reduce a level-0 term directly (§6, "Level 0, direct")."""
    r = fast_reduce(term, env or _fresh_env(), whnf_only=whnf_only,
                    max_steps=max_steps)
    return Outcome(r.term, r.status, r.steps)


def run_level1(packaged, max_steps: int = 1_000_000, *,
               fuel: Optional[int] = None,
               env: Optional[Environment] = None) -> Outcome:
    """Reduce ``interp fuel <program>`` (§6, "Level 1, virtualized").

    ``packaged`` is a :class:`~skijack.expand.Level1Program` or a term
    already closed over its fuel.  ``fuel`` overrides the declaration's.
    """
    if isinstance(packaged, Level1Program):
        if fuel is not None:
            term = packaged.with_fuel(fuel)
        else:
            term = packaged.term
    else:
        if fuel is not None:
            raise RunError("fuel can only be supplied for a Level1Program")
        term = packaged
    return run_level0(term, max_steps, env=env)


# --------------------------------------------------------------- decoding

def peel(result: Term, decl: A.TypeDecl, *, max_steps: int = 1_000_000,
         env: Optional[Environment] = None) -> Tuple[str, Tuple[Term, ...]]:
    """Read the outer result: which constructor of ``decl`` is it, and
    what does it carry?

    A Scott datum of an ``n``-constructor type applied to ``n`` markers
    returns the marker for its own constructor, applied to its fields.
    """
    env = env or _fresh_env()
    marks = [Atom(f"\x00r{i}") for i in range(len(decl.ctors))]
    r = fast_reduce(_ap(result, *marks), env, whnf_only=True,
                    max_steps=max_steps)
    if r.status not in (Status.WHNF, Status.NORMAL):
        raise RunError(
            f"probing the result did not reach weak head normal form "
            f"({r.status.value} after {r.steps} contractions)")
    head, args = r.term, []
    while isinstance(head, App):
        args.append(head.arg)
        head = head.fn
    args.reverse()
    if not isinstance(head, Atom) or head.name not in {m.name for m in marks}:
        raise RunError(
            f"not a value of {decl.name!r}: probing gave "
            f"{pretty(r.term)[:80]}")
    idx = [m.name for m in marks].index(head.name)
    ctor = decl.ctors[idx]
    if len(args) != len(ctor.fields):
        raise RunError(
            f"{ctor.name} carries {len(ctor.fields)} field(s) but the probe "
            f"returned {len(args)}")
    return ctor.name, tuple(args)


def decode(datum: Term, obj: ObjectType, *, max_steps: int = 1_000_000,
           max_nodes: int = 200_000,
           env: Optional[Environment] = None) -> A.Expr:
    """Turn a quoted datum back into a surface term, by probing.

    The datum of an ``n``-constructor object type applied to ``n`` markers
    returns the marker of its own constructor; the application
    constructor's marker comes back applied to the two subterms, which
    are decoded the same way.  Results are memoized by node identity, and
    the cache holds the node so its id cannot be recycled under it.
    """
    env = env or _fresh_env()
    ctors = list(obj.decl.ctors)
    marks = [Atom(f"\x00c{i}") for i in range(len(ctors))]
    names = [m.name for m in marks]
    app_idx = ctors.index(obj.app)
    cache: Dict[int, Tuple[Term, A.Expr]] = {}

    def one(node: Term) -> Tuple[str, Tuple[Term, ...]]:
        r = fast_reduce(_ap(node, *marks), env, whnf_only=True,
                        max_steps=max_steps)
        if r.status not in (Status.WHNF, Status.NORMAL):
            raise RunError(
                f"decoding did not reach weak head normal form "
                f"({r.status.value} after {r.steps} contractions)")
        head, args = r.term, []
        while isinstance(head, App):
            args.append(head.arg)
            head = head.fn
        args.reverse()
        if not isinstance(head, Atom) or head.name not in names:
            raise RunError(
                f"not a datum of {obj.name!r}: probing gave "
                f"{pretty(r.term)[:80]}")
        return head.name, tuple(args)

    # explicit stack: a level-2 datum is deeper than Python's
    todo: List[Tuple[Term, bool]] = [(datum, False)]
    built: List[A.Expr] = []
    visited = 0
    while todo:
        node, done = todo.pop()
        if done:
            r = built.pop()
            l = built.pop()
            e: A.Expr = A.App(l, r)
            cache[id(node)] = (node, e)
            built.append(e)
            continue
        hit = cache.get(id(node))
        if hit is not None and hit[0] is node:
            built.append(hit[1])
            continue
        visited += 1
        if visited > max_nodes:
            raise RunError(f"datum has more than {max_nodes} nodes")
        which, args = one(node)
        idx = names.index(which)
        if idx == app_idx:
            todo.append((node, True))
            todo.append((args[1], False))
            todo.append((args[0], False))
        else:
            e = A.Name(ctors[idx].name)
            cache[id(node)] = (node, e)
            built.append(e)
    return built.pop()


# ------------------------------------------------------------ fuel policy

def timeout_constructor(decl: A.TypeDecl) -> str:
    """The constructor a loop returns when the fuel runs out: ``R``'s
    **last terminal**, not its last constructor (``SURFACE-LANGUAGE-DESIGN.md``
    §6c's loop rule).  For ``maybe ≡ Nothing | Just term`` that is
    ``Nothing``, which is *not* last in declaration order; for
    ``result ≡ RVal term | RErr | RTime`` it is ``RTime``.
    """
    terminals = [c for c in decl.ctors if not c.fields]
    if not terminals:
        raise RunError(
            f"result type {decl.name!r} has no terminal constructor, so a "
            f"loop over it has nothing to return when the fuel runs out")
    return terminals[-1].name


@dataclass
class PolicyResult:
    """The outcome of iterative deepening over elided fuel."""
    constructor: str
    fields: Tuple[Term, ...]
    budget: Optional[int]       #: the budget that succeeded, or None
    budgets: Tuple[int, ...]    #: every budget tried, in order
    steps: int                  #: host contractions of the last attempt
    timed_out: bool

    @property
    def payload(self) -> Optional[Term]:
        return self.fields[0] if self.fields else None


def run_policy(prog: Level1Program, *, start: int = 8, cap: int = DEFAULT_CAP,
               max_steps: int = 5_000_000,
               env: Optional[Environment] = None) -> PolicyResult:
    """``RUNTIME-DESIGN.md`` §3c: the compiler cannot fill in elided fuel,
    so the runtime deepens iteratively -- doubling from ``start`` until a
    value or ``cap`` -- and reports the cap as the timeout outcome rather
    than hiding it.

    "A value" means any result constructor other than the loop's timeout,
    which is the last *terminal* of the result type and not its last
    constructor (§6c's loop rule; see :func:`timeout_constructor`).
    """
    env = env or _fresh_env()
    timeout_ctor = timeout_constructor(prog.result_type)
    tried: List[int] = []
    budget = max(1, start)
    last = None
    while True:
        tried.append(budget)
        out = run_level1(prog, max_steps, fuel=budget, env=env)
        if not out.whnf:
            raise RunError(
                f"host reducer gave up at budget {budget} "
                f"({out.status.value} after {out.steps} contractions)")
        ctor, fields = peel(out.term, prog.result_type, max_steps=max_steps,
                            env=env)
        last = (ctor, fields, out.steps)
        if ctor != timeout_ctor:
            return PolicyResult(ctor, fields, budget, tuple(tried),
                                out.steps, False)
        if budget >= cap:
            return PolicyResult(ctor, fields, None, tuple(tried),
                                out.steps, True)
        budget = min(budget * 2, cap)


# ------------------------------------------------- the blocking driver

def block_constructor(decl: A.TypeDecl, object_type: str) -> Optional[str]:
    """The result constructor a blocked run returns: the one carrying a
    payload that is *not* an object term -- ``RBlockN path``.  ``None``
    when the result type has none, i.e. the interpreter cannot block."""
    for c in decl.ctors:
        if len(c.fields) == 1 and c.fields[0] != object_type:
            return c.name
    return None


def make_resolver(exp: Expansion, facts) -> Term:
    """A closed resolver over ``facts``, a sequence of (key datum, answer
    datum) pairs -- the term a namespace literal compiles to, built at
    run time from a namespace that has grown."""
    at = exp.answer_type
    if at is None:
        raise RunError(
            "this program declares no oracle answer type, so it has no "
            "resolvers to build")
    if "EQ5" not in exp.terms:
        raise RunError("this program does not define 'EQ5'")
    return resolver_term(exp.terms["EQ5"], exp.terms[at.hit.name],
                         exp.terms[at.notyet.name], facts)


@dataclass
class NamespaceRun:
    """The trace of a re-run-from-scratch resolution."""
    trace: Tuple[Tuple[int, str], ...]
    constructor: Optional[str]
    payload: Optional[Term]
    rounds: int
    steps: int

    @property
    def events(self):
        return tuple(ev for _r, ev in self.trace)


def run_with_namespace(exp: Expansion, prog: Level1Program, resolution,
                       fuel=None, max_rounds: int = 10, *,
                       max_steps: int = 5_000_000, start: int = 8,
                       cap: int = DEFAULT_CAP) -> NamespaceRun:
    """``scry_namespace.py``'s resume loop, in the surface.

    The namespace is append-only and the program is **re-run from
    scratch** each round with a resolver built from everything learned so
    far, which is what makes blocking sound: a fact can only be added,
    never changed, so a later run can only get further
    (``SURFACE-LANGUAGE-DESIGN.md`` §7).

    ``resolution`` maps the *rendered* blocked path to the answer datum
    that resolves it -- the host-side source of truth standing in for
    whatever a real namespace would consult.

    ``fuel=None`` composes the two policies: each round deepens
    iteratively (``RUNTIME-DESIGN.md`` §3c) until the round produces
    something other than a timeout, and the outer loop then learns a fact
    and starts again.  The budget that succeeded is recorded in the
    trace.
    """
    import dataclasses
    block = block_constructor(prog.result_type, prog.object_type.name)
    if block is None:
        raise RunError(
            f"result type {prog.result_type.name!r} has no blocking "
            f"constructor, so this interpreter cannot block")
    timeout = timeout_constructor(prog.result_type)
    namespace: List[Tuple[Term, Term]] = []   # append-only list of (key datum, answer datum)
    known = set()
    trace = []
    steps = 0
    for rnd in range(1, max_rounds + 1):
        run = dataclasses.replace(
            prog, params=(make_resolver(exp, namespace),) + prog.params[1:])
        if fuel is None:
            budget = max(1, start)
            while True:
                out = run_level1(run, max_steps, fuel=budget)
                if not out.whnf:
                    break
                ctor, fields = peel(out.term, prog.result_type,
                                    max_steps=max_steps)
                if ctor != timeout or budget >= cap:
                    break
                budget = min(budget * 2, cap)
            if out.whnf:
                trace.append((rnd, f"budget {budget}"))
        else:
            out = run_level1(run, max_steps, fuel=fuel)
        steps = out.steps
        if not out.whnf:
            trace.append((rnd, f"status:{out.status.value}"))
            return NamespaceRun(tuple(trace), None, None, rnd, steps)
        ctor, fields = peel(out.term, prog.result_type, max_steps=max_steps)
        if ctor != block:
            trace.append((rnd, ctor))
            return NamespaceRun(tuple(trace), ctor,
                                fields[0] if fields else None, rnd, steps)
        key_datum = fields[0]
        key = render_ascii(decode(key_datum, prog.object_type,
                                  max_steps=max_steps))
        trace.append((rnd, f"BLOCK on {key}"))
        if key in known or key not in resolution:
            trace.append((rnd, "STUCK"))
            return NamespaceRun(tuple(trace), None, None, rnd, steps)
        namespace.append((key_datum, resolution[key]))
        known.add(key)
    trace.append((max_rounds, "EXCEEDED MAX ROUNDS"))
    return NamespaceRun(tuple(trace), None, None, max_rounds, steps)
