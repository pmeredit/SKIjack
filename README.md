# SKIjack

(Pronounced "sky-jack".)

A subject-oriented language over the $SKI$ combinatory logic and a graph-reduction runtime with jet-accelerated code to make it
(marginally) viable.

- `DESIDERATA.md`: what the language must be, stated as ten properties borrowed from nockasm's discipline, and the four tiers of exposure (primitives, combinators, supercombinators, macros).
- `SYNTAX.md`: the surface direction: equational arms, cores, glyph-named combinators, two brackets, one grammar with two lexicons (ASCII and Unicode) related by a bijective token table, and the scry namespace discipline.
- `SURFACE-LANGUAGE-DESIGN.md`: the kernel forms, the representation ABI (Scott pairs as cells, Nock axes, cores tied with `Y`), the compile rules, the standard subject, and the quotation line that a theorem fixes.
- `EXAMPLES.md`: numerals (increment, decrement, addition, subtraction), a combinator three ways, a macro over pairs at level 0 and level 1, a user interpreter, and a value lookup, in both spellings, with the codegen and the checks that were actually run.
- `RUNTIME-DESIGN.md`: why a Turner-style reducer with jets is required, what it must reproduce, and what it must not do.

- `python/`: `skijack`, the reference implementation in Python on `aviary-kernel`: the two lexers over one token table, one parser, renderers for both lexicons, the expander through bracket abstraction, and behavioral probes; `python/README.md` records every decision taken and what its test suite proves. Its corpus under `python/tests/corpus/` is written in both spellings and is also Avon's conformance suite: the C runtime is correct when it reproduces `skijack`'s terms and contraction counts on every file there.

The reference artifact, the paper, and every reported count live in `~/ski-in-ski`; this repository depends on that one, never the reverse.

