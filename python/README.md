# `skijack` — the surface language, steps 1 and 2

Steps 1 (syntax: two lexicons, one grammar, one tree, a renderer) and 2
(codegen to closed `{S,K,I}` terms, without types and without quotation)
of `DESIDERATA.md` §6.

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
174 passed
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
  1–3, read behaviorally.

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

## What is *not* here

Out of scope for these two steps, and refused with a clear error by
`expand_program` rather than silently mis-compiled:

* **types** — `===` declarations and `:` signatures are parsed and kept
  in the tree; field types and signatures are ignored (`DESIDERATA.md`
  item 11, Stage B). What *is* checked is Stage A's case completeness,
  case order, and constructor arity.
* **quotation and level-1 packaging** — `<t>`, `<t>@n`, `I |- <t>@n`,
  `?^/a/b` and `ns{…}` parse, render and round-trip, but reaching the
  code generator raises `ExpandError`. `EXAMPLES.md` §4 and §5 and
  `SYNTAX.md` §3 are therefore parse/round-trip corpus only.
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

### Still open

None. Nothing in the corrected `SYNTAX.md` §2 table, §4 grammar or §4
lexing notes is inconsistent with the rest of the note or with
`EXAMPLES.md` as far as this package exercises them.

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
    probe.py      behavioral decoding: markers and the Scott-numeral reader
  tests/
    conftest.py
    corpus/       every source in both spellings
    test_lexicon.py test_parser.py test_roundtrip.py
    test_expand.py  test_probe.py
```
