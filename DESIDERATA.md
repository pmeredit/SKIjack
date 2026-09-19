# Desiderata: the language as a macro

*2026-09-16. What the language must be, stated before syntax, with
`~/urbit/nockasm` as the model for the discipline (not the notation) and
the paper in `~/ski-in-ski` as the source of the constraints. This note
sits above `SURFACE-LANGUAGE-DESIGN.md`, which fixes the ABI and compile
rules, and `RUNTIME-DESIGN.md`, which fixes what runs the output.*

## 1. What nockasm got right, and what transfers

Nockasm is "a thin macro over the Nock ISA": named opcodes, an axis
schema, two structural macros, and nothing else. Its properties, and
their SKI counterparts:

| nockasm | property | SKI counterpart |
|---|---|---|
| `(%inc .x)` → `[4 0 2]` | every form has one exact expansion; the macro adds no semantics | every form expands to one closed `{S,K,I}` term, by bracket abstraction and nothing else |
| `:subject {.a .b .c}` | names resolve to axes at compile time; schemas carry no types | **does not transfer**; see below. Names resolve at compile time to supercombinators, not to positions in anything |
| `#let`, `#match` with `+peg(3, n)` | structural macros with a stated shift rule for names already in scope | case binds its fields as ordinary lexical names, discharged by bracket abstraction; there is nothing to shift |
| `%arm` as a synonym of `%const` | intent markers that change nothing in the expansion | the same: an equation is a constant with a declared role |
| `(%nock F)` | an opaque embed for foreign fragments, never rewritten | `(%ski T)`: a raw combinator term embedded as is |
| `expand(render(x)) == lower(x)` | render is canonical and round-trips | the same law over the syntax tree |
| `lower(lift(f)) == f` | lifting a formula back to source is sound by construction and never guesses intent | lifting a term to named form names only exact structural matches of a dictionary and leaves everything else raw |
| source cord is the canonical noun form | storage is text; expansion is always a library call | the same: a `.ski`-source file is a string, expansion is a call |
| Python oracle, Hoon, nockvm, Rust, byte-identical | several executors of one contract | Python oracle first, the reference reducer as its checker; runtime later, byte-identical |
| frozen at version 1.3 | small enough to finish | the kernel is a dozen forms and should stay that way |

**Two things do not transfer.**

*Equality.* Nockasm's `#match` compares the scrutinee against noun
literals with opcode 5, Nock's native equality on nouns. SKI has no
native equality; case analysis is by constructor, applying a Scott datum
to continuations, and literal comparison is `EQ` on encoded data, which
the language provides but the calculus does not. The paper's
Proposition 3.1 is the reason.

*The subject.* Nock needs one because a formula is data interpreted
against an environment: `[4 0 2]` means nothing until you say what it
runs against, so names must be addresses into that thing and the shift
rules follow. Bracket abstraction removes the premise. After it every
subterm is closed and means the same thing wherever it sits, so there is
no environment for a name to address, nothing to extend, and nothing to
shift. The subject is Nock's answer to a problem this calculus does not
have, and an earlier draft of this note inherited the answer without the
problem: item 2 below used to claim axis-resolved names, a pin form with
a shift rule, and one subject argument, none of which was ever built and
none of which should be. What survives is the *boot* sense, and only
that: a program is a function of the single argument the runtime hands
it, and `poke` replaces a kernel wholesale (`RUNTIME-DESIGN.md` §3b).
That one argument keeps the name **subject**; nothing else does.

## 2. Desiderata

1. **Thin.** Every form has one expansion, given by a rule in
   `SURFACE-LANGUAGE-DESIGN.md` §3, and the expander is a fold over the
   syntax tree with no semantics of its own. If a form cannot be stated
   as such a rule it does not belong in the kernel; it is a macro
   (§3 below) or it is out.
