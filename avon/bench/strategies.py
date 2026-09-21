#!/usr/bin/env python3
"""The measurement behind DESIGN.md §1: what a sharing reducer does to the
paper's contraction counts.

Three strategies over one node representation, run on the paper's targets:

  copy    no update in place -- the strategy ``aviary_kernel.reduce`` uses,
          transcribed onto nodes: the position is a flat (head, args) pair,
          contraction builds the combinator body fresh, nothing is mutated.
  share   Turner's machine: contraction overwrites the redex root, so a
          duplicated redex is contracted once.
  cons    share, plus a (left, right) table so structurally equal
          applications built during reduction are one node.

It also runs the differential that says sharing is safe (same normal forms
as the reference on random terms) and the cycle check that says consing is
not obviously safe (a cons can return an ancestor of the redex).

    SKIJACK_ARTIFACT_DIR=/path/to/artifact-metacircular-ski python3 avon/bench/strategies.py

Requires: aviary-kernel, and ``tower_harness.py`` from a checkout of
``artifact-metacircular-ski`` (``SKIJACK_ARTIFACT_DIR``, default ``<repo>/artifact``) for the
compiled interpreter and the encoder.
"""
from __future__ import annotations

import os
import random
import sys
import threading
import time

SKI_IN_SKI = os.path.expanduser(os.environ.get(
    "SKIJACK_ARTIFACT_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "artifact")))
ARITY = {"S": 3, "K": 2, "I": 1}

# a node is a 4-list [tag, l, r, name]; tag in "A" app, "R" indirection,
# "L" leaf.  The C runtime packs the same thing into two 32-bit words.
A_, R_, L_ = "A", "R", "L"


class Heap:
    def __init__(self, cons_at_load=False, cons_during=False):
        self.cons_at_load = cons_at_load
        self.cons_during = cons_during
        self.table = {}
        self.alloc = 0
        self.probes = 0

    @staticmethod
    def res(n):
        while n[0] == R_:
            n = n[1]
        return n

    def leaf(self, name):
        self.alloc += 1
        return [L_, None, None, name]

    def app(self, f, a, during):
        cons = self.cons_during if during else self.cons_at_load
        if cons:
            k = (id(self.res(f)), id(self.res(a)))
            self.probes += 1
            hit = self.table.get(k)
            if hit is not None:
                return hit
        self.alloc += 1
        n = [A_, f, a, None]
        if cons:
            self.table[k] = n
        return n


def load(term, heap):
    """aviary Term -> nodes, preserving the input's object sharing."""
    from aviary_kernel.terms import Atom
    memo, work, out = {}, [(term, False)], []
    while work:
        t, done = work.pop()
        if not done and id(t) in memo:
            out.append(memo[id(t)])
            continue
        if isinstance(t, Atom):
            n = heap.leaf(t.name)
            memo[id(t)] = n
            out.append(n)
            continue
        if not done:
            work.append((t, True))
            work.append((t.arg, False))
            work.append((t.fn, False))
        else:
            a, f = out.pop(), out.pop()
            n = heap.app(f, a, False)
            memo[id(t)] = n
            out.append(n)
    return out.pop()


def unload(root, heap):
    from aviary_kernel.terms import Atom, App
    def go(n):
        n = heap.res(n)
        if n[0] == L_:
            return Atom(n[3])
        return App(go(n[1]), go(n[2]))
    return go(root)


def whnf_share(root, heap, fuel=10 ** 9):
    """Update in place.  Returns (steps, status, peak spine depth)."""
    steps, peak, spine, cur = 0, 0, [], root
    while True:
        cur = heap.res(cur)
        if cur[0] == A_:
            spine.append(cur)
            peak = max(peak, len(spine))
            cur = cur[1]
            continue
        k = ARITY.get(cur[3])
        if k is None or len(spine) < k:
            return steps, "whnf", peak
        if steps >= fuel:
            return steps, "fuel", peak
        if k == 1:                                  # I x -> x
            n = spine[-1]
            n[0], n[1], n[2] = R_, n[2], None
        elif k == 2:                                # K x y -> x
            n = spine[-2]
            n[0], n[1], n[2] = R_, spine[-1][2], None
        else:                                       # S f g x -> f x (g x)
            n = spine[-3]
            f, g, x = spine[-1][2], spine[-2][2], spine[-3][2]
            n[0], n[1], n[2] = A_, heap.app(f, x, True), heap.app(g, x, True)
        del spine[len(spine) - k:]
        steps += 1
        cur = n


def whnf_copy(root, heap, fuel=10 ** 9):
    """No update: the position is (head, args), exactly as the reference
    reducer holds it.  Returns (steps, status, peak arg depth)."""
    steps, peak = 0, 0
    args, head = [], root
    while head[0] == A_:
        args.append(head[2])
        head = head[1]
    args.reverse()
    while True:
        peak = max(peak, len(args))
        k = ARITY.get(head[3])
        if k is None or len(args) < k:
            return steps, "whnf", peak
        if steps >= fuel:
            return steps, "fuel", peak
        if k == 1:
            new, rest = args[0], args[1:]
        elif k == 2:
            new, rest = args[0], args[2:]
        else:
            f, g, x = args[0], args[1], args[2]
            new = heap.app(heap.app(f, x, True), heap.app(g, x, True), True)
            rest = args[3:]
        nargs, cur = [], new
        while cur[0] == A_:
            nargs.append(cur[2])
            cur = cur[1]
        nargs.reverse()
        head, args = cur, nargs + rest
        steps += 1


def nf_share(root, heap, fuel=10 ** 9):
    """Full normal form under the sharing strategy (recursive on argument
    depth; only used on the small terms of the differential)."""
    steps, st, _ = whnf_share(root, heap, fuel)
    if st != "whnf":
        return steps, st
    n = heap.res(root)
    spine = []
    while n[0] == A_:
        spine.append(n)
        n = heap.res(n[1])
    for ap in spine:
        more, st = nf_share(ap[2], heap, fuel - steps)
        steps += more
        if st != "whnf":
            return steps, st
    return steps, "whnf"


def has_cycle(root, heap):
    """Back edge into a node still on the DFS stack."""
    WHITE, GREY, BLACK = 0, 1, 2
    colour, work, found = {}, [(heap.res(root), False)], 0
    while work:
        n, done = work.pop()
        if done:
            colour[id(n)] = BLACK
            continue
        c = colour.get(id(n), WHITE)
        if c == GREY:
            found += 1
            continue
        if c == BLACK:
            continue
        colour[id(n)] = GREY
        work.append((n, True))
        if n[0] == A_:
            work.append((heap.res(n[2]), False))
            work.append((heap.res(n[1]), False))
    return found, len(colour)


def main():
    sys.path.insert(0, SKI_IN_SKI)
    import tower_harness as T
    from aviary_kernel.reduce import Status
    from aviary_kernel.terms import Atom, App, pretty

    t = App(T.I, T.K)
    targets = [
        ("T0  whnfF 3 <I K>", T.A(T.WP, T.natP(3), T.encP(t)), 340),
        ("T1  whnfF 120 <UQ <I K>>",
         T.A(T.WP, T.natP(120), T.encP(T.A(T.UP, T.encP(t)))), 91_556),
        ("T2  whnfF 500 <whnfF 3 <I K>>",
         T.A(T.WP, T.natP(500), T.encP(T.A(T.WP, T.natP(3), T.encP(t)))),
         504_930),
    ]

    print("strategy comparison (WHNF, host contractions)\n")
    for label, term, paper in targets:
        r = T.fast_reduce(term, T.env, max_steps=10 ** 8)
        assert r.status is Status.WHNF and r.steps == paper, (label, r.steps)
        print(f"{label}")
        print(f"  reference (substitution) : {r.steps:>9,}")
        for name, cl, cd, fn in (("copy                    ", 0, 0, whnf_copy),
                                 ("share                   ", 0, 0, whnf_share),
                                 ("share, cons at load     ", 1, 0, whnf_share),
                                 ("share, cons during      ", 1, 1, whnf_share)):
            heap = Heap(bool(cl), bool(cd))
            g = load(term, heap)
            t0 = time.time()
            steps, st, peak = fn(g, heap)
            el = time.time() - t0
            cyc, live = has_cycle(g, heap)
            flag = "= paper" if steps == paper else f"{steps / paper:.0%} of paper"
            print(f"  {name}: {steps:>9,}  {flag:>14}  "
                  f"nodes {heap.alloc:>9,}  probes {heap.probes:>8,}  "
                  f"depth {peak:>3}  result {live:>6,} nodes  "
                  f"cycles {cyc}  {el:5.2f}s")
        sys.stdout.flush()

    print("\ndifferential: sharing vs the reference on random terms")
    rnd = random.Random(7)

    def gen(d):
        if d == 0 or rnd.random() < 0.3:
            return Atom(rnd.choice("SKI"))
        return App(gen(d - 1), gen(d - 1))

    checked = mismatch = worse = 0
    for _ in range(3000):
        term = gen(4)
        r = T.fast_reduce(term, T.env, whnf_only=False, max_steps=3000)
        if r.status is not Status.NORMAL:
            continue
        heap = Heap()
        g = load(term, heap)
        steps, st = nf_share(g, heap, 3000)
        if st != "whnf":
            mismatch += 1
            print("  gave up where the reference normalized:", pretty(term))
            continue
        checked += 1
        if pretty(unload(g, heap)) != pretty(r.term):
            mismatch += 1
            print("  MISMATCH:", pretty(term))
        if steps > r.steps:
            worse += 1
    print(f"  {checked} normal forms compared, {mismatch} mismatches, "
          f"{worse} terms where sharing took more steps")


if __name__ == "__main__":
    sys.setrecursionlimit(10_000_000)
    threading.stack_size(1024 * 1024 * 1024)
    th = threading.Thread(target=main)
    th.start()
    th.join()
