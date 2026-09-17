# Design note: a subject-oriented surface language over SKI

*2026-09-16. Follow-up to the paper ~/ski-in-ski/mss.tex, not part of
it. This note fixes the kernel forms, the ABI, and the compile rules
for a Hoon-like macro language whose target is closed `{S,K,I}` terms,
so that syntax can be designed against a stable target. Nothing here is
built. Where a rule is already implemented in the repository under
another name, the name is given. Syntax in examples is illustrative
only; the note is about what the forms mean and what they compile to,
not how they are spelled.*

Language name bikeshedding:
* Skilling
* Skyjack <- SKIjack
* Skiff
* Skyborn
* Skyclad <-
* Skinnydip
* SKIrocket
* Skirret

## 0. Thesis

Hoon is sugar over Nock plus a standard library, compiled away. The same
layering is available over SKI, with one difference that is a theorem
rather than a choice: quotation of a live term is impossible
(Proposition 3.1 of the paper, from Jay and Given-Wilson), so the line
between compile-time and runtime quotation is forced. Everything on the
encoded side of that line is closed under the calculus, including
running encoded terms, comparing them, and building cores. Everything
that would turn a live value back into data is unavailable and must be
staged. The language's design problem is to make that line visible and
comfortable.

The other difference, which is a gain, is that weak SKI reduction is
call-by-name: arguments are never forced early, `K I Ω` is `I`, and no
form needs thunking.

## 1. What already exists

- **A macro layer.** `D(name, [binders], body)` and `AL(name, term)` in
  `tower_harness.py` define named terms with binders; `expand` applies
  bracket abstraction (`aviary_kernel.abstraction`) and yields a closed
  `{S,K,I}` term. This is the compiler's back end. It has no subject, no
  types, and no surface; binders are Python strings.
- **Scott encoding** for object terms, lists, `Maybe`, and numerals, in
  the fixed continuation orders recorded in the paper's §3.1.
- **Recursion** through `Y = S (K (S I I)) (S (S (K S) K) (K (S I I)))`,
  14 atoms, with every recursive definition written as a generator that
  takes its own fixpoint as first argument (`spGen f m acc`, and so on).
  That is open recursion, and it is the arm-with-self-as-subject
  convention already.
- **Interpreters** `whnfF`, `wfQ`, `wfN` (618, 950, 1,066 atoms), the
  unquoter `UQ` (43), and equality on encoded paths `EQ5` (240).
- **The behavioral verification discipline:** every claim about a
  compiled term is checked by applying it to fresh atoms and reading
  which one it selects, never by reading combinator syntax.

## 2. Representation ABI

These decisions are the interface between the compiler and the standard
subject. They are fixed here so the surface can vary without moving them.

**Pairs.** `[a b]` is the Scott pair `λc. c a b`. Projections: head
`p K`, tail `p (K I)`. Axis addressing is Nock's: axis 1 is the whole,
axis 2 the head, axis 3 the tail, axis `2n` the head of axis `n`, axis
`2n+1` its tail. An axis compiles to the corresponding chain of
projections, innermost first; cost is one projection per bit of the
axis, as in Nock.

**Subject.** Every compiled term is a function of one argument, the
subject, a nested pair. Wings and names are resolved to axes at compile
time (faces are a compile-time symbol table, not data). There is no
lexical environment at runtime; bracket abstraction over the subject
variable is the closure mechanism.

**Gates.** A gate is a core `[battery [sample context]]` with one arm,
following Hoon: the battery is the compiled body, abstracted over the
core; the sample sits at axis 6 and the context (the subject at the
point of definition) at axis 7. Calling a gate with an argument
replaces the sample and pulls the arm: `pull(replace(gate, 6, x))`.
(A lighter dialect compiles `|=` to a plain λ by bracket abstraction
with no core; it is faster and has no `..$`. Both are available from the
same kernel; the core dialect is the one that makes Nock 9 and `%=`
meaningful.)

**Cores.** `[battery payload]` with the battery a tuple of arms. Each arm
is compiled with the whole core as its subject. The core is tied once:
`core = Y (λself. [ ⟨arm₁[self], …, armₙ[self]⟩ payload ])`. Pulling arm
`i` is `(πᵢ (head core)) core`. Replacing the payload (`%=`) is building
a new pair with the same battery; because the battery's arms take the
core as an argument rather than closing over the payload, no
recompilation is needed. This is the property the paper's resolver
lacks: its facts are closed over, so a new fact means re-expanding the
term on the host.

