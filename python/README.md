# `skijack` — the surface language, steps 1 to 3

Steps 1 (syntax: two lexicons, one grammar, one tree, a renderer), 2
(codegen to closed `{S,K,I}` terms, without types and without quotation)
and 3 (the type-generated forms of the interpreter interface) of
`DESIDERATA.md` §6.

The milestone of §6 item 2 is reached: **the paper's interpreter compiles
from surface source, atom for atom and count for count.** `whnfF` written
in the surface compiles to a term byte-identical to the artifact's
618-atom `whnfF`, T0 reaches weak head normal form in exactly 340 host
contractions, and the T3 pair compiles to 768 and 771 atoms with the
paper's table.

The design notes one directory up are the specification:
`DESIDERATA.md`, `SYNTAX.md`, `SURFACE-LANGUAGE-DESIGN.md`,
`EXAMPLES.md`. Nothing in them is edited by this package.

The back end is `aviary-kernel`: bracket abstraction
(`aviary_kernel.abstraction.expand`), the term representation
(`aviary_kernel.terms`), the reducer (`aviary_kernel.reduce`) and the
built-in bird registry. This package reimplements none of them; it
reuses the artifact's `D` / `AL` / `expand` / `fast_reduce` idioms from
`~/ski-in-ski/tower_harness.py` and `~/ski-in-ski/scry_harness.py`.

## Install and run

```sh
cd python
pip install -e .            # needs aviary-kernel (0.1.0 is what this was measured on)
python3 -m pytest -q        # from this directory
```

The suite also runs straight out of the directory without installing,
since `pyproject.toml` puts `tests/` on `pythonpath` and the package is
importable from the working directory.

## What passes

`python3 -m pytest -q` from `python/`:

```
323 passed
```

* `tests/test_lexicon.py` — the token table is checked at import as a
  **strict bijection with no exceptions** (no two rows share a token
  kind; neither column repeats a spelling); both lexers emit the same
  token kinds and values for nine paired snippets; comments run to end
  of line; maximal munch resolves `:=*`/`:=!` before `:=`, `===` and
  `=>` before `=`, `|>`/`|-` before `|`; the fact arrow `=>`/`↦` and the
  signature arrow `->`/`→` are separate kinds in both lexicons; and axis
  picks are told apart from fuel.
* `tests/test_parser.py` — every corpus file parses in its own lexicon;
  the ASCII and Unicode spellings of each corpus file produce *equal
  trees*; application is left-associative; the two documented parsing
  decisions behave as specified, including a clear error on an
  undeclared constructor in a case branch.
* `tests/test_roundtrip.py` — for each of the 14 corpus sources `S` in
  lexicon `L`: `parse_L(render_L(parse_L(S))) == parse_L(S)`;
  `parse_M(render_M(parse_L(S))) == parse_L(S)` for the other lexicon
  `M`; `render_L` is idempotent on text; and a there-and-back trip
  through the other lexicon returns the same tree.
* `tests/test_expand.py` — the exact terms and atom counts of
  `EXAMPLES.md` sections 1–3 (below), plus the behaviour of each pass
  and the errors it raises.
* `tests/test_probe.py` — every "check run" of `EXAMPLES.md` sections
  1–3, read behaviorally, plus two regression tests for the
  Scott-numeral reader's memo table (see "A bug this step found").
* `tests/test_generate.py` — shape discovery (the object type, the
  outcome and result types), what each core is filled with, that a
  user-written `sp` / `step` / `loop` is never replaced, and that
  everything generated is surface syntax that renders and re-parses.
* `tests/test_interpreter.py` — the milestone: every definition of the
  compiled `whnfF` against the artifact's, T0's 340 contractions and its
  decoded value, and the T3 pair's sizes, table and faithfulness.

### The measured values, reproduced

Compiled from both spellings of the corpus; every one is atom-identical
to `EXAMPLES.md`.