2. **Supercombinator.** Every named thing compiles to a closed term:
   the expander lambda-lifts each equation and ties recursion with `Y`,
   so its meaning is a function of itself alone and of nothing around
   it.
   Names resolve in a compile-time table, never at run time; there is no
   environment, no frame, and nothing to shift. The one runtime object
   that resembles an environment is the **subject** the runtime applies
   a program to at boot, and that is an argument, not a scope. (The
   word is Hughes's, 1982, and §3 uses it for Tier 2. We take the
   lifting and not the motivation: supercombinators were proposed as the
   alternative to compiling into a fixed combinator set, and here the
   fixed set is the ISA, so each lifted equation is abstracted into
   `{S,K,I}` afterwards. The surface is equational and has binders; it
   is the target that is variable-free. Three words, three levels: an
   **equation** is what you write, a **supercombinator** is what it
   compiles to, and a **core** is the group they are declared in.)
3. **Exact.** Expansion is deterministic and total on well-formed input:
   the same source gives the same closed term, atom for atom, on every
   executor. The reference reducer's counts are the conformance oracle.
4. **Lawful.** `expand ∘ render = lower` and `lower ∘ lift = id` hold and
   are tested, so source, syntax tree, and term are three views of one
   thing and none is privileged at rest.
5. **Honest about the line.** Quotation happens at compile time only;
   no form promises to turn a live value into data. Equality, `.*`, and
   storage in a namespace are offered for data types and refused for
   functions, and the refusal is visible in the surface (a type or a
   naming convention, but never silence).
6. **Honest about mode.** Direct reduction and virtualized evaluation
   are different; scry works only in the second; fuel is explicit
   there; a declaration's level is stated, not inferred per expression
   (`SURFACE-LANGUAGE-DESIGN.md` §6).
7. **Lazy by default, and says so.** Weak SKI reduction is call-by-name.
   The surface must not suggest strictness it does not have.
8. **Sound to lift.** A term produced by the expander can be lifted back
   to named source by exact structural matching against the dictionary
   of known expansions, and only that; unknown subterms stay raw. This is
   the same operation the runtime's jet table performs (`RUNTIME-DESIGN.md`
   §3), and it is metalevel by theorem.
9. **Small.** The kernel stays at about a dozen forms; growth happens in
   the standard subject and in macros, which are user-definable, not in
   the expander.
10. **Disciplined about paths.** A scry path is a value of a declared
    path type, a list of tagged segments, never an arbitrary term; the
    namespace is routed by prefix through mount tables, so it is a
    namespace and not a dictionary. `SYNTAX.md` §6.
11. **Typed at compile time, erased at codegen.** The calculus has one
    type, so any discipline is a restriction on source, never on terms:
    the checker is a pass that can reject and never rewrites, and the
    expander's output is the same whether checking is on or off, so the
    laws of item 4 are untouched. Two stages. Stage A, with the
    expander: constructor arity; case completeness and order (wrong
    continuation order is silent wrong semantics, the most dangerous
    mistake in this design); data versus function at the four positions
    that need it (`EQ`, quote, namespace, path); the interpreter
    interface; the two symbol tables. Stage B, later: Hindley–Milner
    over declared sum types and function types, so that `Suc : nat →
    nat` and `Suc K` is an error. Declarations carry field types from
    the start (`Suc nat`, not `Suc n`) and equations may carry optional
    signatures, which Stage A ignores and Stage B checks. Nothing is
    observable at runtime: no reflection, no dynamic typing, and
    self-hosting stays untyped where the interpreter sees it.
12. **Frozen when done.** Like nockasm, the kernel and ABI reach a
    version and stop; dialects (`term7`, and so on) are declarations,
    not kernel changes.

## 3. Four tiers of exposure

Everything the language offers is one of four kinds of thing, and the
surface should make the kind visible, because they differ in what they
cost and what they can do.

**Tier 0: primitives.** `S`, `K`, `I`, and application. These are the
ISA. They are values in the standard subject and also the only things
the expander ever emits. There is nothing to name here beyond the three
letters; the analogue of nockasm's named opcodes is not at this tier.

**Tier 1: combinators.** Closed terms over Tier 0 with a fixed meaning
and a fixed expansion, provided by the standard subject and, where they
are small, also as macros: `B`, `C`, `W`, `Y`, the pair and its two
projections, the booleans, the Scott constructors and case forms of the
built-in types, `EQ`. This is the tier that corresponds to nockasm's
opcode vocabulary: a name for a shape the reader would otherwise have to
recognize. Each entry ships with its expansion, its atom count, and its
probe-based test, and the lift dictionary (§2, item 8) is exactly this
tier's table. A Tier 1 name used in source expands to its term (as a
macro) or to a reference to one shared supercombinator node; which one is the
author's choice per name, by the cost model of
`SURFACE-LANGUAGE-DESIGN.md` §3a.