**Sum types.** A type declaration is an ordered constructor list, each constructor followed by the types of its fields (`Suc nat`); the field types are ignored by the expander and used by the type stage (`DESIDERATA.md` item 11). It
generates the constructors, each `λ fields. λ c₁ … cₙ. cᵢ fields`, and
the case form for that type, which applies a datum to `n` continuations
in declaration order. The order is part of the ABI: the paper's object
terms are the declaration `S, K, I, App(t,u)`, and every interpreter
depends on that order. Changing a declaration changes every case form
over it, which is exactly the outcome-type-growth phenomenon of the
paper stated as a compiler fact.

**Numerals.** Scott numerals for data (`zero`, `suc`), matching the fuel
convention; Church numerals only where iteration is wanted. No native
atoms exist; arithmetic is unary and O(n). This is the one place Nock is
richer at the machine level, and the language should not pretend
otherwise.

**Booleans.** `K` for yes and `K I` for no, so `?:` is application to two
continuations.

**Encoded terms.** The five-constructor encoding `S, K, I, App, Scry` of
`scry_harness.py` is the object language of the virtualizing
interpreters. A literal term in source compiles to its encoding at
compile time.

## 3. Kernel forms and their compile rules

Written as `⟦form⟧ᵤ`, the compilation of a form against subject
variable `u`; `abs(u, t)` is bracket abstraction of `t` over `u`.

| form | rule |
|---|---|
| axis `+n` | the projection chain for `n`, applied to `u` |
| wing `a.b` | resolve to an axis at compile time, then as above |
| cell `[a b]` | `pair ⟦a⟧ᵤ ⟦b⟧ᵤ` |
| literal (a term as data) | its Scott encoding, a closed term; no `u` |
| pin `=+ x body` | `⟦body⟧ᵥ [⟦x⟧ᵤ u]`, i.e. body compiled against the extended subject `v = [x u]` |
| gate `\|= body` | `core([abs(self, ⟦body⟧_self)] [placeholder u])` per §2 |
| call `(g x)` | `pull(replace(⟦g⟧ᵤ, 6, ⟦x⟧ᵤ))` |
| core `\|% ++a₁ … ++aₙ --` | `Y (λself. [⟨abs(self,⟦a₁⟧_self), …⟩ u])` |
| pull `a.c` | `(πₐ (head ⟦c⟧ᵤ)) ⟦c⟧ᵤ` |
| replace `%= c a x` | `pair (head ⟦c⟧ᵤ) (set(payload, axis(a), ⟦x⟧ᵤ))` |
| case `?- x [%cᵢ fields] bodyᵢ` | `⟦x⟧ᵤ (λ fields. ⟦body₁⟧) … (λ fields. ⟦bodyₙ⟧)` in declaration order, each body compiled against the subject extended by its fields |
| if `?: c a b` | `⟦c⟧ᵤ ⟦a⟧ᵤ ⟦b⟧ᵤ` |
| loop `\|- body`, `$` | a one-arm core whose arm is `body`; `$` is a pull on it |
| arm `++ name body` | a member of the enclosing core's battery; compiled once, shared as one node, reached by a pull at runtime |
| macro `+* name body` | expanded at each use site at compile time; no runtime cost to reach, duplicated per use; see §3a |
| eval `.* fuel term` | `whnfF ⟦fuel⟧ᵤ ⟦term⟧ᵤ`, a `Maybe`; under a virtualizing interpreter, `wfQ E …` or `wfN E …` with their outcome types |
| scry `.^ path` | the leaf `Scry ⟨path⟩` in the object language; stuck under host reduction, resolved only under `wfQ`/`wfN` |

Everything in the table is either an application, a pair, a projection,
a Scott constructor, or bracket abstraction, so every program compiles
to a closed `{S,K,I}` term applied to the standard subject.

### 3a. Arms versus macros

The two definition keywords mirror Hoon's `++` and `+*`, and the cost
model decides between them. An arm is one node in the DAG, shared by
every use, and costs a pull to reach: the projections of its axis plus
one application. A macro is expanded into every use site, so it costs
nothing to reach and is duplicated per use. Small things, the derived
combinators, booleans, projections, and the sugar of §3b, want to be
macros; large things, `EQ`, the interpreters, the standard subject's
library, want to be arms. The kernel table above is the whole compiler;
most of a comfortable surface is macros over it: `?:` over `?-`, `=/` as
pin plus face, `|-` as a one-arm core, and so on. That is how the
compiler stays small and how the surface can grow without touching it.

