# SKIjack

(Pronounced "sky-jack".)

A supercombinator language over the $SKI$ combinatory logic and a graph-reduction runtime with jet-accelerated code to make it
(marginally) viable.

- `DESIDERATA.md`: what the language must be, stated as twelve properties borrowed from nockasm's discipline, and the four tiers of exposure (primitives, combinators, supercombinators, macros).
- `SYNTAX.md`: the surface direction: equations, cores, glyph-named combinators, two brackets, one grammar with two lexicons (ASCII and Unicode) related by a bijective token table, and the scry namespace discipline.
- `SURFACE-LANGUAGE-DESIGN.md`: the kernel forms, the representation ABI (Scott pairs as cells, Nock axes over data, cores tied with `Y`), the compile rules, compile-time name resolution with no runtime environment, the standard library the runtime supplies at boot, and the quotation line that a theorem fixes.
- `EXAMPLES.md`: numerals (increment, decrement, addition, subtraction), a combinator three ways, a macro over pairs at level 0 and level 1, a user interpreter, and a value lookup, in both spellings, with the codegen and the checks that were actually run.
- `RUNTIME-DESIGN.md`: why a Turner-style reducer with jets is required, what it must reproduce, and what it must not do.
- `avon/DESIGN.md`: the build plan for the C runtime — the measurement that fixes its acceptance test (sharing changes the paper's counts and not its values, so Avon carries two strategies), the node and arena representation, jets as loader-installed wrappers rather than runtime hashing, the conformance harness, and eight stages with what each one has to prove. `avon/bench/strategies.py` reproduces the measurement.

- `python/`: `skijack`, the reference implementation in Python on `aviary-kernel`: the two lexers over one token table, one parser, renderers for both lexicons, the expander through bracket abstraction, and behavioral probes; `python/README.md` records every decision taken and what its test suite proves. Its corpus under `python/tests/corpus/` is written in both spellings and is also Avon's conformance suite: the C runtime is correct when it reproduces `skijack`'s terms and decoded values on every file there, and the reference host's contraction counts under its faithful strategy (`avon/DESIGN.md` §1).

**Three words, three levels.** *Equation*: `f x y = body`, what an author writes, and the level at which sibling and scope relations live. *Supercombinator*: what an equation compiles to — closed, `Y`-tied, one node — and the unit of naming, sharing, jetting, lifting, and the census. *Core*: the group an equation is declared in. *Subject*: the single argument the runtime applies a program to at boot, and nothing else; it is an argument, not a scope, and nothing resolves into it at run time. *Axis*: addressing into a Scott-encoded data cell, never into a scope. Names resolve in a compile-time table and are gone before anything runs, which is why the subject-oriented vocabulary this repository started with does not survive contact with bracket abstraction (`DESIDERATA.md` §1, "two things do not transfer").

The reference artifact, the paper, and every reported count live in `~/ski-in-ski`; this repository depends on that one, never the reverse.