**Tier 2: supercombinators.** Hughes's term: a closed abstraction
compiled as one unit, with no free variables, so that it can be
reduced by the graph reducer without environment lookup. In this
language a supercombinator is what an equation compiles to: the
expander lambda-lifts every equation over its own parameters and over
the sibling equations it calls, and ties the group with `Y`. The interpreter's own components
(`sp`, `rb`, the step equations, the fuel loop) are supercombinators in
exactly this sense, and the paper's census is a census of their
structure. The nesting survives compilation intact — `sp` is a subterm
of `step`, `step` of `whnfF`, and 40 of the compiled interpreter's 348
distinct nodes are dictionary rows (`avon/bench/coverage.py`) — which is
what lets the runtime's jets attach by hash of the expansion, and what
makes one supercombinator one shared node. The surface should make
that closedness visible, since it is what makes a term jettable and
shareable.

**Tier 3: macros.** `+*` forms: expanded at each use site at compile
time, hygienic by default, with a marked capturing variant. Macros are
how the surface grows without the kernel growing: `?:` over `?-`, `=/`
over pin, `|-` over a one-equation core, and any user vocabulary. A macro has
no runtime existence at all, which is what distinguishes it from a
Tier 1 name used as a supercombinator, and the surface should not let the two look
alike.

The tiers nest downward: a macro expands to forms over supercombinators
and combinators, an equation compiles to a closed term over combinators, a
combinator is a closed term over primitives, and primitives are the ISA.
Lifting runs the other way and stops at the first tier whose dictionary
does not match.

## 4. What the expander is, concretely

- **Input:** a Scott-encodable syntax tree: forms with children,
  literals, names. Its canonical rest form is the source text.
- **Environment:** the schema (name → axis), the equation table of the
  enclosing cores, the macro table, and the type declarations
  (constructor lists in order).
- **Output:** a closed term over `{S,K,I}` plus, for lifting and for the
  runtime, the dictionary of named subterms with their hashes.
- **Passes:** macro expansion (hygienic, to fixpoint), name resolution
  (against the compile-time table, qualified names like `whnfF.step`
  included), lambda-lifting of equations, bracket abstraction. Each pass is a total function on the tree; none consults
  anything but the environment.
- **Laws checked in the test suite:** exactness (against the reference
  reducer's counts on the paper's targets), round-trip, lift soundness,
  and the fresh-marker probes on every dictionary entry.

## 5. Two decisions this note takes

- The **dictionary is the ABI's public face.** Tier 1's table, with
  expansions, sizes, and hashes, is a versioned artifact, published with
  the language, and it is the same table the runtime's jets key on. A
  change to it is a version change. There is one table per declared
  object type, not one table: `sp`, `rb`, and the default equations are
  different terms at different arities, so a four-constructor
  interpreter's entries and a five-constructor one's do not merge, and
  the implementation refuses to merge them (`python/skijack/dictionary.py`).
- **`EQ` is a standard-subject entry, not a kernel form.** The token
  table names it and §5 builds rules around it, but nothing supplies it
  until the standard subject exists; a program today defines its own
  (`EQ5` in the corpus) and Stage A's data check keys on the name.
- **Supercombinators are the unit of everything.** Sharing, jetting,
  lifting, and the census all operate on supercombinators. The surface
  therefore makes equations the primary way to write code, with macros for
  vocabulary and Tier 1 names for shapes, and never encourages large
  open terms.

## 6. Order of work, revised

1. The expander in Python, with the dictionary and the four laws
   tested against the reference reducer (Tier 0, 1, 3).
2. The interpreter written in the surface as equations, checked against
   `whnfF` atom for atom and count for count (Tier 2, first milestone).
3. Lift, and the runtime's jet table, from the same dictionary.
4. The dialect declaration and its measurement (§3b of the language
   note).
5. The expander in the surface (self-hosting).