| name | atoms | term |
|---|---|---|
| `Zero` | 1 | `K` |
| `Suc` | 8 | `S (K K) (S (K (S I)) K)` |
| `inc` | 8 | `S (K K) (S (K (S I)) K)` — identical to `Suc` (the abstraction algorithm η-reduces `λn. Suc n`) |
| `dec` | 7 | `S (S I (K K)) (K I)` |
| `add` | 42 | `Y`-tied; the first fourteen atoms are `Y` |
| `sub` | 43 | `Y`-tied |
| `C` | 10 | `S (S (K S) (S (K K) S)) (K K)` |
| `flipK1` | 11 | `S (S (K S) (S (K K) S)) (K K) K` |
| `flipK2` | 5 | `S (K (S K)) K` |
| `pair` | 17 | `S (S (K S) (S (K K) (S (K S) (S (K (S I)) K)))) (K K)` |
| `hd` | 4 | `S I (K K)` |
| `tl` | 5 | `S I (K (K I))` |
| `flipA` | 29 | `S (S (K (S (S (K S) (S (K K) (S (K S) (S (K (S I)) K)))) (K K))) (S I (K (K I)))) (S I (K K))` |

Probes (fresh marker atoms, never combinator syntax): `inc 2 = 3`,
`dec 3 = 2`, `dec 0 = 0`, `add 2 3 = 5`, `add 0 4 = 4`, `sub 5 2 = 3`,
`sub 2 5 = 0`; `C K X1 X2 → X2`; `flipK1 X1 X2 → X2`;
`flipK2 X1 X2 → X2`; `flipA [X1 X2] K → X2`. Contraction counts also
match `EXAMPLES.md`: `dec 3` reaches WHNF in 15 host contractions and
`flipA [K I] K` reduces to `I` in 40.

### The interpreter, compiled from surface source

`tests/corpus/interp-whnff.*.ski` is the whole of the paper's base
interpreter:

```
term === S | K | I | App term term
maybe === Nothing | Just term

whnfF := {
  step m = sp m nil stepS stepK stepI
}
```

`generate.py` supplies the rest from the two declarations: the walker
`sp`, the rebuilder `rb`, their helpers, the default `stepS` / `stepK` /
`stepI`, and the core's fuel loop. Every definition it produces is
**byte-identical** to the artifact's, checked one by one in
`test_interpreter.py::test_every_definition_matches_the_artifact`:

