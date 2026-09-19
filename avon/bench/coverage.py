#!/usr/bin/env python3
"""What a loader that hashes every node would actually find (DESIGN.md §6.1).

For each corpus program: compile it, build its dictionary, hash every node
of every row, and report which rows occur inside which — that is exactly
the match the C loader performs once, at load time, before it wraps a node
in an AV_JET.

    python3 avon/bench/coverage.py [corpus-file ...]

Two things to watch for in the output, both of which are properties of the
key and not bugs: one hash can carry several names (aliases expand to the
same term), and the smallest rows match everywhere (``K`` is ``Nothing``,
``nil`` and ``zero`` at once), which is why matching needs a size floor.
"""
from __future__ import annotations

import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(HERE, "..", "..", "python")
DEFAULT = ["interp-whnff.ascii.ski", "scry-wfn.ascii.ski", "sec1-nat.ascii.ski"]


def main():
    sys.path.insert(0, os.path.abspath(PYTHON))
    import skijack
    from skijack.dictionary import from_expansion, hash_all, VERSION

    args = sys.argv[1:] or DEFAULT
    for spec in args:
        path = spec if os.path.exists(spec) else os.path.join(
            PYTHON, "tests", "corpus", spec)
        exp = skijack.compile(open(path, encoding="utf-8").read(), "ascii")
        d = from_expansion(exp)
        rows = sorted(d.entries.items(), key=lambda kv: -kv[1].size)

        by_hash = {}
        for name, e in rows:
            by_hash.setdefault(e.hash, []).append(name)
        aliases = {h: ns for h, ns in by_hash.items() if len(ns) > 1}

        print(f"\n=== {os.path.basename(path)}: {len(rows)} rows, "
              f"{len(by_hash)} distinct terms")
        if aliases:
            print("    one term, several names: "
                  + "; ".join("=".join(ns) for ns in aliases.values()))

        for name, e in rows:
            nodes = hash_all(e.term)
            inside, small = {}, 0
            for _i, (node, h) in nodes.items():
                key = f"{VERSION}:{h}"
                if key in by_hash and node is not e.term:
                    row = "/".join(by_hash[key])
                    if d.entries[by_hash[key][0]].size < 3:
                        small += 1
                        continue
                    inside[row] = inside.get(row, 0) + 1
            if inside or small:
                found = ", ".join(f"{k}x{v}" for k, v in sorted(inside.items()))
                print(f"    {name:14} {e.size:>5} atoms, {len(nodes):>4} nodes"
                      f" | contains {found or '-'}"
                      + (f" (+{small} under the size floor)" if small else ""))

        top = max(rows, key=lambda kv: kv[1].size)[0]
        nodes = hash_all(d.entries[top].term)
        hits = sum(1 for _i, (_x, h) in nodes.items()
                   if f"{VERSION}:{h}" in by_hash)
        big = sum(1 for _i, (_x, h) in nodes.items()
                  if f"{VERSION}:{h}" in by_hash
                  and d.entries[by_hash[f"{VERSION}:{h}"][0]].size >= 3)
        print(f"    loader's view of {top}: {len(nodes)} distinct nodes, "
              f"{hits} match a row ({big} above the size floor)")


if __name__ == "__main__":
    sys.setrecursionlimit(10_000_000)
    threading.stack_size(1024 * 1024 * 1024)
    th = threading.Thread(target=main)
    th.start()
    th.join()