**Hygiene is a decision, and the default is hygienic.** If a macro body
is expanded before wings are resolved, its names bind at the use site
and capture the caller's faces, which is what Hoon's `+*` does and is
occasionally wanted. If wings in the body are resolved at the definition
site and the expansion carries axes rather than names, the macro is
hygienic. The default is hygienic, because in a subject-passing language
a capture is invisible in the source and shows up only as a wrong axis;
a separate, clearly marked capturing form is available for the cases
that want it.

### 3b. Derived combinators and the basis as a declaration

`B = S (K S) K`, `C = S (S (K (S (K S) K)) S) (K K)`, and `W = S S (K I)`
are values in the standard subject and macros in the surface, at no cost
to the kernel; the runtime jets them by hash (`RUNTIME-DESIGN.md` §2).

Making them *leaves of the object language* is a different decision,
and a real tradeoff. Abstraction into `{S, K}` alone is quadratic in
size; Turner's algorithm with `B` and `C` (and their primed variants) is
near-linear, and the paper's census measured the effect on the
interpreter's own core: 151 atoms over BCKW against 249 over SKI, about
40% smaller. But a leaf is not free. Each added constructor is one more
continuation in every encoded node, so every leaf encoding grows by
about two atoms, every case form over the type grows, and the
interpreter gains an arm per leaf (`B` and `C` need three arguments, `W`
two). This is the paper's outcome-type growth as an engineering cost.
Whether it pays depends on how often `B` and `C` occur in compiled
output relative to all leaves; for Turner-style abstraction they
dominate, so a net win for large programs is expected, but it is to be
measured, not assumed.

The design answer is that **the basis is a type declaration**. The
kernel dialect is `+$ term [%s] [%k] [%i] [%app t u]`, the `{S,K,I}` of
the paper's artifact and theorems, and it is the reference. An extended
dialect is another declaration, `+$ term7 [%s] [%k] [%i] [%b] [%c] [%w]
[%app t u]`, whose constructors, case form, and interpreter are
generated by the same rules. The compiler targets whichever basis the
program declares. The interpreter for the extended dialect is itself the
first serious program to write in the surface, and its size relative to
`whnfF` is the measurement the tradeoff above needs.

## 4. The standard subject

The subject every program is compiled against is a nested pair holding,
at fixed axes:

- `S`, `K`, `I` as values, and `Y`;
- pairs and projections, booleans, Scott lists with fold, `Maybe`,
  numerals with successor, predecessor, addition, equality;
- `EQ` on encoded terms (the 4- and 5-constructor versions);
- `UQ`, the unquoter;
- `whnfF`, `wfQ`, `wfN` as arms, the analogue of `++nock` in `hoon.hoon`;
- the constructors and case forms of the built-in types (object terms,
  outcomes, oracle answers).

Estimated size two to three thousand atoms, compiled once and shared by
reference. Its axes are the ABI; a program compiled against one layout
is not portable to another, as in Nock.

## 5. The quotation line, stated as rules

1. A literal in source is quoted at compile time. This is the only
   quotation the language performs.
2. A value of a data type (any Scott-encoded type declared in the
   language) may be compared with `EQ`, passed to `.*`, stored in a
   namespace, and re-encoded one level up by a definable data
   transformation `⟨t⟩ ↦ ⟨⟨t⟩⟩`.
3. A value of function type (a gate, a core, an arm) can be applied and
   nothing else. It cannot be compared, quoted, or stored as a fact. No
   `!=`, no `!>`, no `.=` on functions.
4. `.*` on a computed term is available only if the term was built from
   data forms; a gate cannot be turned into a term to run.

Rule 3 is where a type system earns its keep: the compiler must know
which values are data. The cheap version is a naming convention; the
honest version is a type checker over the declarations, which is
ordinary work in the macro layer.

## 6. Execution model: level 0 and level 1

The compiler has one target, closed `{S,K,I}` terms, and one code
generator. What varies is the level a declaration runs at, and the
level is a property of the declaration, not a choice made per
expression.

**Level 0, direct.** The term is handed to the host reducer as is: the
interpreters, the standard subject, and anything runtime-facing. No
fuel, no interpreter in the loop; a `Scry` leaf is an inert atom, which
is why nothing at level 0 may use one.

**Level 1, virtualized.** The term is quoted at compile time and the
executable the host reduces is `interp E n ⟨program⟩`: an interpreter
applied to the encoded program, a resolver, and fuel. Scry is live, fuel
is explicit, the outcome is the interpreter's outcome type. Any
declaration that uses `∵` is level 1; the compiler packages it so
without being asked. The default interpreter is the blocking resolver
loop `wfN`; `interp ⊢ …` selects another.