| this package | the artifact | atoms |
|---|---|---|
| `whnfF` (the core's loop) | `whnfF` | **618** |
| `whnfF.loop1` | `wf1` | 588 |
| `whnfF.step` | `step` | **569** (`SURFACE-LANGUAGE-DESIGN.md` §9) |
| `sp` / `spApp` / `resS` / `resK` / `resI` | same names | 126 / 48 / 15 / 13 / 11 |
| `rb` / `rb1` | same names | 74 / 44 |
| `stepS`…`stepS3`, `stepK`…`stepK2`, `stepI`, `stepI1` | same names | 237 / 105 / 92 … |
| `S` `K` `I` `App` | `encS` `encK` `encI` `encA` | 7 / 5 / 3 / 32 |
| `Nothing` `Just` `nil` `cons` | `nothing` `just` `nil` `cons` | 1 / 8 / 1 / 22 |

**T0.** `whnfF 3 <I K>` reaches weak head normal form in exactly **340**
host contractions, and decodes behaviorally to `Just <K>`: the outcome
selects the `Just` marker and its payload, applied to four markers,
selects the `K` one.

A second corpus file writes the loop out instead
(`interp-whnff-written-loop.*.ski`) and compiles to the same 618-atom
term, which is what "a written loop overrides the generated one" has to
mean.

**T3.** `interp-t3.*.ski` declares the five-constructor alphabet, the
three-way outcome and the three-way result, and two cores differing in
one arm:

```
wf5Abs := { stepErr acc = Errd }
wf5Omg := { stepErr acc = omega }
```

`wf5Abs` compiles to **768** atoms and `wf5Omg` to **771**, both
byte-identical to the artifact's, as are their `step`, `loop1`, `stepErr`
and the shared `sp` / `rb` / `stepS` / `stepK` / `stepI`. With fuel 20
and a host cap of 400,000 contractions the table is the paper's:

| object term | `wf5Abs` | `wf5Omg` |
|---|---|---|
| `Err` | ERR (127 contractions) | host diverges (hits the cap) |
| `Err K` | ERR (222) | host diverges |
| `K I Err` | VAL (574) | VAL (574) |
| `I K` | VAL (438) | VAL (438) |
| `Omega` | TIME (10,130) | TIME (10,130) |

The two agree exactly — answer *and* contraction count — wherever the
`Err` arm never fires, which is the faithfulness claim; they differ only
where it does, and there the absorbing arm reports a crash the other
hides as host divergence.

## What is *not* here

Out of scope for these three steps, and refused with a clear error by
`expand_program` rather than silently mis-compiled:

* **types** — `===` declarations and `:` signatures are parsed and kept
  in the tree; field types and signatures are ignored (`DESIDERATA.md`
  item 11, Stage B). What *is* checked is Stage A's case completeness,
  case order, and constructor arity.
* **quotation and level-1 packaging** — `<t>`, `<t>@n`, `I |- <t>@n`,
  `?^/a/b` and `ns{…}` parse, render and round-trip, but reaching the
  code generator raises `ExpandError`. `EXAMPLES.md` §4 and §5 and
  `SYNTAX.md` §3 are therefore parse/round-trip corpus only; the
  interpreters they sketch are compiled here from `interp-*.ski`
  instead, and driven with the artifact's encoder rather than a
  surface quoter.
* **wing resolution** — `a.b` is carried as the dotted name; there is no
  subject and no axis schema yet, so a wing does not compile.
* **capturing macros** — `:=!` is refused by name
  (`macro 'm' is declared capturing (':=!'); the capturing form is not
  implemented`).
* **mutual recursion between arms** — see the fixpoint decision below.
* **lift**, the dictionary/hash artifact, and the standard subject.

## Decisions the specification left open

Each of these is a place where the notes do not determine the answer;
the interpretation chosen is the one that makes `EXAMPLES.md` work.

1. **(a) Case branches need the type declarations, so parsing is two
   pass.** A branch is `CName binder* body` and the binder count is the
   constructor's *declared* arity, so `Suc k Suc (add m k)` can only be
   split by knowing `Suc` has one field. `parser.collect_ctors` scans
   the token stream for `===` declarations first (a type declaration
   runs to the end of its logical line, which is what bounds the field
   list), then the real parse runs with that table. An undeclared
   constructor in a branch is a `ParseError` naming it.
2. **(b) `name := { … }` is a core; `name := ns{ … }` is a namespace
   literal.** The `ns` prefix is munched by the ASCII lexer as one
   `NSOPEN` token; Unicode spells it `⦃`, and its closer `⦄` lexes to
   the same `RBRACE` kind as `}` (`SYNTAX.md` §2 says so explicitly), so
   one grammar serves both. `⦄` is therefore declared in
   `lexicon.UNICODE_ALIASES`, not as a table row, which is what keeps
   the table's ASCII column injective.
3. **Core fixpoint strategy: one fixpoint per arm, not one over a
   tuple.** A self-recursive arm `f b1 … bn = body` compiles to
   `AL(f, Y fGen)` with `D(fGen, [self, b1, …, bn], body[f := self])`,
   which is the `spGen`/`sp` and `wfGen`/`whnfF` shape of
   `tower_harness.py`. A non-recursive arm is a plain `D`. This is what
   reproduces `EXAMPLES.md`'s 42 and 43 atoms for `add` and `sub`
   exactly. The cost is that **mutual recursion between two arms is
   refused** with a named error rather than mis-compiled; a tuple
   fixpoint would handle it and is the natural next step.
4. **Every lambda is lambda-lifted into its own supercombinator.** A
   case branch with binders, and a `\x.e`, become a helper `D` over the
   enclosing binders that occur free in the body, applied to those
   binders at the use site. For `add` this yields exactly the reference
   `add1 f m k = Suc (f m k)` and `addGen f m n = n m (add1 f m)`. This
   is Tier 2 of `DESIDERATA.md` §3 taken literally: arms are the unit.
5. **Cell items are atoms.** `'[' expr expr+ ']'` in the grammar sketch
   is ambiguous under juxtaposition (`[3@p 2@p]` would be one
   application), so a cell's items are parsed as atoms and an
   application inside a cell is parenthesized: `[(f x) y]`. Every cell
   in the corpus is unaffected.
6. **Newlines terminate declarations and arms.** The grammar sketch is
   silent, but a core body `{ inc n = Suc n  dec n = … }` is otherwise
   ambiguous. Newlines are significant at declaration and arm level and
   invisible inside `(`, `[`, `<`/`⟨`, a case brace, and a namespace
   literal; core braces do *not* hide them.
7. **The lambda rule consumes exactly one `.`.** `SYNTAX.md` §9 flags
   the collision between the wing dot and the lambda dot. `DOT` is its
   own token; `atom` builds a wing from `NAME ('.' NAME)*` and the
   lambda rule eats the dot after its binder, so `\x.a.b` is
   `Lambda("x", Name("a.b"))`.
8. **A bare number is refused in expression position.** `atom :=
   … | NUMBER | …` in the sketch has nothing to compile to, since the
   calculus has no integer type (`SYNTAX.md` §8). Numbers appear only in
   an axis pick (`2@p`) and as fuel (`<t>@10`), both of which the lexer
   turns into their own token kinds.
9. **Backend names are mangled on collision with an aviary bird.** The
   kernel refuses to shadow a built-in, so an arm named `C` is defined
   as `Cc` — the form `EXAMPLES.md`'s codegen notes record. Mangling
   never changes a compiled term; `Expansion.backend` records the map.
10. **The prelude is `pair`, `hd`, `tl`.** `[a b]` compiles to
    `pair a b`, `2@p` to `hd p`, `3@p` to `tl p`, and axis `n` to the
    chain of heads and tails Nock's numbering gives (axis `2n` is the
    head of axis `n`, axis `2n+1` its tail; axis 1 is `p` itself).
    Writing `pair`, `hd` or `tl` in a program replaces the prelude's.
