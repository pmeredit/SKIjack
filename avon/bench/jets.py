"""Jet candidates: which structures the compiled corpus repeats most.

    python3 avon/bench/jets.py [--min-atoms 5] [--top 20]

For every compiled term of every corpus program, every subterm of at
least ``--min-atoms`` atoms is keyed by structural hash (``avon/DESIGN.md``
section 5: the subterm and nothing else) and counted by *tree*
occurrence -- how often a substitution-semantics reducer would meet it --
with multiplicities propagated through sharing so a DAG does not
undercount.  Rows are ranked by occurrences times atoms, the crude
estimate of work a jet for that structure would absorb, and marked with
the dictionary name when the structure is a named supercombinator.

Linear in the DAG.  Requires only ``skijack`` (the corpus ships inside it).
"""

import argparse
import collections
import hashlib
import os
import sys

try:
    import skijack
except ModuleNotFoundError:            # run from a checkout without installing
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "python"))
    import skijack
from skijack import corpus, dictionary
from aviary_kernel.terms import App, Atom, pretty

sys.setrecursionlimit(10 ** 6)


def census(min_atoms: int):
    hashes, sizes, keep = {}, {}, []           # keyed by id(node); keep holds nodes

    def h(x):
        k = id(x)
        if k in hashes:
            return hashes[k]
        if isinstance(x, Atom):
            hv = hashlib.blake2b(b"A" + x.name.encode(), digest_size=12).hexdigest()
            n = 1
        else:
            hv = hashlib.blake2b(b"P" + h(x.fn).encode() + h(x.arg).encode(),
                                 digest_size=12).hexdigest()
            n = sizes[id(x.fn)] + sizes[id(x.arg)]
        hashes[k], sizes[k] = hv, n
        keep.append(x)
        return hv

    occ, progs, atoms, sample, named = (collections.Counter(), collections.defaultdict(set),
                                        {}, {}, {})
    for stem in corpus.names():
        try:
            exp = skijack.compile(corpus.read(stem))
        except Exception:                       # parse-only corpus files
            continue
        for name in dictionary.from_expansion(exp).names():
            term = exp.terms.get(name)
            if term is not None:
                named.setdefault(h(term), name)
        for term in exp.terms.values():
            h(term)
            # tree multiplicity on a DAG: parents before children
            mult = collections.Counter({id(term): 1})
            order, seen, stack = [], set(), [term]
            while stack:
                x = stack.pop()
                if isinstance(x, tuple):
                    order.append(x[0])
                    continue
                if id(x) in seen:
                    continue
                seen.add(id(x))
                stack.append((x,))
                if isinstance(x, App):
                    stack.append(x.fn)
                    stack.append(x.arg)
            for x in reversed(order):
                m = mult[id(x)]
                if isinstance(x, App):
                    mult[id(x.fn)] += m
                    mult[id(x.arg)] += m
                    if sizes[id(x)] >= min_atoms:
                        k = hashes[id(x)]
                        occ[k] += m
                        progs[k].add(stem)
                        atoms[k] = sizes[id(x)]
                        sample.setdefault(k, x)
    rows = sorted(occ, key=lambda k: -occ[k] * atoms[k])
    return [(occ[k], atoms[k], len(progs[k]), named.get(k, "-"), pretty(sample[k]))
            for k in rows]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min-atoms", type=int, default=5)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()
    rows = census(args.min_atoms)
    print(f"{'occurrences':>11} {'atoms':>5} {'progs':>5}  {'name':10s} structure")
    for o, a, p, nm, s in rows[:args.top]:
        print(f"{o:11,d} {a:5d} {p:5d}  {nm:10s} {s[:56]}")
    top = rows[:40]
    print(f"\n{len(rows):,} distinct structures; among the top 40, "
          f"{sum(1 for r in top if r[3] != '-')} are named supercombinators.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