This is Urbit's split: the kernel runs raw Nock, userspace runs under
`+mink` with scry, and jets make the virtualization free. Here the
interpreters and library are level 0, applications are level 1, and the
runtime's first jet is the interpreter, after which a level-1 program
costs what a level-0 program does. Towers beyond level 1 are the
explicit `⟪ ⟫` form nested, for when an interpreter is to run an
interpreter (the paper's T2).

### 6a. What codegen targets, exactly

Every interpreter reimplements the ISA: its `S`, `K`, `I` arms are its
own code, reduced by the host or by the interpreter below it. So the
alphabet a level-1 program is written in is the *object type of the
interpreter it will run under*, a declared type such as
`{S, K, I, App}`, `{S, K, I, App, Scry}`, or a dialect with `B`, `C`,
`W`. The code generator therefore does two things in sequence:

1. **Expand** the declaration to a term over the target alphabet, by the
   rules of §3. At level 0 the alphabet is the host's ISA and the result
   is the executable. At level 1 the alphabet is the interpreter's object
   type; the result is a term over that alphabet, not yet executable.
2. **Quote**, at level 1 only: encode the term as Scott data over the
   declared type's constructors (`encS5 …` for a five-constructor type),
   and wrap it with the interpreter application.

Both steps emit only `{S,K,I}`; the quoted datum is pure `{S,K,I}` even
when the object alphabet has extra leaves, because a leaf is a
constructor. "Targeting the interpreter" and "targeting pure SKI" are
therefore both true, of different steps.

### 6b. Two symbol tables

Inside `⟪ ⟫` names resolve differently from outside it, and the compiler
keeps two tables:

- **The level-0 table:** the standard subject's schema. Names are axes
  into the subject the host applies the term to.
- **The level-1 table:** the object type's constructors, plus the
  *quoted* standard subject. A level-1 program does not share the
  level-0 subject (it is data at a different level); it receives the
  same library as a Scott-encoded value, `⟨subject⟩`, computed once and
  shared by reference across every level-1 program. Names inside `⟪ ⟫`
  that are library names resolve to axes into `⟨subject⟩`; names that
  are constructors of the object type resolve to the constructors; and
  application inside `⟪ ⟫` is the `App` constructor.

This is how Arvo sits in userspace's subject. It also fixes what the
runtime's jet table must contain: the dictionary of §5 of `DESIDERATA.md`
*and its image under quotation*, since a level-1 program's use of `EQ`
is the encoded `EQ`, walked by the interpreter, until the runtime
recognizes it.

### 6c. The interpreter interface

An interpreter is a core that the compiler can put in the `interp`
position. Its interface is generated from, or checked against, three
type declarations, and the reference implementation reproduces the
paper's `whnfF`, `wf5Abs`, and `wf5Omg` from this interface atom for
atom (`python/tests/corpus/interp-*.ski`).

- **The object type** (the alphabet), identified by shape: the one
  declared type with exactly one constructor carrying two fields of its
  own type, the application constructor; every other constructor of
  that type must be nullary, a leaf. Zero or two such constructors, a
  non-leaf non-application constructor, or two such types are errors.
  The declaration generates the constructors, the case form, the spine
  walker `sp` and the rebuilder `rb` at that arity (the paper's
  `spQ`/`rbQ` are the five-constructor instances).
- **One step arm per leaf.** The application constructor has no arm and
  cannot: it is the spine the walker descends, not a head that fires,
  and the walker hands the collected arguments to the leaf it reaches.
  The standard subject supplies default arms for leaves *named* `S`,
  `K`, `I`, which is the one place a name rather than a shape decides
  what the ISA is; a leaf named otherwise gets no default and must be
  written. So an interpreter that only adds a leaf writes only that
  leaf's arm, which is the paper's one-site authorship as a compiler
  convenience. If the core omits `step`, it is generated as `step m =
  sp m nil stepC₁ … stepCₙ` in declaration order.
- **Two more types: the step outcome `O` and the result `R`.** The arms
  return `O`; the loop returns `R`; they differ because the loop has a
  timeout the arms cannot express. Both are found by shape among the
  non-object types: exactly one constructor carrying one field of the
  object type and no other constructor carrying fields. The first such
  declaration is `O`, the last is `R`; a single one serves as both (the
  Maybe shape of `whnfF`); their constructor counts must agree.
- **The loop, generated from `O` and `R`** unless written. Rule: peel one
  `Suc` per attempt, returning `R`'s last terminal at `Zero`; apply
  `step m` to one continuation per `O` constructor in declaration order,
  where the term-carrying constructor continues the loop with the new
  term and the remaining fuel, `O`'s first terminal (no redex) returns
  `R`'s term-carrying constructor applied to the current term, and each
  further terminal of `O` maps to the terminal of `R` at the same
  position. For `maybe ≡ Nothing ∣ Just term` this yields the paper's
  `wf1`/`wfGen`; for `outcome ≡ Stepped term ∣ Done ∣ Errd` with
  `result ≡ RVal term ∣ RErr ∣ RTime` it yields `wf5Abs1`/`wf5Abs`. A
  written `loop` in the core overrides the generated one; because arms
  are tied with per-arm fixpoints, a written loop passes itself to its
  helper as the artifact does (`loop1 f m n2 = step m (Just m) (f n2)`,
  `loop n m = n Nothing (loop1 loop m)`) rather than recursing mutually.
- **The core's name denotes its loop.** `whnfF ⊢ …` applies it.

Two interpreters with the same three types and different arms are the
paper's `wf5Abs`/`wf5Omg`; an interpreter with an added constructor and
a resolver parameter is `wfQ`. The conformance tests for a user
interpreter whose `S`, `K`, `I` arms claim to be the ISA are the paper's
T0–T2 counts.

## 7. Cores as the internalized namespace

The paper's blocking resolver is host-side because its facts are closed
over. Under the core ABI the resolver is `[battery facts]` where the
battery has one arm, lookup, compiled against the core, and `facts` is
an encoded list of pairs. Learning a fact is `%=` with `cons`; the
resume loop becomes a one-arm core whose arm runs `wfN` with the
resolver, inspects the outcome, and on a block pulls itself with the
extended resolver. The whole loop is then one closed term, which is the
"pure-SKI driver" the paper leaves open. The decoder from an encoded
payload back to a path is not needed inside the calculus, since the
blocked path is already encoded data; it was only ever needed to consult
a Python dict.

## 8. Self-hosting

The compiler of §3 is a function from Scott-encoded syntax trees to
Scott-encoded `{S,K,I}` terms. Both are data, so the compiler is
definable in the language and compiles to a closed term, the analogue of
`++mint` in `hoon.hoon`. Its core is bracket abstraction over encoded
terms with a variable tag, the same combinator the partial-evaluation
design (`~/ski-in-ski/PARTIAL-EVALUATION-DESIGN.md`, Stage 4) needs to unfold under
an unknown head. Building it once serves both. Cost is unknown; a few
thousand atoms is the guess, and running it on itself is a T2-scale
computation.

## 9. Worked example

The interpreter's step function, in an illustrative syntax, compiled
against a subject holding the object-term type and the spine walker:

```
+$  term  [%s] [%k] [%i] [%app t=term u=term]
+$  step  [%stepped t=term] [%done] [%errd]
++  step
  |=  m=term
  (spine m ~ arm-s arm-k arm-i)
```

`spine` is `spQ`, the arms are `stepSQ`, `stepKQ`, `stepIQ`, and the
whole compiles to the 569-atom `step` of the paper. The fuel loop is a
`|-` over it with a Scott numeral as sample. Writing the interpreter in
the surface and checking that it compiles to a term with the same
behavior as `whnfF` (by the fresh-marker probes, and by T0's 340
contractions) is the first milestone; writing the compiler in the
surface is the second.

## 10. What is decided here and what is left to syntax

Decided: Scott pairs as cells with Nock axes; subject-passing with
compile-time wing resolution; Hoon's gate layout; cores tied with `Y`
and pulled by projection; declaration order as continuation order;
Scott numerals; the quotation rules of §5; the two modes of §6; two
definition keywords, arm and macro, with hygienic macros by default
(§3a); derived combinators as names and macros, with an extended basis
available only as a separate type declaration (§3b).

Left to syntax: runes versus S-expressions; whether lexical names exist
alongside wings; how declaration order is made visible; whether `.*` is
a form or a subject arm; how the data/function line of §5 is written;
and how the mode of §6 is marked; how the capturing macro form is
marked; and how a program declares which basis it targets.

## 11. Order of work

1. The ABI of §2 as a follow-on file: pairs, axes, cores, pull, replace,
   with fresh-marker checks. Small.
2. The standard subject of §4, compiled and measured.
3. The kernel compiler of §3 in Python over a syntax-tree data type, so
   the interpreter can be written in the surface and checked against
   `whnfF` (§9, first milestone).
4. The resolver as a core (§7): the paper's open problem closed.
4a. The BCKW dialect (§3b): its interpreter written in the surface, and
    the size and step-count comparison against `whnfF` that decides
    whether extended bases are worth their dispatch cost.
5. The compiler in the surface (§8), and the partial-evaluation Stage 4
   it enables.