11. **Constructors come from the type declaration**, as
    `λ fields. λ c₁ … cₙ. cᵢ fields`. `nat === Zero | Suc nat` therefore
    produces exactly the artifact's `zero` and `suc`.
12. **Hygiene is capture avoidance.** With one global namespace,
    resolving a macro body's free names at the definition site and at
    the use site coincide, so the operative part of the hygiene rule is
    that substituting an argument into a macro body alpha-renames any
    binder of the body that would capture a name free in the argument.
    That is what is implemented and tested; a real definition-site
    environment arrives with the subject.

13. **The object type is identified by shape, not by name.** It is the
    unique declared type with exactly one constructor carrying two fields
    of its own type — the application constructor. Every other
    constructor of that type must be a leaf. Two such constructors, a
    non-leaf non-application constructor, or two such types are each a
    named `GenerateError`. A program with no such type generates nothing,
    which is why `nat === Zero | Suc nat` is left alone (`Suc` carries
    one field, not two).
14. **The step-outcome type `O` and the result type `R` are the
    outcome-shaped declarations, first and last.** A candidate is a
    declared type other than the object type with exactly one constructor
    carrying a single field of the object type and nothing else carrying
    fields. The first candidate in declaration order is `O`, the last is
    `R`; with one candidate `O = R`, which is `whnfF`'s Maybe shape. More
    than two is refused.
15. **The loop's mapping rule.** `loop1 f m n2 = step m …` applies
    `step m` to one continuation per `O` constructor **in declaration
    order**: `O`'s term-carrying constructor continues the loop,
    `(f n2)`; `O`'s *first* terminal is "no redex", so the loop is done
    and yields `R`'s term-carrying constructor applied to the current
    term; `O`'s further terminals map one for one onto `R`'s terminals in
    order. `loop n m = n <timeout> (loop1 loop m)` peels one `Suc` per
    attempt and yields `R`'s **last** terminal at `Zero`. Hence
    `|R| = |O|`, which the generator checks. For Maybe this is
    `step m (Just m) (f n2)` and `n Nothing …`; for the T3 shape
    `step m (f n2) (RVal m) RErr` and `n RTime …` — the artifact's `wf1`
    and `wf5Abs1` exactly.
16. **Default step arms are parameterized over `O`, not hard-wired.**
    `stepS` / `stepK` / `stepI` are generated only for leaf constructors
    literally named `S`, `K`, `I` (which is what §6c asks for), and take
    their two outcome constructors from `O`: "no redex" is `O`'s first
    terminal and a contraction is wrapped in `O`'s term-carrying
    constructor. The rebuilt `x z (y z)` is spelled with the object
    type's own application constructor and its own `rb`.
17. **A core's fuel loop is its arm named `loop`, and the core's name
    denotes it.** `generate.py` adds `loop` and `loop1` only when `loop`
    is absent, and `step` only when `step` is absent, so a written one
    always wins. `loop1` without `loop` is refused. `SYNTAX.md` §3's
    `myInterp |- …` therefore has a term to name.
18. **A core is an interpreter core** when an object type is declared and
    the core writes any part of the interface: an arm named `step`,
    `loop`, or `step<C>` for a leaf `C` of the object type.
19. **Arms are scoped to their core.** A core arm's backend name is
    `core_arm`, and a name inside a core resolves to a sibling arm before
    anything program-level, so two interpreter cores can each have their
    own `step` while sharing one `sp`. Results are keyed `core.arm`, and
    also by the bare name when it is unambiguous program-wide.
20. **`S`, `K` and `I` always mean the ISA at level 0**, even when the
    object type declares constructors of those names. That is
    `SURFACE-LANGUAGE-DESIGN.md` §6b's two symbol tables with only the
    level-0 one implemented, and `EXAMPLES.md` §4's "outside it they
    would be the level-0 combinators". It is what lets
    `omega = S I I (S I I)` sit in the same file as
    `term5 === S | K | I | App term5 term5 | Err`.
21. **`nil` and `cons` joined the prelude.** The generated walker needs
    the Scott list, and `EXAMPLES.md` §4 writes `sp m nil …` without
    declaring a list type; `SURFACE-LANGUAGE-DESIGN.md` §4 lists Scott
    lists in the standard subject. The prelude is now `pair`, `hd`, `tl`,
    `nil`, `cons`; a program may still define its own.
22. **`omega` is written in the surface, not built in**
    (`omega = S I I (S I I)`, a zero-binder top-level arm), so the one
    authored difference between `wf5Abs` and `wf5Omg` stays visible in
    the source.
23. **A closing `}` ends the last arm of a core**, so a one-arm core fits
    on a line (`wf5Abs := { stepErr acc = Errd }`). Elsewhere the
    newline rule of decision 6 is unchanged.

## Discrepancies found in the specification

### Resolved in the specification

These eight were reported against the first draft of `SYNTAX.md` and are
now settled by the note itself; the code follows the note, and each line
says how.

1. **The ASCII column was not injective** — `↦` and `→` both spelled
   `->`, contradicting §1 item 4. *Resolved:* §2 now spells the fact
   arrow `=>`, leaving `->` the signature arrow alone. `MAPSTO` and
   `ARROW` are separate token kinds in both lexicons, no grammar
   position has to disambiguate them, and `check_table` is a **strict
   bijection with no shared-kind exceptions** (`SHARED_KIND_ROWS` is
   gone).
2. **The arm equation `=` was missing from the table.** *Resolved:* §2
   now carries an "arm equation" row, same spelling in both lexicons;
   maximal munch puts `===` and `=>` ahead of `=`.
3. **Arms at top level were not in the grammar**, though `EXAMPLES.md`
   §2 and §3 use them. *Resolved:* §4's `decl` now reads
   `type-decl | sig | arm | macro | core | def`. `Arm` is a top-level
   declaration and compiles exactly as a one-arm core's arm.
4. **`@` was spent twice in ASCII** (axis pick `2@`, fuel `<t>@10`).
   *Resolved:* §4's lexing notes now state the rule this package
   implements — `<digits>@` is an axis pick, `@<digits>` or `@[]` is
   fuel — so `@` is not ambiguous and both lexicons hand the parser the
   same kinds.
5. **`}` closes both a core and a namespace literal in ASCII**, while
   Unicode has `⦄`. *Resolved:* §2's namespace-literal row now states
   that `⦄` and `}` are one token kind. `⦄` is therefore declared in
   `lexicon.UNICODE_ALIASES` rather than as a row, which is what keeps
   the table a strict bijection; the renderer picks the closer from the
   construct.
6. **Subscript digits appear both inside identifiers** (`flipK₁`) **and
   as the fuel notation** (`⟨t⟩₁₀`). *Resolved:* §4's lexing notes now
   say they do not collide because a subscript cannot start an
   identifier, and that identifier subscripts normalize to ASCII digits
   — which is what the Unicode lexer does, so `flipK₁` and `flipK1`
   denote the same tree.
7. **Tier 1 ASCII names are ordinary identifiers in the Unicode
   lexicon**, so both `C` and `⇄` give `Name("C")`. *Resolved:* §4's
   lexing notes now state exactly this, and that the Unicode renderer
   emits the glyph. Tree round-trip is unaffected, which is the law that
   matters.
8. **`add` = 42 was given without its construction.** *Resolved:* the
   construction is now pinned here as decisions 3 and 4 below (per-arm
   `Y`-tied generator, branch lambda lifted into its own
   supercombinator), so the number is reproducible rather than
   coincidental; `sub` = 43 follows from the same two.

Six more, reported against `SURFACE-LANGUAGE-DESIGN.md` §6c and
`SYNTAX.md` §3 after step 3, now rewritten there:

9. **"One step arm per constructor" meant per *leaf*.** *Resolved:* §6c
   now reads "One step arm per leaf", and says why the application
   constructor cannot have one — it is the spine the walker descends,
   not a head that fires.
10. **§6c had no result type, though the loop needs two.** *Resolved:*
    §6c now declares "Two more types: the step outcome `O` and the
    result `R`", says the arms return `O` and the loop returns `R`, and
    says why: the loop has a timeout the arms cannot express.
11. **§6c did not say how the application constructor is found.**
    *Resolved:* §6c now identifies the object type by shape — the one
    type with exactly one constructor carrying two fields of its own
    type — and makes zero, two, or a non-leaf sibling an error.
12. **The default arms key off names while everything else keys off
    shape.** *Resolved:* §6c now states it as a deliberate exception —
    "the one place a name rather than a shape decides what the ISA is" —
    and says a leaf named otherwise gets no default and must be written.
13. **`SYNTAX.md` §3's written loop did not compile** (mutually
    recursive `loop`/`loop1`, and a body mixing Maybe with a three-way
    outcome). *Resolved:* §6c now spells the written loop in the
    artifact's shape, `loop1 f m n2 = step m (Just m) (f n2)` with
    `loop n m = n Nothing (loop1 loop m)`, and says it passes itself to
    its helper "rather than recursing mutually"; §3 carries that source.
14. **`EXAMPLES.md` §4 spelled constructors in lower case.**
    *Resolved:* §3 of `SYNTAX.md` and §4 of `EXAMPLES.md` now carry the
    exact sources of `tests/corpus/interp-*.ski`, constructors
    capitalized.

### Still open

None. `SYNTAX.md` §2/§4 and `SURFACE-LANGUAGE-DESIGN.md` §6c are both
consistent with what this package builds; every item above is settled in
the notes themselves.

### A bug this step found

Adding the interpreter tests made the suite allocate enough that
`Prober.read_nat`'s memo table started returning another numeral's
answer: it was keyed by `id(node)` without holding a reference, and
CPython recycles an id as soon as its object is collected. It surfaced as
`dec 3 == 0` in one parametrization only. Fixed by storing
`(node, value)` so the node pins its own id, with an identity check on
lookup; `tests/test_probe.py` now has two regression tests for it. The
bug was latent from step 2 and never affected a compiled term — only the
reader that decodes one.

## Layout

```
python/
  pyproject.toml
  README.md
  skijack/
    __init__.py
    ast.py        the lexicon-free syntax tree
    lexicon.py    the token table as data + lex_ascii / lex_unicode
    parser.py     one grammar over token kinds, two pass
    render.py     tree -> text in either lexicon
    expand.py     macros, cases, cells/picks, cores, bracket abstraction
    generate.py   the type-generated forms: walker, rebuilder, step arms, loop
    probe.py      behavioral decoding: markers and the Scott-numeral reader
  tests/
    conftest.py
    corpus/       every source in both spellings
    test_lexicon.py test_parser.py  test_roundtrip.py
    test_expand.py  test_probe.py    test_generate.py
    test_interpreter.py   -- the milestone, against the paper's artifact
```
